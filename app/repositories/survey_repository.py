class SurveyRepository:

    def __init__(self, supabase):
        self.supabase = supabase

    # ============================================================
    # FORMULAIRES D'ENQUÊTE
    # ============================================================

    def get_all_forms(self, owner_id, cooperative_id=None, campaign=None):
        query = (
            self.supabase
            .table("survey_forms")
            .select("""
                *,
                cooperative:cooperatives(
                    uuid,
                    name
                )
            """)
            .eq("owner", owner_id)
            .order("created_at", desc=True)
        )

        if cooperative_id:
            query = query.eq("cooperative_id", cooperative_id)

        if campaign:
            query = query.eq("campaign", campaign)

        response = query.execute()
        return response.data or []

    def get_form_by_id(self, form_id, owner_id=None):
        query = (
            self.supabase
            .table("survey_forms")
            .select("""
                *,
                cooperative:cooperatives(
                    uuid,
                    name
                )
            """)
            .eq("uuid", form_id)
        )

        if owner_id:
            query = query.eq("owner", owner_id)

        response = query.execute()
        return response.data[0] if response.data else None

    def create_form(self, data):
        response = (
            self.supabase
            .table("survey_forms")
            .insert(data)
            .execute()
        )
        return response.data[0] if response.data else None

    def update_form(self, form_id, owner_id, data):
        response = (
            self.supabase
            .table("survey_forms")
            .update(data)
            .eq("uuid", form_id)
            .eq("owner", owner_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def delete_form(self, form_id, owner_id):
        response = (
            self.supabase
            .table("survey_forms")
            .delete()
            .eq("uuid", form_id)
            .eq("owner", owner_id)
            .execute()
        )
        return response.data

    # ============================================================
    # RÉPONSES AUX ENQUÊTES
    # ============================================================

    def get_responses_by_form(self, form_id):
        response = (
            self.supabase
            .table("survey_responses")
            .select("""
                *,
                farmer:farmers(
                    uuid,
                    full_name,
                    id_card
                ),
                parcel:parcels(
                    uuid,
                    area_ha
                )
            """)
            .eq("form_id", form_id)
            .order("created_at", desc=True)
            .execute()
        )
        data = response.data or []
        if not data:
            return []

        # Récupération des profils des utilisateurs ayant soumis les réponses
        user_ids = list({r["submitted_by"] for r in data if r.get("submitted_by")})
        if user_ids:
            try:
                profiles_res = (
                    self.supabase
                    .table("user_profiles")
                    .select("id, first_name, last_name, role")
                    .in_("id", user_ids)
                    .execute()
                )
                profiles_map = {p["id"]: p for p in (profiles_res.data or [])}
                for r in data:
                    r["submitted_user"] = profiles_map.get(r.get("submitted_by"))
            except Exception:
                pass

        return data

    def get_response_by_id(self, response_id):
        response = (
            self.supabase
            .table("survey_responses")
            .select("""
                *,
                farmer:farmers(
                    uuid,
                    full_name,
                    id_card
                ),
                parcel:parcels(
                    uuid,
                    area_ha
                )
            """)
            .eq("uuid", response_id)
            .execute()
        )
        if not response.data:
            return None

        res_data = response.data[0]
        sub_id = res_data.get("submitted_by")
        if sub_id:
            try:
                prof_res = (
                    self.supabase
                    .table("user_profiles")
                    .select("id, first_name, last_name, role")
                    .eq("id", sub_id)
                    .execute()
                )
                if prof_res.data:
                    res_data["submitted_user"] = prof_res.data[0]
            except Exception:
                pass

        return res_data

    def count_responses_by_form(self, form_id):
        response = (
            self.supabase
            .table("survey_responses")
            .select("uuid", count="exact")
            .eq("form_id", form_id)
            .execute()
        )
        return response.count or len(response.data or [])

    def create_response(self, data):
        response = (
            self.supabase
            .table("survey_responses")
            .insert(data)
            .execute()
        )
        return response.data[0] if response.data else None

    def delete_response(self, response_id, user_id):
        response = (
            self.supabase
            .table("survey_responses")
            .delete()
            .eq("uuid", response_id)
            .execute()
        )
        return response.data
