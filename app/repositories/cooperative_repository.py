class CooperativeRepository:

    def __init__(self, supabase):
        self.supabase = supabase

    def get_all(self, owner_id=None):
        query = (
            self.supabase
            .table("cooperatives")
            .select("*")
            .order("created_at", desc=True)
        )
        if owner_id:
            query = query.eq("owner", owner_id)

        response = query.execute()
        return response.data

    def get_by_id(
        self,
        cooperative_id,
        owner_id=None
    ):
        query = (
            self.supabase
            .table("cooperatives")
            .select("*")
            .eq("uuid", cooperative_id)
        )
        if owner_id:
            query = query.eq("owner", owner_id)

        response = query.execute()
        return response.data

    def create(self, data):

        response = (
            self.supabase
            .table("cooperatives")
            .insert(data)
            .execute()
        )

        return response.data

    def update(
        self,
        cooperative_id,
        owner_id,
        data
    ):

        response = (
            self.supabase
            .table("cooperatives")
            .update(data)
            .eq("uuid", cooperative_id)
            .eq("owner", owner_id)
            .execute()
        )

        return response.data

    def delete(
        self,
        cooperative_id,
        owner_id
    ):

        response = (
            self.supabase
            .table("cooperatives")
            .delete()
            .eq("uuid", cooperative_id)
            .eq("owner", owner_id)
            .execute()
        )

        return response.data