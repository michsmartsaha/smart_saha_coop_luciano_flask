from flask import Blueprint, current_app, request

from app.services.auth_service import get_user

from app.repositories.cooperative_repository import CooperativeRepository
from app.services.cooperative_service import CooperativeService
from app.extensions.supabase import set_user_token


cooperative_bp = Blueprint(
    "cooperatives",
    __name__,
    url_prefix="/api/cooperatives"
)


from app.utils.auth import get_current_user_and_role


def get_authenticated_user():
    user, role, _ = get_current_user_and_role()
    return user


def get_service():
    repository = CooperativeRepository(
        current_app.supabase
    )

    return CooperativeService(repository)


@cooperative_bp.get("/")
def get_cooperatives():

    user, role, _ = get_current_user_and_role()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    service = get_service()

    # Si l'utilisateur est admin ou auditeur bio, il a accès à toutes les coopératives
    owner_id = None if role in ("admin", "bio_auditor") else user.id

    cooperatives = service.get_all_cooperatives(
        owner_id
    )

    return {
        "success": True,
        "data": cooperatives
    }, 200


@cooperative_bp.post("/")
def create_cooperative():

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

        cooperative = service.create_cooperative(
            data,
            user.id
        )

        return {
            "success": True,
            "data": cooperative
        }, 201

    except ValueError as e:

        return {
            "success": False,
            "error": str(e)
        }, 400


@cooperative_bp.get("/<cooperative_id>")
def get_cooperative(cooperative_id):

    user, role, _ = get_current_user_and_role()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    service = get_service()

    try:
        owner_id = None if role in ("admin", "bio_auditor") else user.id

        cooperative = service.get_cooperative(
            cooperative_id,
            owner_id
        )

        if not cooperative:
            return {
                "success": False,
                "error": "Coopérative introuvable"
            }, 404

        return {
            "success": True,
            "data": cooperative[0]
        }, 200

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400


@cooperative_bp.put("/<cooperative_id>")
def update_cooperative(cooperative_id):

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

        cooperative = service.update_cooperative(
            cooperative_id,
            user.id,
            data
        )

        if not cooperative:
            return {
                "success": False,
                "error": "Coopérative introuvable"
            }, 404

        return {
            "success": True,
            "data": cooperative[0]
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


@cooperative_bp.delete("/<cooperative_id>")
def delete_cooperative(cooperative_id):

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

        deleted = service.delete_cooperative(
            cooperative_id,
            user.id
        )

        if not deleted:
            return {
                "success": False,
                "error": "Coopérative introuvable"
            }, 404

        return {
            "success": True,
            "message": "Coopérative supprimée avec succès"
        }, 200

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400