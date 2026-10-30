from flask import current_app


class FireRepository:

    @staticmethod
    def insert_detection(data):
        supabase = current_app.supabase

        response = supabase.rpc(
            "insert_fire_detection",
            data
        ).execute()

        return response.data

    @staticmethod
    def get_nearby_parcels(
        radius_m=5000,
        period_hours=168
    ):
        supabase = current_app.supabase

        response = supabase.rpc(
            "get_nearby_fire_parcels",
            {
                "p_radius_m": radius_m,
                "p_period_hours": period_hours,
            }
        ).execute()

        return response.data