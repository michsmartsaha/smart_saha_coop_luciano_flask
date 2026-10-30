from flask import Blueprint, jsonify, request, current_app

from app.services.audit_service import AuditService
from app.utils.auth import get_current_user_and_role


audits_bp = Blueprint(
    "audits",
    __name__,
    url_prefix="/api/audits"
)


def get_authenticated_user():
    """
    Récupère l'utilisateur connecté via le cache sécurisé.
    Retourne le dictionnaire de l'utilisateur ou None.
    """
    user, _, _ = get_current_user_and_role()
    if not user:
        return None
    return user.model_dump() if hasattr(user, "model_dump") else user


# ============================================================================
# GET /api/audits/
# Récupérer tous les audits de l'utilisateur connecté
# ============================================================================

@audits_bp.get("/")
def get_audits():

    try:
        user, role, _ = get_current_user_and_role()

        if not user:
            return jsonify({
                "success": False,
                "message": "Utilisateur non authentifié."
            }), 401

        if role == "admin":
            return jsonify({
                "success": False,
                "message": "Accès non autorisé : le rôle administrateur n'a pas accès à la gestion des audits."
            }), 403

        user_id = user.id

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Identifiant utilisateur introuvable."
            }), 401

        owner_id = None if role == "bio_auditor" else user_id
        service = AuditService(current_app.supabase)
        audits = service.get_all_audits(owner_id)

        return jsonify({
            "success": True,
            "data": audits
        }), 200

    except Exception as e:

        current_app.logger.exception(
            "Erreur lors de la récupération des audits"
        )

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# ============================================================================
# GET /api/audits/<audit_id>
# Récupérer un audit
# ============================================================================

@audits_bp.get("/<audit_id>")
def get_audit(audit_id):

    try:
        user, role, _ = get_current_user_and_role()

        if not user:
            return jsonify({
                "success": False,
                "message": "Utilisateur non authentifié."
            }), 401

        if role == "admin":
            return jsonify({
                "success": False,
                "message": "Accès non autorisé : le rôle administrateur n'a pas accès à la gestion des audits."
            }), 403

        user_id = user.id
        owner_id = None if role == "bio_auditor" else user_id

        service = AuditService(current_app.supabase)

        audit = service.get_audit(
            audit_id,
            owner_id
        )

        if not audit:
            return jsonify({
                "success": False,
                "message": "Audit introuvable."
            }), 404

        return jsonify({
            "success": True,
            "data": audit
        }), 200

    except Exception as e:

        current_app.logger.exception(
            "Erreur lors de la récupération de l'audit"
        )

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# ============================================================================
# POST /api/audits/
# Créer un audit
# ============================================================================

@audits_bp.post("/")
def create_audit():

    try:
        user, role, _ = get_current_user_and_role()

        if not user:
            return jsonify({
                "success": False,
                "message": "Utilisateur non authentifié."
            }), 401

        if role == "admin":
            return jsonify({
                "success": False,
                "message": "Accès non autorisé : le rôle administrateur n'a pas accès à la gestion des audits."
            }), 403

        user_id = user.id

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Identifiant utilisateur introuvable."
            }), 401

        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "success": False,
                "message": "Les données JSON sont obligatoires."
            }), 400

        service = AuditService(current_app.supabase)

        audit = service.create_audit(
            data,
            user_id
        )

        return jsonify({
            "success": True,
            "message": "Audit créé avec succès.",
            "data": audit
        }), 201

    except ValueError as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 400

    except Exception as e:

        current_app.logger.exception(
            "Erreur lors de la création de l'audit"
        )

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# ============================================================================
# PUT /api/audits/<audit_id>
# Modifier un audit
# ============================================================================

@audits_bp.put("/<audit_id>")
def update_audit(audit_id):

    try:
        user, role, _ = get_current_user_and_role()

        if not user:
            return jsonify({
                "success": False,
                "message": "Utilisateur non authentifié."
            }), 401

        if role == "admin":
            return jsonify({
                "success": False,
                "message": "Accès non autorisé : le rôle administrateur n'a pas accès à la gestion des audits."
            }), 403

        user_id = user.id

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Identifiant utilisateur introuvable."
            }), 401

        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "success": False,
                "message": "Les données JSON sont obligatoires."
            }), 400

        owner_id = None if role == "bio_auditor" else user_id
        service = AuditService(current_app.supabase)

        audit = service.update_audit(
            audit_id,
            data,
            owner_id
        )

        if not audit:
            return jsonify({
                "success": False,
                "message": "Audit introuvable ou non autorisé."
            }), 404

        return jsonify({
            "success": True,
            "message": "Audit modifié avec succès.",
            "data": audit
        }), 200

    except ValueError as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 400

    except Exception as e:

        current_app.logger.exception(
            "Erreur lors de la modification de l'audit"
        )

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# ============================================================================
# DELETE /api/audits/<audit_id>
# Supprimer un audit
# ============================================================================

@audits_bp.delete("/<audit_id>")
def delete_audit(audit_id):

    try:
        user, role, _ = get_current_user_and_role()

        if not user:
            return jsonify({
                "success": False,
                "message": "Utilisateur non authentifié."
            }), 401

        if role == "admin":
            return jsonify({
                "success": False,
                "message": "Accès non autorisé : le rôle administrateur n'a pas accès à la gestion des audits."
            }), 403

        user_id = user.id

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Identifiant utilisateur introuvable."
            }), 401

        owner_id = None if role == "bio_auditor" else user_id
        service = AuditService(current_app.supabase)

        deleted = service.delete_audit(
            audit_id,
            owner_id
        )

        if not deleted:
            return jsonify({
                "success": False,
                "message": "Audit introuvable ou non autorisé."
            }), 404

        return jsonify({
            "success": True,
            "message": "Audit supprimé avec succès."
        }), 200

    except Exception as e:

        current_app.logger.exception(
            "Erreur lors de la suppression de l'audit"
        )

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500