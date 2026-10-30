from flask import Blueprint, current_app, request, jsonify

from app.services.auth_service import (
    register_user,
    login_user,
    get_user,
    logout_user
)
from app.utils.auth import get_current_user_and_role



auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/api/auth"
)


@auth_bp.post("/register")
def register():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Données manquantes"
        }), 400

    required_fields = [
        "email",
        "password",
        "first_name",
        "last_name"
    ]

    for field in required_fields:
        if not data.get(field):
            return jsonify({
                "error": f"Le champ '{field}' est obligatoire"
            }), 400

    try:
        response = register_user(
            current_app.supabase,
            data["email"],
            data["password"],
            data["first_name"],
            data["last_name"],
            data.get("phone"),
            role="cooperative_manager"
        )

        user_data = response.user.model_dump() if response.user else None

        # Synchroniser explicitement user_profiles pour garantir le rôle cooperative_manager
        if response.user:
            try:
                current_app.supabase.table("user_profiles").upsert({
                    "id": response.user.id,
                    "first_name": data["first_name"].strip(),
                    "last_name": data["last_name"].strip(),
                    "phone": (data.get("phone") or "").strip() or None,
                    "role": "cooperative_manager"
                }).execute()
            except Exception as pe:
                print("⚠️ Upsert user_profiles lors du register :", pe)

        return jsonify({
            "message": "Compte gestionnaire de coopérative créé avec succès",
            "user": user_data
        }), 201

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 400


@auth_bp.post("/login")
def login():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Données manquantes"
        }), 400

    if not data.get("email") or not data.get("password"):
        return jsonify({
            "error": "Email et mot de passe obligatoires"
        }), 400

    try:
        response = login_user(
            current_app.supabase,
            data["email"],
            data["password"]
        )

        user_id = response.user.id if response.user else None
        user_meta = (response.user.user_metadata or {}) if response.user else {}
        user_role = user_meta.get("role", "cooperative_manager")

        # Récupération du rôle dans user_profiles
        if user_id:
            try:
                prof_res = current_app.supabase.table("user_profiles").select("*").eq("id", user_id).execute()
                if prof_res.data and len(prof_res.data) > 0:
                    user_role = prof_res.data[0].get("role") or user_role
            except Exception as pe:
                print("⚠️ Erreur vérification rôle au login :", pe)

        # Contrôle d'accès : Seul 'field_agent' est réservé à l'application mobile
        if user_role == "field_agent":
            role_label = "Agent de terrain / Enquêteur"
            return jsonify({
                "error": f"Accès réservé au mobile : Votre compte est enregistré en tant que '{role_label}'. Veuillez utiliser l'application mobile SmartSahaBio.",
                "message": f"Ce compte ({role_label}) est réservé à l'application mobile."
            }), 403

        user_dict = response.user.model_dump() if response.user else None
        if user_dict:
            user_dict["role"] = user_role

        return jsonify({
            "message": "Connexion réussie",
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": user_dict
        }), 200

    except Exception as e:
        error_str = str(e)
        if "Invalid login credentials" in error_str:
            return jsonify({
                "error": "Aucun compte associé à cet email ou mot de passe incorrect.",
                "message": "Aucun compte associé à cet email ou mot de passe incorrect."
            }), 401
        elif "Email not confirmed" in error_str:
            return jsonify({
                "error": "Veuillez confirmer votre email avant de vous connecter.",
                "message": "Veuillez confirmer votre email avant de vous connecter."
            }), 401
        elif "rate limit" in error_str.lower() or "too many requests" in error_str.lower():
            return jsonify({
                "error": "Trop de tentatives de connexion. Veuillez réessayer plus tard.",
                "message": "Trop de tentatives de connexion. Veuillez réessayer plus tard."
            }), 429

        return jsonify({
            "error": error_str,
            "message": error_str
        }), 401


