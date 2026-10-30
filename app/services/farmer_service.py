class FarmerService:

    @staticmethod
    def clean_phone(phone_str):
        if not phone_str:
            return None
        cleaned = "".join(c for c in str(phone_str).strip() if c.isdigit() or c == "+")
        if not cleaned:
            return None
        # Format malgache standard : 034... (10 chiffres) ou +26134... (12 caractères)
        if cleaned.startswith("+261"):
            return cleaned
        if cleaned.startswith("261") and len(cleaned) == 12:
            return f"+{cleaned}"
        if cleaned.startswith("0") and len(cleaned) == 10:
            return cleaned
        if len(cleaned) == 9 and cleaned.startswith("3"):
            return f"0{cleaned}"
        return cleaned

    def __init__(self, repository):
        self.repository = repository

    def get_all_farmers(self, cooperative_id):
        return self.repository.get_all(
            cooperative_id
        )

    def get_all_farmers_by_owner(self, owner_id):
        return self.repository.get_all_by_owner(
            owner_id
        )

    def get_farmer(
        self,
        farmer_id,
        cooperative_id
    ):
        return self.repository.get_by_id(
            farmer_id,
            cooperative_id
        )

    def create_farmer(
        self,
        data,
        cooperative_id,
        owner_id
    ):

        if not data.get("full_name"):
            raise ValueError(
                "Le nom complet de l'agriculteur est obligatoire"
            )

        from datetime import date
        current_year = date.today().year
        min_year = current_year - 100
        max_year = current_year - 10

        try:
            year = int(data.get("year_of_birth"))
            if year < min_year or year > max_year:
                raise ValueError(
                    f"L'année de naissance doit être comprise entre {min_year} et {max_year}"
                )
            data["year_of_birth"] = year
        except (TypeError, ValueError) as e:
            raise ValueError(
                str(e) if "comprise entre" in str(e) else "L'année de naissance doit être un nombre valide à 4 chiffres"
            )

        if not data.get("gender"):
            raise ValueError(
                "Le sexe est obligatoire"
            )

        id_card = str(data.get("id_card") or "").strip()
        if not id_card or not id_card.isdigit() or len(id_card) != 12:
            raise ValueError(
                "Le numéro de CIN doit comporter exactement 12 chiffres"
            )
        data["id_card"] = id_card

        if "phone" in data:
            data["phone"] = self.clean_phone(data.get("phone"))

        if not data.get("marital_status"):
            raise ValueError(
                "La situation matrimoniale est obligatoire"
            )

        try:
            household = int(data.get("household_number"))
            if household < 1:
                raise ValueError(
                    "Le nombre de personnes dans le ménage doit être supérieur ou égal à 1"
                )
            data["household_number"] = household
        except (TypeError, ValueError) as e:
            raise ValueError(
                str(e) if "supérieur ou égal à 1" in str(e) else "Le nombre de personnes dans le ménage doit être un nombre valide"
            )

        if not data.get("status"):
            raise ValueError(
                "Le statut de l'agriculteur est obligatoire"
            )

        # La coopérative vient de l'URL,
        # pas des données envoyées par le client.
        data["cooperative_id"] = cooperative_id

        # L'utilisateur connecté devient automatiquement
        # propriétaire de l'enregistrement.
        data["owner"] = owner_id

        return self.repository.create(data)

    def update_farmer(
        self,
        farmer_id,
        cooperative_id,
        data
    ):

        if not data:
            raise ValueError(
                "Aucune donnée à modifier"
            )

        if "year_of_birth" in data:
            from datetime import date
            current_year = date.today().year
            min_year = current_year - 100
            max_year = current_year - 10
            try:
                year = int(data["year_of_birth"])
                if year < min_year or year > max_year:
                    raise ValueError(
                        f"L'année de naissance doit être comprise entre {min_year} et {max_year}"
                    )
                data["year_of_birth"] = year
            except (TypeError, ValueError) as e:
                raise ValueError(
                    str(e) if "comprise entre" in str(e) else "L'année de naissance doit être un nombre valide à 4 chiffres"
                )

        if "id_card" in data:
            id_card = str(data["id_card"] or "").strip()
            if not id_card or not id_card.isdigit() or len(id_card) != 12:
                raise ValueError(
                    "Le numéro de CIN doit comporter exactement 12 chiffres"
                )
            data["id_card"] = id_card

        if "household_number" in data:
            try:
                household = int(data["household_number"])
                if household < 1:
                    raise ValueError(
                        "Le nombre de personnes dans le ménage doit être supérieur ou égal à 1"
                    )
                data["household_number"] = household
            except (TypeError, ValueError) as e:
                raise ValueError(
                    str(e) if "supérieur ou égal à 1" in str(e) else "Le nombre de personnes dans le ménage doit être un nombre valide"
                )

        if "phone" in data:
            data["phone"] = self.clean_phone(data.get("phone"))

        # Ces champs ne doivent jamais être
        # modifiés par le client.
        data.pop("uuid", None)
        data.pop("cooperative_id", None)
        data.pop("owner", None)
        data.pop("created_at", None)

        return self.repository.update(
            farmer_id,
            cooperative_id,
            data
        )

    def delete_farmer(
        self,
        farmer_id,
        cooperative_id
    ):
        return self.repository.delete(
            farmer_id,
            cooperative_id
        )