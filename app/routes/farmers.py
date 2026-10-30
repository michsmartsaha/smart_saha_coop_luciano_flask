from flask import Blueprint, current_app, request

from app.services.auth_service import get_user
from app.extensions.supabase import set_user_token
from app.utils.auth import get_current_user_and_role

from app.repositories.farmer_repository import FarmerRepository
from app.services.farmer_service import FarmerService


farmer_bp = Blueprint(
    "farmers",
    __name__,
    url_prefix="/api/cooperatives"
)

farmer_bp_base = Blueprint(
    "user_farmers",
    __name__,
    url_prefix="/api/farmers"
)


def get_authenticated_user():
    user, role, _ = get_current_user_and_role()
    return user


def get_service():

    repository = FarmerRepository(
        current_app.supabase
    )

    return FarmerService(repository)


@farmer_bp_base.get("")
def get_all_user_farmers():

    user, role, _ = get_current_user_and_role()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    service = get_service()

    try:
        owner_id = None if role in ("admin", "bio_auditor") else user.id

        farmers = service.get_all_farmers_by_owner(
            owner_id
        )

        return {
            "success": True,
            "data": farmers
        }, 200

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400


@farmer_bp.get("/<cooperative_id>/farmers")
def get_farmers(cooperative_id):

    user = get_authenticated_user()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    service = get_service()

    try:

        farmers = service.get_all_farmers(
            cooperative_id
        )

        return {
            "success": True,
            "data": farmers
        }, 200

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400


@farmer_bp.post("/<cooperative_id>/farmers")
def create_farmer(cooperative_id):

    user, role, _ = get_current_user_and_role()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    if role == "bio_auditor":
        return {
            "success": False,
            "error": "Accès refusé : l'auditeur bio a un accès en lecture seule."
        }, 403

    data = request.get_json()

    if not data:
        return {
            "success": False,
            "error": "Données manquantes"
        }, 400

    service = get_service()

    try:

        farmer = service.create_farmer(
            data,
            cooperative_id,
            user.id
        )

        return {
            "success": True,
            "data": farmer
        }, 201

    except ValueError as e:

        return {
            "success": False,
            "error": str(e)
        }, 400

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400


@farmer_bp.get("/<cooperative_id>/farmers/<farmer_id>")
def get_farmer(
    cooperative_id,
    farmer_id
):

    user = get_authenticated_user()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    service = get_service()

    try:

        farmer = service.get_farmer(
            farmer_id,
            cooperative_id
        )

        if not farmer:
            return {
                "success": False,
                "error": "Agriculteur introuvable"
            }, 404

        return {
            "success": True,
            "data": farmer[0]
        }, 200

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400


@farmer_bp.put("/<cooperative_id>/farmers/<farmer_id>")
def update_farmer(
    cooperative_id,
    farmer_id
):

    user, role, _ = get_current_user_and_role()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    if role == "bio_auditor":
        return {
            "success": False,
            "error": "Accès refusé : l'auditeur bio a un accès en lecture seule."
        }, 403

    data = request.get_json()

    if not data:
        return {
            "success": False,
            "error": "Données manquantes"
        }, 400

    service = get_service()

    try:

        farmer = service.update_farmer(
            farmer_id,
            cooperative_id,
            data
        )

        if not farmer:
            return {
                "success": False,
                "error": "Agriculteur introuvable"
            }, 404

        return {
            "success": True,
            "data": farmer[0]
        }, 200

    except ValueError as e:

        return {
            "success": False,
            "error": str(e)
        }, 400

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400


@farmer_bp.delete("/<cooperative_id>/farmers/<farmer_id>")
def delete_farmer(
    cooperative_id,
    farmer_id
):

    user, role, _ = get_current_user_and_role()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    if role == "bio_auditor":
        return {
            "success": False,
            "error": "Accès refusé : l'auditeur bio a un accès en lecture seule."
        }, 403

    service = get_service()

    try:

        deleted = service.delete_farmer(
            farmer_id,
            cooperative_id
        )

        if not deleted:
            return {
                "success": False,
                "error": "Agriculteur introuvable"
            }, 404

        return {
            "success": True,
            "message": "Agriculteur supprimé avec succès"
        }, 200

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400