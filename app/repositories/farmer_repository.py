class FarmerRepository:

    def __init__(self, supabase):
        self.supabase = supabase

    def get_all(self, cooperative_id):
        try:
            response = (
                self.supabase
                .table("farmers")
                .select("""
                    *,
                    cooperative:cooperatives(
                        uuid,
                        name
                    )
                """)
                .eq("cooperative_id", cooperative_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data
        except Exception:
            response = (
                self.supabase
                .table("farmers")
                .select("*")
                .eq("cooperative_id", cooperative_id)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data

    def get_all_by_owner(self, owner_id=None):
        if owner_id is None:
            try:
                response = (
                    self.supabase
                    .table("farmers")
                    .select("""
                        *,
                        cooperative:cooperatives(
                            uuid,
                            name
                        )
                    """)
                    .order("created_at", desc=True)
                    .execute()
                )
                return response.data or []
            except Exception:
                response = self.supabase.table("farmers").select("*").order("created_at", desc=True).execute()
                return response.data or []

        try:
            response = (
                self.supabase
                .table("farmers")
                .select("""
                    *,
                    cooperative:cooperatives(
                        uuid,
                        name
                    )
                """)
                .eq("owner", owner_id)
                .order("created_at", desc=True)
                .execute()
            )
            if response.data:
                return response.data
        except Exception:
            pass

        try:
            coops = (
                self.supabase
                .table("cooperatives")
                .select("uuid")
                .eq("owner", owner_id)
                .execute()
            )
            if coops.data:
                coop_ids = [c["uuid"] for c in coops.data]
                response = (
                    self.supabase
                    .table("farmers")
                    .select("""
                        *,
                        cooperative:cooperatives(
                            uuid,
                            name
                        )
                    """)
                    .in_("cooperative_id", coop_ids)
                    .order("created_at", desc=True)
                    .execute()
                )
                return response.data or []
        except Exception:
            pass

        return []

    def get_by_id(
        self,
        farmer_id,
        cooperative_id
    ):

        response = (
            self.supabase
            .table("farmers")
            .select("*")
            .eq("uuid", farmer_id)
            .eq("cooperative_id", cooperative_id)
            .execute()
        )

        return response.data

    def create(self, data):

        response = (
            self.supabase
            .table("farmers")
            .insert(data)
            .execute()
        )

        return response.data

    def update(
        self,
        farmer_id,
        cooperative_id,
        data
    ):

        response = (
            self.supabase
            .table("farmers")
            .update(data)
            .eq("uuid", farmer_id)
            .eq("cooperative_id", cooperative_id)
            .execute()
        )

        return response.data

    def delete(
        self,
        farmer_id,
        cooperative_id
    ):

        response = (
            self.supabase
            .table("farmers")
            .delete()
            .eq("uuid", farmer_id)
            .eq("cooperative_id", cooperative_id)
            .execute()
        )

        return response.data