@auth_bp.get("/me")
def me():
    user, role, access_token = get_current_user_and_role()

    if not user:
        return jsonify({
            "error": "Token invalide ou expiré"
        }), 401

    try:
        user_dict = user.model_dump() if hasattr(user, "model_dump") else (user if isinstance(user, dict) else {})
        user_meta = user_dict.get("user_metadata") or {}

        # Enrichissement avec les données de public.user_profiles si nécessaire
        first_name = user_dict.get("first_name") or user_meta.get("first_name", "")
        last_name = user_dict.get("last_name") or user_meta.get("last_name", "")
        phone = user_dict.get("phone") or user_meta.get("phone", "")

        # Essai d'enrichissement depuis user_profiles si non présent
        if not first_name or not last_name:
            try:
                prof_res = (
                    current_app.supabase
                    .table("user_profiles")
                    .select("*")
                    .eq("id", user.id if hasattr(user, "id") else user_dict.get("id"))
                    .execute()
                )
                if prof_res.data and len(prof_res.data) > 0:
                    prof = prof_res.data[0]
                    user_dict["profile"] = prof
                    first_name = prof.get("first_name") or first_name
                    last_name = prof.get("last_name") or last_name
                    phone = prof.get("phone") or phone
                    role = prof.get("role") or role
            except Exception:
                pass

        user_dict["first_name"] = first_name
        user_dict["last_name"] = last_name
        user_dict["phone"] = phone
        user_dict["role"] = role

        return jsonify({
            "success": True,
            "user": user_dict
        }), 200

    except Exception as e:
        print("ERREUR AUTH /ME :", repr(e))
        return jsonify({
            "error": "Token invalide ou expiré",
            "details": str(e)
        }), 401


@auth_bp.post("/refresh")
def refresh_session():
    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refresh_token")

    if not refresh_token:
        return jsonify({
            "error": "refresh_token manquant"
        }), 400

    try:
        res = current_app.supabase.auth.refresh_session(refresh_token)
        if not res or not res.session:
            return jsonify({
                "error": "Session invalide ou expirée"
            }), 401

        user_dict = res.user.model_dump() if res.user else None
        return jsonify({
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
            "user": user_dict
        }), 200
    except Exception as e:
        return jsonify({
            "error": "Impossible de rafraîchir la session",
            "details": str(e)
        }), 401



@auth_bp.put("/profile")
def update_profile():
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({
            "error": "Token manquant ou invalide"
        }), 401

    access_token = auth_header.split(" ", 1)[1]

    data = request.get_json(silent=True) or {}

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    phone = (data.get("phone") or "").strip() if data.get("phone") else None
    new_password = (data.get("password") or "").strip() if data.get("password") else None

    if not first_name or not last_name:
        return jsonify({
            "error": "Le prénom et le nom sont obligatoires"
        }), 400

    if new_password and len(new_password) < 6:
        return jsonify({
            "error": "Le nouveau mot de passe doit comporter au moins 6 caractères"
        }), 400

    try:
        from datetime import datetime, timezone
        from app.extensions.supabase import set_user_token

        set_user_token(current_app.supabase, access_token)

        user_res = get_user(current_app.supabase, access_token)
        if not user_res.user:
            return jsonify({
                "error": "Utilisateur non trouvé"
            }), 401

        user_id = user_res.user.id

        # 1. Mise à jour de public.user_profiles
        update_data = {
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        current_app.supabase.table("user_profiles").update(update_data).eq("id", user_id).execute()

        # 2. Mise à jour de Supabase Auth
        auth_update = {
            "data": {
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone
            }
        }
        if new_password:
            auth_update["password"] = new_password

        try:
            current_app.supabase.auth.update_user(auth_update)
        except Exception as e:
            print("⚠️ Auth update_user info :", e)

        # Récupération de l'utilisateur rafraîchi
        refreshed = get_user(current_app.supabase, access_token)
        user_dict = refreshed.user.model_dump() if refreshed.user else {}
        user_dict["first_name"] = first_name
        user_dict["last_name"] = last_name
        user_dict["phone"] = phone
        user_dict["role"] = (
            user_dict.get("user_metadata", {}).get("role")
            or "cooperative_manager"
        )

        return jsonify({
            "success": True,
            "message": "Profil mis à jour avec succès",
            "user": user_dict
        }), 200

    except Exception as e:
        current_app.logger.error("Erreur mise à jour profil : %s", str(e))
        return jsonify({
            "error": str(e)
        }), 500

@auth_bp.post("/logout")
def logout():
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return jsonify({
            "error": "Token manquant"
        }), 401

    if not auth_header.startswith("Bearer "):
        return jsonify({
            "error": "Format du token invalide"
        }), 401

    access_token = auth_header.split(" ", 1)[1]

    data = request.get_json(silent=True) or {}

    refresh_token = data.get("refresh_token")

    if not refresh_token:
        return jsonify({
            "error": "Refresh token manquant"
        }), 400

    try:
        logout_user(
            current_app.supabase,
            access_token,
            refresh_token
        )

        return jsonify({
            "message": "Déconnexion réussie"
        }), 200

    except Exception as e:
        return jsonify({
            "error": "Erreur lors de la déconnexion"
        }), 401