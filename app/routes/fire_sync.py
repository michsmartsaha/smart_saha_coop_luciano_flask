from flask import Blueprint, jsonify, current_app, request

from app.services.fire_sync_service import FireSyncService
from app.utils.auth import get_authenticated_user


fire_sync_bp = Blueprint(
    "fire_sync",
    __name__,
    url_prefix="/api/fire-sync"
)


@fire_sync_bp.route("/status", methods=["GET"])
def get_sync_status():
    status = FireSyncService.get_sync_status()
    return jsonify({
        "success": True,
        "data": status
    }), 200


@fire_sync_bp.route("", methods=["POST"])
def synchronize_fires():
    user = get_authenticated_user()

    if not user:
        return jsonify({
            "error": "Utilisateur non authentifié"
        }), 401

    try:
        days = int(request.args.get("days", 2))
        radius_km = float(request.args.get("radius_km", 10))

        result = FireSyncService.sync_for_owner(
            owner_id=user.id,
            days=days,
            radius_km=radius_km
        )

        return jsonify({
            "success": True,
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500