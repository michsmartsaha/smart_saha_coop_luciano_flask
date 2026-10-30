from typing import Optional, Dict, Any, List

from app.repositories.audit_repository import AuditRepository


class AuditService:
    """
    Service métier pour la gestion des audits biologiques.
    """

    # Valeurs autorisées
    CONVERSION_STATUSES = {
        "not_started",
        "in_conversion",
        "certified",
    }

    CONTAMINATION_RISKS = {
        "low",
        "medium",
        "high",
    }

    NON_CONFORMITY_SEVERITIES = {
        "none",
        "minor",
        "major",
        "critical",
    }

    OVERALL_STATUSES = {
        "compliant",
        "non_compliant",
        "compliant_with_reservations",
    }

    def __init__(self, supabase):
        self.repository = AuditRepository(supabase)

    # =========================================================================
    # VALIDATION COMMUNE
    # =========================================================================

    def _validate_audit_data(
        self,
        data: Dict[str, Any],
        is_update: bool = False
    ) -> Dict[str, Any]:

        if not isinstance(data, dict):
            raise ValueError("Les données de l'audit doivent être un objet JSON.")
        cleaned = {}

        if not is_update or "parcel_id" in data:
            parcel_id = data.get("parcel_id")
            if not parcel_id:
                raise ValueError("La parcelle est obligatoire.")
            if not isinstance(parcel_id, str):
                raise ValueError("parcel_id doit être une chaîne de caractères.")

            cleaned["parcel_id"] = parcel_id

        if not is_update or "auditor_name" in data:
            auditor_name = data.get("auditor_name")

            if not auditor_name or not str(auditor_name).strip():
                raise ValueError("Le nom de l'auditeur est obligatoire.")

            cleaned["auditor_name"] = str(auditor_name).strip()

        if "audit_date" in data:
            audit_date = data.get("audit_date")
            if audit_date:
                cleaned["audit_date"] = audit_date

        if "conversion_start_date" in data:
            conversion_start_date = data.get("conversion_start_date")

            if conversion_start_date:
                cleaned["conversion_start_date"] = conversion_start_date
            else:
                cleaned["conversion_start_date"] = None

        if "conversion_status" in data:
            conversion_status = data.get("conversion_status")

            if conversion_status not in self.CONVERSION_STATUSES:
                raise ValueError(
                    "Statut de conversion invalide. "
                    "Valeurs autorisées : "
                    "not_started, in_conversion, certified."
                )

            cleaned["conversion_status"] = conversion_status

        elif not is_update:
            cleaned["conversion_status"] = "not_started"

        # ---------------------------------------------------------------------
        # inputs_used
        # ---------------------------------------------------------------------

        if "inputs_used" in data:
            cleaned["inputs_used"] = self._clean_optional_text(
                data.get("inputs_used")
            )

        # ---------------------------------------------------------------------
        # seed_origin
        # ---------------------------------------------------------------------

        if "seed_origin" in data:
            cleaned["seed_origin"] = self._clean_optional_text(
                data.get("seed_origin")
            )

        # ---------------------------------------------------------------------
        # pest_management_method
        # ---------------------------------------------------------------------

        if "pest_management_method" in data:
            cleaned["pest_management_method"] = self._clean_optional_text(
                data.get("pest_management_method")
            )

        # ---------------------------------------------------------------------
        # neighboring_crops
        # ---------------------------------------------------------------------

        if "neighboring_crops" in data:
            cleaned["neighboring_crops"] = self._clean_optional_text(
                data.get("neighboring_crops")
            )

        # ---------------------------------------------------------------------
        # buffer_zone_distance_m
        # ---------------------------------------------------------------------

        if "buffer_zone_distance_m" in data:
            value = data.get("buffer_zone_distance_m")

            if value is not None and value != "":
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    raise ValueError(
                        "La distance de la zone tampon doit être un nombre."
                    )

                if value < 0:
                    raise ValueError(
                        "La distance de la zone tampon ne peut pas être négative."
                    )

                cleaned["buffer_zone_distance_m"] = value
            else:
                cleaned["buffer_zone_distance_m"] = None

        # ---------------------------------------------------------------------
        # contamination_risk
        # ---------------------------------------------------------------------

        if "contamination_risk" in data:
            contamination_risk = data.get("contamination_risk")

            if contamination_risk not in self.CONTAMINATION_RISKS:
                raise ValueError(
                    "Niveau de risque de contamination invalide. "
                    "Valeurs autorisées : low, medium, high."
                )

            cleaned["contamination_risk"] = contamination_risk

        elif not is_update:
            cleaned["contamination_risk"] = "low"

        # ---------------------------------------------------------------------
        # REGISTRES
        # ---------------------------------------------------------------------

        boolean_fields = [
            "parcel_register_kept",
            "inputs_register_kept",
            "harvest_register_kept",
            "sales_register_kept",
        ]

        for field in boolean_fields:
            if field in data:
                value = data.get(field)

                if not isinstance(value, bool):
                    raise ValueError(
                        f"{field} doit être true ou false."
                    )

                cleaned[field] = value

        # ---------------------------------------------------------------------
        # bio_nonbio_separation
        # ---------------------------------------------------------------------

        if "bio_nonbio_separation" in data:
            cleaned["bio_nonbio_separation"] = self._clean_optional_text(
                data.get("bio_nonbio_separation")
            )

        # ---------------------------------------------------------------------
        # storage_handling_notes
        # ---------------------------------------------------------------------

        if "storage_handling_notes" in data:
            cleaned["storage_handling_notes"] = self._clean_optional_text(
                data.get("storage_handling_notes")
            )

        # ---------------------------------------------------------------------
        # non_conformities
        # ---------------------------------------------------------------------

        if "non_conformities" in data:
            cleaned["non_conformities"] = self._clean_optional_text(
                data.get("non_conformities")
            )

        # ---------------------------------------------------------------------
        # non_conformity_severity
        # ---------------------------------------------------------------------

        if "non_conformity_severity" in data:
            severity = data.get("non_conformity_severity")

            if severity not in self.NON_CONFORMITY_SEVERITIES:
                raise ValueError(
                    "Niveau de non-conformité invalide. "
                    "Valeurs autorisées : "
                    "none, minor, major, critical."
                )

            cleaned["non_conformity_severity"] = severity

        elif not is_update:
            cleaned["non_conformity_severity"] = "none"

        # ---------------------------------------------------------------------
        # corrective_action_plan
        # ---------------------------------------------------------------------

        if "corrective_action_plan" in data:
            cleaned["corrective_action_plan"] = self._clean_optional_text(
                data.get("corrective_action_plan")
            )

        # ---------------------------------------------------------------------
        # corrective_action_deadline
        # ---------------------------------------------------------------------

        if "corrective_action_deadline" in data:
            deadline = data.get("corrective_action_deadline")

            if deadline:
                cleaned["corrective_action_deadline"] = deadline
            else:
                cleaned["corrective_action_deadline"] = None

        # ---------------------------------------------------------------------
        # overall_status
        # ---------------------------------------------------------------------

        if "overall_status" in data:
            overall_status = data.get("overall_status")

            if overall_status not in self.OVERALL_STATUSES:
                raise ValueError(
                    "Statut global invalide. "
                    "Valeurs autorisées : "
                    "compliant, non_compliant, "
                    "compliant_with_reservations."
                )

            cleaned["overall_status"] = overall_status

        elif not is_update:
            cleaned["overall_status"] = "compliant"

        # ---------------------------------------------------------------------
        # auditor_signature
        # ---------------------------------------------------------------------

        if "auditor_signature" in data:
            signature = data.get("auditor_signature")

            if signature is not None and not isinstance(signature, str):
                raise ValueError(
                    "La signature de l'auditeur doit être une chaîne."
                )

            cleaned["auditor_signature"] = signature

        return cleaned

    # =========================================================================
    # UTILITAIRE
    # =========================================================================

    @staticmethod
    def _clean_optional_text(value: Any) -> Optional[str]:
        """
        Nettoie un champ texte optionnel.
        """

        if value is None:
            return None

        value = str(value).strip()

        return value if value else None

    # =========================================================================
    # LISTE
    # =========================================================================

    def get_all_audits(
        self,
        owner_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retourne tous les audits. Si owner_id est None (auditeur bio), retourne tous les audits du système.
        """
        return self.repository.get_all(owner_id)

    # =========================================================================
    # DETAIL
    # =========================================================================

    def get_audit(
        self,
        audit_id: str,
        owner_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retourne un audit précis.
        """
        if not audit_id:
            raise ValueError("Identifiant de l'audit manquant.")

        return self.repository.get_by_id(
            audit_id,
            owner_id
        )

    # =========================================================================
    # CREATION
    # =========================================================================

    def create_audit(
        self,
        data: Dict[str, Any],
        owner_id: str
    ) -> Dict[str, Any]:
        """
        Crée un nouvel audit.
        """

        if not owner_id:
            raise ValueError("Utilisateur non identifié.")

        cleaned_data = self._validate_audit_data(
            data,
            is_update=False
        )

        # Règle métier : une parcelle a un audit maximum
        existing_audit = self.repository.find_by_parcel_id(cleaned_data["parcel_id"])
        if existing_audit:
            raise ValueError(
                "Cette parcelle fait déjà l'objet d'un audit biologique. "
                "Une parcelle ne peut avoir qu'un seul audit."
            )

        # L'utilisateur connecté devient automatiquement propriétaire
        cleaned_data["owner"] = owner_id

        return self.repository.create(cleaned_data)

    # =========================================================================
    # MODIFICATION
    # =========================================================================

    def update_audit(
        self,
        audit_id: str,
        data: Dict[str, Any],
        owner_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Modifie un audit existant.
        """

        if not audit_id:
            raise ValueError("Identifiant de l'audit manquant.")

        cleaned_data = self._validate_audit_data(
            data,
            is_update=True
        )

        # Règle métier : si la parcelle est modifiée, vérifier qu'elle n'est pas déjà auditée
        if "parcel_id" in cleaned_data:
            existing_audit = self.repository.find_by_parcel_id(cleaned_data["parcel_id"])
            if existing_audit and str(existing_audit.get("uuid")) != str(audit_id):
                raise ValueError(
                    "Cette parcelle fait déjà l'objet d'un audit biologique. "
                    "Une parcelle ne peut avoir qu'un seul audit."
                )

        # Ne jamais permettre au client de modifier le propriétaire
        cleaned_data.pop("owner", None)

        return self.repository.update(
            audit_id,
            owner_id,
            cleaned_data
        )

    # =========================================================================
    # SUPPRESSION
    # =========================================================================

    def delete_audit(
        self,
        audit_id: str,
        owner_id: Optional[str] = None
    ) -> bool:
        """
        Supprime un audit.
        """

        if not audit_id:
            raise ValueError("Identifiant de l'audit manquant.")

        return self.repository.delete(
            audit_id,
            owner_id
        )