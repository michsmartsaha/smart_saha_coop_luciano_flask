from flask import Blueprint, Response, current_app, request

from app.repositories.survey_repository import SurveyRepository
from app.services.survey_service import SurveyService
from app.utils.auth import get_authenticated_user


surveys_bp = Blueprint("surveys", __name__, url_prefix="/api/surveys")


def get_service():
    repository = SurveyRepository(current_app.supabase)
    return SurveyService(repository)


# ============================================================
# FORMULAIRES D'ENQUÊTE
# ============================================================

@surveys_bp.get("")
def list_forms():
    user = get_authenticated_user()
    if not user:
        return {"success": False, "error": "Utilisateur non authentifié"}, 401

    cooperative_id = request.args.get("cooperative_id")
    campaign = request.args.get("campaign")

    service = get_service()
    try:
        forms = service.get_forms(
            owner_id=user.id,
            cooperative_id=cooperative_id,
            campaign=campaign
        )
        return {"success": True, "data": forms}, 200
    except Exception as e:
        return {"success": False, "error": str(e)}, 400


@surveys_bp.post("")
def create_form():
    user = get_authenticated_user()
    if not user:
        return {"success": False, "error": "Utilisateur non authentifié"}, 401

    data = request.get_json()
    if not data:
        return {"success": False, "error": "Données requises manquantes"}, 400

    service = get_service()
    try:
        created = service.create_form(data, user.id)
        return {"success": True, "data": created}, 201
    except ValueError as e:
        return {"success": False, "error": str(e)}, 400
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


@surveys_bp.get("/<form_id>")
def get_form(form_id):
    user = get_authenticated_user()
    if not user:
        return {"success": False, "error": "Utilisateur non authentifié"}, 401

    service = get_service()
    try:
        form = service.get_form(form_id)
        return {"success": True, "data": form}, 200
    except ValueError as e:
        return {"success": False, "error": str(e)}, 404
    except Exception as e:
        return {"success": False, "error": str(e)}, 400


@surveys_bp.put("/<form_id>")
def update_form(form_id):
    user = get_authenticated_user()
    if not user:
        return {"success": False, "error": "Utilisateur non authentifié"}, 401

    data = request.get_json()
    if not data:
        return {"success": False, "error": "Données requises manquantes"}, 400

    service = get_service()
    try:
        updated = service.update_form(form_id, data, user.id)
        return {"success": True, "data": updated}, 200
    except ValueError as e:
        return {"success": False, "error": str(e)}, 400
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


@surveys_bp.delete("/<form_id>")
def delete_form(form_id):
    user = get_authenticated_user()
    if not user:
        return {"success": False, "error": "Utilisateur non authentifié"}, 401

    service = get_service()
    try:
        service.delete_form(form_id, user.id)
        return {"success": True, "message": "Formulaire supprimé"}, 200
    except ValueError as e:
        return {"success": False, "error": str(e)}, 400
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


# ============================================================
# RÉPONSES
# ============================================================

@surveys_bp.get("/<form_id>/responses")
def list_responses(form_id):
    user = get_authenticated_user()
    if not user:
        return {"success": False, "error": "Utilisateur non authentifié"}, 401

    service = get_service()
    try:
        responses = service.get_responses(form_id)
        return {"success": True, "data": responses}, 200
    except Exception as e:
        return {"success": False, "error": str(e)}, 400


@surveys_bp.post("/<form_id>/responses")
def submit_response(form_id):
    user = get_authenticated_user()
    if not user:
        return {"success": False, "error": "Utilisateur non authentifié"}, 401

    data = request.get_json()
    if not data:
        return {"success": False, "error": "Données requises manquantes"}, 400

    service = get_service()
    try:
        submitted = service.create_response(form_id, data, user.id)
        return {"success": True, "data": submitted}, 201
    except ValueError as e:
        return {"success": False, "error": str(e)}, 400
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


@surveys_bp.delete("/<form_id>/responses/<response_id>")
def delete_response(form_id, response_id):
    user = get_authenticated_user()
    if not user:
        return {"success": False, "error": "Utilisateur non authentifié"}, 401

    service = get_service()
    try:
        service.delete_response(response_id, user.id)
        return {"success": True, "message": "Réponse supprimée"}, 200
    except Exception as e:
        return {"success": False, "error": str(e)}, 400


# ============================================================
# EXPORT CSV
# ============================================================

@surveys_bp.get("/<form_id>/export")
def export_responses(form_id):
    user = get_authenticated_user()
    if not user:
        return {"success": False, "error": "Utilisateur non authentifié"}, 401

    service = get_service()
    try:
        csv_data = service.export_responses_csv(form_id)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=enquete_{form_id}.csv",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )
    except Exception as e:
        return {"success": False, "error": str(e)}, 400
