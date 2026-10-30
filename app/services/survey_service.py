import csv
import io


class SurveyService:

    def __init__(self, repository):
        self.repository = repository

    # ============================================================
    # FORMULAIRES
    # ============================================================

    def get_forms(self, owner_id, cooperative_id=None, campaign=None):
        forms = self.repository.get_all_forms(
            owner_id=owner_id,
            cooperative_id=cooperative_id,
            campaign=campaign
        )

        # Enrichir avec le nombre de réponses pour chaque formulaire
        for form in forms:
            try:
                form["responses_count"] = self.repository.count_responses_by_form(
                    form["uuid"]
                )
            except Exception:
                form["responses_count"] = 0

        return forms

    def get_form(self, form_id, owner_id=None):
        form = self.repository.get_form_by_id(form_id, owner_id)
        if not form:
            raise ValueError("Formulaire d'enquête introuvable")

        try:
            form["responses_count"] = self.repository.count_responses_by_form(
                form["uuid"]
            )
        except Exception:
            form["responses_count"] = 0

        return form

    def create_form(self, data, owner_id):
        if not data.get("title") or not str(data["title"]).strip():
            raise ValueError("Le titre du formulaire est obligatoire")

        if not data.get("cooperative_id"):
            raise ValueError("La coopérative est obligatoire")

        if not data.get("campaign") or not str(data["campaign"]).strip():
            raise ValueError("La campagne d'enquête est obligatoire")

        fields = data.get("fields")
        if not isinstance(fields, list):
            fields = []

        payload = {
            "title": str(data["title"]).strip(),
            "description": str(data.get("description") or "").strip() or None,
            "campaign": str(data["campaign"]).strip(),
            "cooperative_id": data["cooperative_id"],
            "version": int(data.get("version", 1)),
            "status": data.get("status", "published"),
            "fields": fields,
            "owner": owner_id,
        }

        return self.repository.create_form(payload)

    def update_form(self, form_id, data, owner_id):
        existing = self.repository.get_form_by_id(form_id, owner_id)
        if not existing:
            raise ValueError("Formulaire introuvable ou non autorisé")

        payload = {}

        if "title" in data:
            if not str(data["title"]).strip():
                raise ValueError("Le titre du formulaire ne peut pas être vide")
            payload["title"] = str(data["title"]).strip()

        if "description" in data:
            payload["description"] = str(data["description"] or "").strip() or None

        if "campaign" in data:
            if not str(data["campaign"]).strip():
                raise ValueError("La campagne ne peut pas être vide")
            payload["campaign"] = str(data["campaign"]).strip()

        if "cooperative_id" in data:
            payload["cooperative_id"] = data["cooperative_id"]

        if "status" in data:
            if data["status"] not in ("draft", "published", "archived"):
                raise ValueError("Statut de formulaire invalide")
            payload["status"] = data["status"]

        if "fields" in data:
            fields = data["fields"]
            if not isinstance(fields, list):
                raise ValueError("Les champs du formulaire doivent être une liste")
            payload["fields"] = fields

            # Gestion des versions : si le formulaire a déjà des réponses,
            # on incrémente automatiquement le numéro de version
            responses_count = self.repository.count_responses_by_form(form_id)
            if responses_count > 0:
                payload["version"] = int(existing.get("version", 1)) + 1

        return self.repository.update_form(form_id, owner_id, payload)

    def delete_form(self, form_id, owner_id):
        existing = self.repository.get_form_by_id(form_id, owner_id)
        if not existing:
            raise ValueError("Formulaire introuvable ou non autorisé")

        return self.repository.delete_form(form_id, owner_id)

    # ============================================================
    # RÉPONSES
    # ============================================================

    def get_responses(self, form_id):
        return self.repository.get_responses_by_form(form_id)

    def get_response(self, response_id):
        response = self.repository.get_response_by_id(response_id)
        if not response:
            raise ValueError("Réponse d'enquête introuvable")
        return response

    def create_response(self, form_id, data, user_id):
        form = self.repository.get_form_by_id(form_id)
        if not form:
            raise ValueError("Formulaire d'enquête introuvable")

        if form.get("status") != "published":
            raise ValueError("Ce formulaire n'est pas ouvert aux réponses (non publié)")

        answers = data.get("answers", {})
        if not isinstance(answers, dict):
            raise ValueError("Les réponses doivent être un dictionnaire")

        # Validation des champs obligatoires
        fields = form.get("fields") or []
        for field in fields:
            field_id = field.get("id")
            field_label = field.get("label", "Champ")
            is_required = field.get("required", False)

            if is_required:
                ans = answers.get(field_id)
                if ans is None or (isinstance(ans, str) and not ans.strip()) or (isinstance(ans, list) and len(ans) == 0):
                    raise ValueError(f"Le champ '{field_label}' est obligatoire")

        payload = {
            "form_id": form_id,
            "form_version": int(form.get("version", 1)),
            "cooperative_id": form.get("cooperative_id"),
            "farmer_id": data.get("farmer_id") or None,
            "parcel_id": data.get("parcel_id") or None,
            "answers": answers,
            "latitude": float(data["latitude"]) if data.get("latitude") is not None else None,
            "longitude": float(data["longitude"]) if data.get("longitude") is not None else None,
            "submitted_by": user_id,
        }

        return self.repository.create_response(payload)

    def delete_response(self, response_id, user_id):
        return self.repository.delete_response(response_id, user_id)

    # ============================================================
    # EXPORT CSV
    # ============================================================

    def export_responses_csv(self, form_id):
        form = self.repository.get_form_by_id(form_id)
        if not form:
            raise ValueError("Formulaire introuvable")

        responses = self.repository.get_responses_by_form(form_id)
        fields = form.get("fields") or []

        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        # En-têtes CSV
        headers = [
            "ID Réponse",
            "Date soumission",
            "Version formulaire",
            "Agriculteur",
            "CIN Agriculteur",
            "Parcelle ID",
            "Latitude",
            "Longitude",
        ]

        # Ajouter chaque champ du formulaire comme colonne
        for field in fields:
            headers.append(field.get("label", field.get("id", "Champ")))

        writer.writerow(headers)

        # Lignes
        for resp in responses:
            farmer = resp.get("farmer") or {}
            answers = resp.get("answers") or {}

            row = [
                resp.get("uuid"),
                resp.get("created_at"),
                resp.get("form_version", 1),
                farmer.get("full_name", ""),
                farmer.get("id_card", ""),
                resp.get("parcel_id", ""),
                resp.get("latitude", ""),
                resp.get("longitude", ""),
            ]

            for field in fields:
                val = answers.get(field.get("id"))
                if isinstance(val, list):
                    val_str = ", ".join(str(v) for v in val)
                elif isinstance(val, dict):
                    val_str = str(val)
                elif val is None:
                    val_str = ""
                else:
                    val_str = str(val)
                row.append(val_str)

            writer.writerow(row)

        return output.getvalue()
