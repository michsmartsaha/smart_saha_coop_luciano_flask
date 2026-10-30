from app.repositories.fire_alert_repository import FireAlertRepository
from app.services.sms_service import SmsService


class FireAlertService:

    @staticmethod
    def create_alerts(
        radius_km=5,
        period_hours=168
    ):
        radius_m = radius_km * 1000

        return FireAlertRepository.create_alerts(
            radius_m=radius_m,
            period_hours=period_hours
        )

    @staticmethod
    def get_alerts():
        return FireAlertRepository.get_alerts()

    @staticmethod
    def send_single_alert(alert_id: str, recipient: str = None, alert_type: str = "sms", message: str = None):
        """
        Envoie une alerte incendie spécifique à un agriculteur, par SMS via sms.mg ou autre canal.
        """
        alert = FireAlertRepository.get_alert_by_id(alert_id)
        if not alert:
            raise ValueError("Alerte incendie introuvable.")

        channel = alert_type or alert.get("alert_type") or "sms"

        if channel == "sms":
            # Recherche automatique du numéro de l'agriculteur
            target_phone = recipient
            parcel = alert.get("parcels") or {}
            farmer = parcel.get("farmers") or {}
            farmer_name = farmer.get("full_name") or "Agriculteur"
            parcel_name = parcel.get("name") or "Parcelle"
            distance_m = alert.get("distance_m")

            if not target_phone:
                target_phone = alert.get("recipient") or farmer.get("phone")

            if not target_phone:
                raise ValueError(
                    f"Aucun numéro de téléphone pour l'agriculteur ({farmer_name}). "
                    f"Veuillez renseigner le téléphone dans sa fiche ou le saisir manuellement."
                )

            sms_content = message or SmsService.format_fire_alert_sms(
                farmer_name=farmer_name,
                parcel_name=parcel_name,
                distance_m=distance_m,
            )

            sms_res = SmsService.send_sms(target_phone, sms_content)

            if sms_res.get("success"):
                FireAlertRepository.mark_as_sent(
                    alert_id=alert_id,
                    recipient=target_phone,
                    alert_type="sms"
                )
                return {
                    "success": True,
                    "channel": "sms",
                    "recipient": target_phone,
                    "farmer_name": farmer_name,
                    "simulated": sms_res.get("simulated", False),
                    "message_id": sms_res.get("message_id"),
                    "message": "SMS d'alerte incendie envoyé avec succès."
                }
            else:
                err_msg = sms_res.get("error") or "Échec de l'envoi du SMS via mapi.mg"
                FireAlertRepository.mark_as_sent(
                    alert_id=alert_id,
                    recipient=target_phone,
                    alert_type="sms",
                    error_message=err_msg
                )
                raise RuntimeError(f"Erreur passerelle SMS mapi.mg : {err_msg}")

        # Pour les canaux traditionnels (notification push / système)
        result = FireAlertRepository.mark_as_sent(
            alert_id=alert_id,
            recipient=recipient,
            alert_type=channel
        )
        return {
            "success": True,
            "channel": channel,
            "data": result
        }

    @staticmethod
    def send_all_pending(recipient: str = None, alert_type: str = "sms", message: str = None):
        """
        Envoie TOUTES les alertes incendie en attente aux agriculteurs concernés par SMS via mapi.mg.
        """
        channel = alert_type or "sms"

        if channel == "sms":
            pending = FireAlertRepository.get_pending_alerts()
            if not pending:
                return {
                    "success": True,
                    "total": 0,
                    "sent": 0,
                    "failed": 0,
                    "message": "Aucune alerte incendie en attente."
                }

            sent_count = 0
            failed_count = 0
            details = []

            for alert in pending:
                a_id = alert.get("uuid")
                parcel = alert.get("parcels") or {}
                farmer = parcel.get("farmers") or {}
                farmer_name = farmer.get("full_name") or "Agriculteur"
                parcel_name = parcel.get("name") or "Parcelle"
                distance_m = alert.get("distance_m")

                target_phone = recipient or alert.get("recipient") or farmer.get("phone")

                if not target_phone:
                    failed_count += 1
                    details.append({
                        "alert_id": a_id,
                        "farmer_name": farmer_name,
                        "success": False,
                        "error": "Numéro de téléphone non renseigné"
                    })
                    continue

                sms_content = message or SmsService.format_fire_alert_sms(
                    farmer_name=farmer_name,
                    parcel_name=parcel_name,
                    distance_m=distance_m,
                )

                sms_res = SmsService.send_sms(target_phone, sms_content)

                if sms_res.get("success"):
                    sent_count += 1
                    FireAlertRepository.mark_as_sent(
                        alert_id=a_id,
                        recipient=target_phone,
                        alert_type="sms"
                    )
                    details.append({
                        "alert_id": a_id,
                        "farmer_name": farmer_name,
                        "recipient": target_phone,
                        "success": True,
                        "simulated": sms_res.get("simulated", False)
                    })
                else:
                    failed_count += 1
                    FireAlertRepository.mark_as_sent(
                        alert_id=a_id,
                        recipient=target_phone,
                        alert_type="sms",
                        error_message=sms_res.get("error")
                    )
                    details.append({
                        "alert_id": a_id,
                        "farmer_name": farmer_name,
                        "recipient": target_phone,
                        "success": False,
                        "error": sms_res.get("error")
                    })

            return {
                "success": True,
                "total": len(pending),
                "sent": sent_count,
                "failed": failed_count,
                "details": details,
                "message": f"{sent_count} alerte(s) SMS envoyée(s) sur {len(pending)} en attente."
            }

        # Pour les autres canaux
        result = FireAlertRepository.send_all_pending(recipient, channel)
        return {
            "success": True,
            "channel": channel,
            "data": result,
            "message": "Toutes les alertes ont été transmises."
        }

    # Alias pour compatibilité
    @staticmethod
    def mark_as_sent(alert_id, recipient=None, alert_type="sms", message=None):
        return FireAlertService.send_single_alert(alert_id, recipient, alert_type, message)