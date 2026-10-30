from flask import Blueprint, jsonify, request, current_app

from app.services.fire_service import FireService
from app.services.fire_sync_service import FireSyncService
from app.utils.auth import get_authenticated_user


fire_bp = Blueprint(
    "fires",
    __name__,
    url_prefix="/api/fires"
)


@fire_bp.route("/nearby", methods=["GET"])
def get_nearby_fires():

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

        if radius_km <= 0:
            return jsonify({
                "error": "Le rayon doit être supérieur à 0"
            }), 400

        period = request.args.get(
            "period",
            "7d"
        ).lower()

        periods = {
            "24h": 1,
            "48h": 2,
            "7d": 7,
            "30d": 30,
        }

        if period not in periods:
            return jsonify({
                "error": (
                    "Période invalide. "
                    "Utilisez 24h, 48h ou 7d."
                )
            }), 400

        days = periods[period]
        force_refresh = request.args.get("refresh", "false").lower() == "true"

        # Synchronisation ciblée si demandée explicitement ou si la zone de l'utilisateur n'a jamais été synchronisée
        needs_initial_sync = not FireSyncService.has_synced_owner(user.id)
        if force_refresh or needs_initial_sync:
            try:
                FireSyncService.sync_for_owner(
                    owner_id=user.id,
                    days=max(days, 2),
                    radius_km=max(radius_km, 10)
                )
            except Exception as sync_err:
                print("⚠️ Erreur synchronisation à la demande :", sync_err)

        # Récupération ultra-rapide (<50ms) depuis PostGIS via GIST spatial index
        fires = FireService.get_fires_from_db(
            owner_id=user.id,
            radius_km=radius_km,
            days=days
        )

        # Fallback de secours si la base PostGIS est vide lors d'un premier lancement
        if len(fires) == 0 and not FireSyncService.has_synced_owner(user.id):
            fires = FireService.get_fires_from_nasa(
                owner_id=user.id,
                radius_km=radius_km,
                days=days
            )

        sync_status = FireSyncService.get_sync_status()

        return jsonify({
            "radius_km": radius_km,
            "period": period,
            "count": len(fires),
            "data": fires,
            "last_sync_at": sync_status.get("last_sync_at"),
            "is_syncing": sync_status.get("is_syncing", False)
        }), 200

    except ValueError as e:

        return jsonify({
            "error": str(e)
        }), 400

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500