from datetime import datetime, timezone
import json
import os
from flask import Blueprint, current_app, request, jsonify

from app.utils.auth import get_current_user_and_role, require_admin
from app.services.auth_service import register_user


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/api/admin"
)

# Chemin pour persister les paramètres système de l'administrateur
SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config",
    "system_settings.json"
)

DEFAULT_SETTINGS = {
    "platform_name": "SmartSahaBio",
    "bio_standard": "Règlementation UE 2018/848",
    "fire_alert_radius_km": 5,
    "audit_validity_months": 12,
    "nasa_firm_source": "VIIRS_NOAA21_NRT",
    "auto_notify_fire": True,
    "require_parcel_gps": True,
    "allow_offline_mobile": True,
    "maintenance_mode": False
}


def load_system_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
    except Exception as e:
        print("Erreur lecture system_settings.json :", e)
    return DEFAULT_SETTINGS.copy()


def save_system_settings(settings):
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print("Erreur écriture system_settings.json :", e)
        return False


# ============================================================================
# GESTION DES UTILISATEURS (COMPTES & RÔLES)
# ============================================================================

@admin_bp.get("/users")
def get_users():
    """
    Retourne la liste de tous les utilisateurs et leurs rôles.
    Accessible uniquement aux administrateurs.
    """
    user, role = require_admin()
    if not user:
        return jsonify({
            "success": False,
            "error": "Accès réservé aux administrateurs."
        }), 403

    try:
        # Récupération de tous les profils
        res = (
            current_app.supabase
            .table("user_profiles")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        profiles = res.data or []

        # Récupération des coopératives pour mapper les noms si nécessaire
        try:
            coops_res = current_app.supabase.table("cooperatives").select("uuid, name").execute()
            coops_map = {c["uuid"]: c["name"] for c in (coops_res.data or [])}
            for p in profiles:
                cid = p.get("cooperative_id")
                if cid and cid in coops_map:
                    p["cooperative_name"] = coops_map[cid]
        except Exception as ce:
            print("Erreur mapping coopératives :", ce)

        return jsonify({
            "success": True,
            "data": profiles,
            "count": len(profiles)
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@admin_bp.post("/users")
def create_user():
    """
    Permet à l'administrateur de créer un compte (Agent de terrain, Auditeur bio, ou Gestionnaire).
    - Pas d'option Administrateur (créé manuellement dans Supabase).
    - Agent de terrain : affectation obligatoire à une coopérative.
    - Auditeur Bio : pas d'affectation à une coopérative.
    """
    user, role = require_admin()
    if not user:
        return jsonify({
            "success": False,
            "error": "Accès réservé aux administrateurs."
        }), 403

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    phone = (data.get("phone") or "").strip() or None
    user_role = (data.get("role") or "").strip()
    cooperative_id = data.get("cooperative_id") or None
    cooperative_name = data.get("cooperative_name") or None

    # Pas d'option Administrateur à la création d'utilisateur
    if user_role == "admin":
        return jsonify({
            "success": False,
            "error": "La création d'un compte Administrateur n'est pas autorisée depuis cette interface. Les administrateurs sont créés directement dans Supabase."
        }), 400

    valid_roles = ["field_agent", "bio_auditor", "cooperative_manager"]
    if user_role not in valid_roles:
        return jsonify({
            "success": False,
            "error": f"Rôle invalide. Rôles autorisés pour la création : {', '.join(valid_roles)}"
        }), 400

    # Règle : Agent de terrain doit obligatoirement avoir une coopérative affectée
    if user_role == "field_agent":
        if not cooperative_id:
            return jsonify({
                "success": False,
                "error": "L'affectation à une coopérative est obligatoire pour un Agent de terrain."
            }), 400

    # Règle : Auditeur bio n'a pas de choix de coopérative
    if user_role == "bio_auditor":
        cooperative_id = None
        cooperative_name = None

    if not email or not password or not first_name or not last_name:
        return jsonify({
            "success": False,
            "error": "Email, mot de passe, prénom et nom sont obligatoires."
        }), 400

    if len(password) < 8:
        return jsonify({
            "success": False,
            "error": "Le mot de passe doit comporter au moins 8 caractères."
        }), 400

    try:
        extra_meta = {}
        if cooperative_id:
            extra_meta["cooperative_id"] = cooperative_id
            if cooperative_name:
                extra_meta["cooperative_name"] = cooperative_name

        response = register_user(
            current_app.supabase,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=user_role,
            metadata=extra_meta
        )

        created_user = response.user
        if created_user:
            profile_data = {
                "id": created_user.id,
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone,
                "role": user_role
            }
            if cooperative_id:
                profile_data["cooperative_id"] = cooperative_id

            try:
                current_app.supabase.table("user_profiles").upsert(profile_data).execute()
            except Exception as pe:
                print("⚠️ Upsert avec cooperative_id échoué, tentative sans :", pe)
                profile_data.pop("cooperative_id", None)
                current_app.supabase.table("user_profiles").upsert(profile_data).execute()

        return jsonify({
            "success": True,
            "message": f"Utilisateur créé avec succès avec le rôle '{user_role}'.",
            "user": created_user.model_dump() if created_user else None
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@admin_bp.put("/users/<user_id>/role")
def update_user_role(user_id):
    """
    Permet à l'administrateur de modifier le rôle d'un utilisateur.
    """
    user, role = require_admin()
    if not user:
        return jsonify({
            "success": False,
            "error": "Accès réservé aux administrateurs."
        }), 403

    data = request.get_json(silent=True) or {}
    new_role = (data.get("role") or "").strip()

    valid_roles = ["admin", "cooperative_manager", "field_agent", "bio_auditor"]
    if new_role not in valid_roles:
        return jsonify({
            "success": False,
            "error": f"Rôle invalide. Rôles autorisés : {', '.join(valid_roles)}"
        }), 400

    try:
        update_data = {
            "role": new_role,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        res = (
            current_app.supabase
            .table("user_profiles")
            .update(update_data)
            .eq("id", user_id)
            .execute()
        )

        return jsonify({
            "success": True,
            "message": f"Rôle mis à jour avec succès vers '{new_role}'.",
            "data": res.data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@admin_bp.delete("/users/<user_id>")
def delete_user(user_id):
    """
    Supprime le profil d'un utilisateur.
    """
    user, role = require_admin()
    if not user:
        return jsonify({
            "success": False,
            "error": "Accès réservé aux administrateurs."
        }), 403

    if user.id == user_id:
        return jsonify({
            "success": False,
            "error": "Vous ne pouvez pas supprimer votre propre compte administrateur."
        }), 400

    try:
        res = (
            current_app.supabase
            .table("user_profiles")
            .delete()
            .eq("id", user_id)
            .execute()
        )

        return jsonify({
            "success": True,
            "message": "Profil utilisateur supprimé avec succès.",
            "data": res.data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# STATISTIQUES GLOBALES POUR L'ADMINISTRATEUR
# ============================================================================

@admin_bp.get("/stats")
def get_global_stats():
    """
    Retourne les indicateurs de synthèse globaux de toute la plateforme.
    """
    user, role = require_admin()
    if not user:
        return jsonify({
            "success": False,
            "error": "Accès réservé aux administrateurs."
        }), 403

    try:
        # 1. Total Coopératives
        coop_res = current_app.supabase.table("cooperatives").select("uuid", count="exact").execute()
        cooperatives_count = coop_res.count if coop_res.count is not None else len(coop_res.data or [])

        # 2. Total Agriculteurs
        farmers_res = current_app.supabase.table("farmers").select("uuid", count="exact").execute()
        farmers_count = farmers_res.count if farmers_res.count is not None else len(farmers_res.data or [])

        # 3. Total Parcelles
        parcels_res = current_app.supabase.table("parcels").select("uuid", count="exact").execute()
        parcels_count = parcels_res.count if parcels_res.count is not None else len(parcels_res.data or [])

        # 4. Total Audits Bio
        audits_count = 0
        try:
            audits_res = current_app.supabase.table("audits_bio").select("id", count="exact").execute()
            audits_count = audits_res.count if audits_res.count is not None else len(audits_res.data or [])
        except Exception:
            pass

        # 5. Formulaires d'enquêtes
        surveys_count = 0
        try:
            surveys_res = current_app.supabase.table("survey_forms").select("id", count="exact").execute()
            surveys_count = surveys_res.count if surveys_res.count is not None else len(surveys_res.data or [])
        except Exception:
            pass

        # 6. Répartition des utilisateurs par rôle
        users_res = current_app.supabase.table("user_profiles").select("role").execute()
        users_data = users_res.data or []
        roles_count = {
            "admin": 0,
            "cooperative_manager": 0,
            "field_agent": 0,
            "bio_auditor": 0,
            "total": len(users_data)
        }
        for u in users_data:
            r = u.get("role")
            if r in roles_count:
                roles_count[r] += 1

        return jsonify({
            "success": True,
            "data": {
                "cooperatives": cooperatives_count,
                "farmers": farmers_count,
                "parcels": parcels_count,
                "audits": audits_count,
                "surveys": surveys_count,
                "users": roles_count
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# PARAMÉTRAGES SYSTÈME (ADMINISTRATION)
# ============================================================================

@admin_bp.get("/settings")
def get_settings():
    """
    Retourne les paramètres de la plateforme.
    """
    user, role = require_admin()
    if not user:
        return jsonify({
            "success": False,
            "error": "Accès réservé aux administrateurs."
        }), 403

    settings = load_system_settings()
    return jsonify({
        "success": True,
        "data": settings
    }), 200


@admin_bp.put("/settings")
def update_settings():
    """
    Met à jour les paramètres de la plateforme.
    """
    user, role = require_admin()
    if not user:
        return jsonify({
            "success": False,
            "error": "Accès réservé aux administrateurs."
        }), 403

    data = request.get_json(silent=True) or {}
    current_settings = load_system_settings()

    # Mise à jour des clés fournies
    for key in DEFAULT_SETTINGS.keys():
        if key in data:
            current_settings[key] = data[key]

    if save_system_settings(current_settings):
        return jsonify({
            "success": True,
            "message": "Paramètres enregistrés avec succès.",
            "data": current_settings
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": "Échec de l'enregistrement des paramètres."
        }), 500
