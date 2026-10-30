from datetime import datetime, timezone
from flask import current_app


class FireAlertRepository:

    @staticmethod
    def create_alerts(
        radius_m=5000,
        period_hours=168
    ):
        supabase = current_app.supabase

        response = supabase.rpc(
            "create_fire_alerts",
            {
                "p_radius_m": radius_m,
                "p_period_hours": period_hours,
            }
        ).execute()

        return response.data

    @staticmethod
    def get_alerts():
        supabase = current_app.supabase

        try:
            response = (
                supabase
                .table("fire_alerts")
                .select("""
                    *,
                    parcels(
                        uuid,
                        name,
                        area_ha,
                        cooperative_id,
                        farmer_id,
                        farmers(
                            uuid,
                            full_name,
                            phone
                        )
                    ),
                    fire_detections(
                        latitude,
                        longitude,
                        detected_at,
                        frp,
                        confidence,
                        satellite
                    )
                """)
                .order("created_at", desc=True)
                .execute()
            )
            return response.data
        except Exception as e:
            print("⚠️ Erreur sélection enrichie fire_alerts, repli sur select simple :", e)
            try:
                response = (
                    supabase
                    .table("fire_alerts")
                    .select("*, parcels(uuid, name, area_ha, cooperative_id), fire_detections(latitude, longitude, detected_at, frp, confidence, satellite)")
                    .order("created_at", desc=True)
                    .execute()
                )
                return response.data
            except Exception:
                response = (
                    supabase
                    .table("fire_alerts")
                    .select("*")
                    .order("created_at", desc=True)
                    .execute()
                )
                return response.data

    @staticmethod
    def get_alert_by_id(alert_id: str):
        supabase = current_app.supabase
        try:
            response = (
                supabase
                .table("fire_alerts")
                .select("""
                    *,
                    parcels(
                        uuid,
                        name,
                        area_ha,
                        cooperative_id,
                        farmer_id,
                        farmers(
                            uuid,
                            full_name,
                            phone
                        )
                    ),
                    fire_detections(
                        latitude,
                        longitude,
                        detected_at,
                        frp,
                        confidence,
                        satellite
                    )
                """)
                .eq("uuid", alert_id)
                .single()
                .execute()
            )
            return response.data
        except Exception:
            response = (
                supabase
                .table("fire_alerts")
                .select("*")
                .eq("uuid", alert_id)
                .single()
                .execute()
            )
            return response.data

    @staticmethod
    def get_pending_alerts():
        supabase = current_app.supabase
        try:
            response = (
                supabase
                .table("fire_alerts")
                .select("""
                    *,
                    parcels(
                        uuid,
                        name,
                        area_ha,
                        cooperative_id,
                        farmer_id,
                        farmers(
                            uuid,
                            full_name,
                            phone
                        )
                    ),
                    fire_detections(
                        latitude,
                        longitude,
                        detected_at,
                        frp,
                        confidence,
                        satellite
                    )
                """)
                .eq("status", "pending")
                .execute()
            )
            return response.data or []
        except Exception:
            response = (
                supabase
                .table("fire_alerts")
                .select("*")
                .eq("status", "pending")
                .execute()
            )
            return response.data or []

    @staticmethod
    def mark_as_sent(alert_id, recipient=None, alert_type="sms", error_message=None):
        supabase = current_app.supabase
        payload = {
            "status": "sent" if not error_message else "failed",
            "sent_at": datetime.now(timezone.utc).isoformat()
        }
        if recipient:
            payload["recipient"] = recipient
        if alert_type in ("email", "notification", "sms"):
            payload["alert_type"] = alert_type
        if error_message:
            payload["error_message"] = error_message

        response = (
            supabase
            .table("fire_alerts")
            .update(payload)
            .eq("uuid", alert_id)
            .execute()
        )
        return response.data

    @staticmethod
    def send_all_pending(recipient=None, alert_type="sms"):
        supabase = current_app.supabase
        payload = {
            "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat()
        }
        if recipient:
            payload["recipient"] = recipient
        if alert_type in ("email", "notification", "sms"):
            payload["alert_type"] = alert_type

        response = (
            supabase
            .table("fire_alerts")
            .update(payload)
            .eq("status", "pending")
            .execute()
        )
        return response.data