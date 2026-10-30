from flask import Blueprint, jsonify, request, current_app

from app.services.fire_alert_service import FireAlertService
from app.utils.auth import get_authenticated_user


fire_alert_bp = Blueprint(
    "fire_alerts",
    __name__,
    url_prefix="/api/fire-alerts"
)


@fire_alert_bp.route("/generate", methods=["POST"])
def generate_alerts():

    user = get_authenticated_user()

    if not user:
        return jsonify({
            "error": "Utilisateur non authentifié"
        }), 401

    try:
        radius_km = float(
            request.args.get(
                "radius_km",
                5
            )
        )

        period = request.args.get(
            "period",
            "7d"
        ).lower()

        periods = {
            "24h": 24,
            "48h": 48,
            "7d": 168,
            "30d": 720,
        }

        if radius_km <= 0:
            return jsonify({
                "error": "Le rayon doit être supérieur à 0"
            }), 400

        if period not in periods:
            return jsonify({
                "error": (
                    "Période invalide. "
                    "Utilisez 24h, 48h ou 7d."
                )
            }), 400

        count = FireAlertService.create_alerts(
            radius_km=radius_km,
            period_hours=periods[period]
        )

        return jsonify({
            "success": True,
            "created": count,
            "radius_km": radius_km,
            "period": period
        }), 200

    except ValueError:
        return jsonify({
            "error": "radius_km doit être un nombre"
        }), 400

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@fire_alert_bp.route("", methods=["GET"])
def get_alerts():

    user = get_authenticated_user()

    if not user:
        return jsonify({
            "error": "Utilisateur non authentifié"
        }), 401

    try:
        alerts = FireAlertService.get_alerts()

        return jsonify({
            "success": True,
            "count": len(alerts),
            "data": alerts
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@fire_alert_bp.route("/<uuid:alert_id>/send", methods=["POST"])
def send_single_alert(alert_id):

    user = get_authenticated_user()

    if not user:
        return jsonify({
            "error": "Utilisateur non authentifié"
        }), 401

    try:
        body = request.get_json(silent=True) or {}
        recipient = body.get("recipient")
        alert_type = body.get("alert_type", "sms")
        message = body.get("message")

        result = FireAlertService.send_single_alert(
            alert_id=str(alert_id),
            recipient=recipient,
            alert_type=alert_type,
            message=message
        )

        return jsonify({
            "success": True,
            "message": "Alerte diffusée avec succès",
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 400


@fire_alert_bp.route("/send-all", methods=["POST"])
def send_all_alerts():

    user = get_authenticated_user()

    if not user:
        return jsonify({
            "error": "Utilisateur non authentifié"
        }), 401

    try:
        body = request.get_json(silent=True) or {}
        recipient = body.get("recipient")
        alert_type = body.get("alert_type", "sms")
        message = body.get("message")

        result = FireAlertService.send_all_pending(
            recipient=recipient,
            alert_type=alert_type,
            message=message
        )

        return jsonify({
            "success": True,
            "message": result.get("message", "Toutes les alertes ont été transmises"),
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@fire_alert_bp.route("/test-sms", methods=["POST"])
def test_sms():
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Utilisateur non authentifié"}), 401

    try:
        from app.services.sms_service import SmsService

        body = request.get_json(silent=True) or {}
        phone = body.get("phone") or body.get("recipient")
        if not phone:
            return jsonify({"error": "Numéro de téléphone requis (ex: 0341234567)"}), 400

        msg = body.get("message") or "Test SmartSahaBio via passerelle SMS mapi.mg : connexion opérationnelle !"
        res = SmsService.send_sms(recipient=phone, message=msg)

        return jsonify({
            "success": res.get("success", False),
            "data": res
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400