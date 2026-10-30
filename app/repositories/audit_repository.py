from typing import Optional, Dict, Any, List


class AuditRepository:
    """
    Repository chargé de communiquer avec la table public.audits_bio
    dans Supabase.
    """

    def __init__(self, supabase):
        self.supabase = supabase
        self.table = "audits_bio"

    # -------------------------------------------------------------------------
    # GET ALL
    # -------------------------------------------------------------------------

    def get_all(self, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Récupère tous les audits avec les informations de la parcelle associée.
        Si owner_id est None (auditeur bio), récupère tous les audits.
        """
        try:
            query = self.supabase.table(self.table).select("""
                *,
                parcel:parcels(
                    uuid,
                    name,
                    area_ha
                )
            """).order("created_at", desc=True)
            if owner_id:
                query = query.eq("owner", owner_id)

            response = query.execute()
            audits = response.data or []
        except Exception:
            query = self.supabase.table(self.table).select("*").order("created_at", desc=True)
            if owner_id:
                query = query.eq("owner", owner_id)
            response = query.execute()
            audits = response.data or []

        for a in audits:
            p = a.get("parcel")
            if isinstance(p, dict):
                a["parcel_name"] = p.get("name")

        return audits

    # -------------------------------------------------------------------------
    # GET BY ID
    # -------------------------------------------------------------------------

    def get_by_id(
        self,
        audit_id: str,
        owner_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Récupère un audit précis avec les informations de la parcelle associée.
        """
        try:
            query = self.supabase.table(self.table).select("""
                *,
                parcel:parcels(
                    uuid,
                    name,
                    area_ha
                )
            """).eq("uuid", audit_id)
            if owner_id:
                query = query.eq("owner", owner_id)

            response = query.maybe_single().execute()
            data = response.data
        except Exception:
            query = self.supabase.table(self.table).select("*").eq("uuid", audit_id)
            if owner_id:
                query = query.eq("owner", owner_id)
            response = query.maybe_single().execute()
            data = response.data

        if data and isinstance(data, dict):
            p = data.get("parcel")
            if isinstance(p, dict):
                data["parcel_name"] = p.get("name")

        return data

    # -------------------------------------------------------------------------
    # CREATE
    # -------------------------------------------------------------------------

    def create(
        self,
        audit_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Crée un nouvel audit.
        """

        response = (
            self.supabase
            .table(self.table)
            .insert(audit_data)
            .execute()
        )

        if not response.data:
            raise Exception("Impossible de créer l'audit.")

        return response.data[0]

    # -------------------------------------------------------------------------
    # UPDATE
    # -------------------------------------------------------------------------

    def update(
        self,
        audit_id: str,
        owner_id: Optional[str],
        audit_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Modifie un audit. Si owner_id est None (auditeur bio), modifie sans filtrer par propriétaire.
        """

        query = (
            self.supabase
            .table(self.table)
            .update(audit_data)
            .eq("uuid", audit_id)
        )

        if owner_id:
            query = query.eq("owner", owner_id)

        response = query.execute()

        if not response.data:
            return None

        return response.data[0]

    # -------------------------------------------------------------------------
    # FIND BY PARCEL ID
    # -------------------------------------------------------------------------

    def find_by_parcel_id(
        self,
        parcel_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Recherche s'il existe déjà un audit associé à cette parcelle.
        """
        response = (
            self.supabase
            .table(self.table)
            .select("uuid, parcel_id, auditor_name, audit_date")
            .eq("parcel_id", parcel_id)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    # -------------------------------------------------------------------------
    # DELETE
    # -------------------------------------------------------------------------

    def delete(
        self,
        audit_id: str,
        owner_id: Optional[str]
    ) -> bool:
        """
        Supprime un audit. Si owner_id est None (auditeur bio), supprime sans filtrer par propriétaire.
        """

        query = (
            self.supabase
            .table(self.table)
            .delete()
            .eq("uuid", audit_id)
        )

        if owner_id:
            query = query.eq("owner", owner_id)

        response = query.execute()

        return bool(response.data)