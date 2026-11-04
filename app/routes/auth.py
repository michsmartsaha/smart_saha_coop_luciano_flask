import os
from flask import Blueprint, current_app, request, jsonify

from app.services.auth_service import (
    register_user,
    login_user,
    get_user,
    logout_user,
    request_password_reset,
    update_password,
    verify_email_otp,
    resend_signup_otp
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
            "message": "Compte gestionnaire de coopérative créé avec succès. Un code de validation à 6 chiffres vous a été envoyé par e-mail.",
            "requires_verification": True,
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
    current_password = (data.get("current_password") or "").strip() if data.get("current_password") else None
    new_password = (data.get("password") or "").strip() if data.get("password") else None

    if not first_name or not last_name:
        return jsonify({
            "error": "Le prénom et le nom sont obligatoires"
        }), 400

    if new_password:
        if not current_password:
            return jsonify({
                "error": "Le mot de passe actuel est obligatoire pour modifier votre mot de passe"
            }), 400
        if len(new_password) < 6:
            return jsonify({
                "error": "Le nouveau mot de passe doit comporter au moins 6 caractères"
            }), 400
        if current_password == new_password:
            return jsonify({
                "error": "Le nouveau mot de passe doit être différent de votre mot de passe actuel"
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
        user_email = user_res.user.email

        if new_password:
            # Vérification du mot de passe actuel
            try:
                current_app.supabase.auth.sign_in_with_password({
                    "email": user_email,
                    "password": current_password
                })
            except Exception as auth_err:
                current_app.logger.warning("Échec validation mot de passe actuel : %s", auth_err)
                return jsonify({
                    "error": "Le mot de passe actuel est incorrect"
                }), 400

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
            if new_password:
                try:
                    current_app.supabase.auth.admin.update_user_by_id(user_id, auth_update)
                except Exception as adm_e:
                    current_app.logger.warning("auth.admin.update_user_by_id fallback : %s", adm_e)
                    current_app.supabase.auth.update_user(auth_update)
            else:
                current_app.supabase.auth.update_user(auth_update)
        except Exception as e:
            print("⚠️ Auth update_user info :", e)

        # Si le mot de passe a été modifié, reconnecter immédiatement pour renouveler le JWT
        new_access_token = None
        new_refresh_token = None
        if new_password:
            try:
                new_session_res = current_app.supabase.auth.sign_in_with_password({
                    "email": user_email,
                    "password": new_password
                })
                if new_session_res and new_session_res.session:
                    new_access_token = new_session_res.session.access_token
                    new_refresh_token = new_session_res.session.refresh_token
            except Exception as relogin_e:
                current_app.logger.warning("Auto sign-in après mise à jour mot de passe : %s", relogin_e)

        # Récupération sécurisée du profil utilisateur sans dépendre de l'ancien token révoqué
        try:
            admin_user_res = current_app.supabase.auth.admin.get_user_by_id(user_id)
            refreshed_user = getattr(admin_user_res, "user", admin_user_res)
            user_dict = refreshed_user.model_dump() if hasattr(refreshed_user, "model_dump") else {}
        except Exception:
            user_dict = user_res.user.model_dump() if hasattr(user_res.user, "model_dump") else {}

        user_dict["first_name"] = first_name
        user_dict["last_name"] = last_name
        user_dict["phone"] = phone
        user_dict["role"] = (
            user_dict.get("user_metadata", {}).get("role")
            or "cooperative_manager"
        )

        response_payload = {
            "success": True,
            "message": "Profil mis à jour avec succès",
            "user": user_dict
        }
        if new_access_token:
            response_payload["access_token"] = new_access_token
            response_payload["refresh_token"] = new_refresh_token

        return jsonify(response_payload), 200

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


def translate_auth_error(err_str: str) -> str:
    lower = (err_str or "").lower()
    if "error sending recovery email" in lower:
        return "Impossible d'expédier l'e-mail de réinitialisation. Veuillez vérifier la configuration de la messagerie."
    if "rate limit" in lower or "too many requests" in lower:
        return "Trop de demandes en peu de temps. Veuillez patienter quelques minutes avant de réessayer."
    if "token has expired" in lower or "token is expired" in lower:
        return "Le code de confirmation a expiré. Veuillez demander un nouveau code."
    if "token is invalid" in lower or "invalid token" in lower:
        return "Le code de confirmation saisi est incorrect. Veuillez vérifier les 6 chiffres."
    if "already confirmed" in lower:
        return "Cette adresse email a déjà été confirmée. Vous pouvez vous connecter directement."
    if "expired" in lower or "otp_expired" in lower:
        return "Ce lien ou code de validation a expiré. Veuillez refaire une demande."
    if "invalid" in lower:
        return "Le lien ou code de validation est invalide. Veuillez vérifier votre saisie."
    if "password" in lower and ("short" in lower or "least" in lower or "character" in lower):
        return "Le mot de passe doit comporter au moins 6 caractères."
    if "user not found" in lower:
        return "Aucun compte associé à cette adresse e-mail."
    if "network" in lower or "connect" in lower or "timeout" in lower:
        return "Impossible de joindre le serveur d'authentification. Veuillez réessayer."
    return err_str


@auth_bp.post("/forgot-password")
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({
            "error": "L'adresse e-mail est obligatoire"
        }), 400

    # 1. Vérification préalable : existence d'un compte lié à cette adresse e-mail
    try:
        rpc_res = current_app.supabase.rpc(
            "check_user_exists_by_email",
            {"user_email": email}
        ).execute()

        if rpc_res and rpc_res.data is False:
            return jsonify({
                "error": "Aucun compte n'est associé à cette adresse e-mail."
            }), 404
    except Exception as check_err:
        current_app.logger.warning("Vérification RPC existence utilisateur : %s", check_err)

    # 2. Détection de l'URL de redirection vers le frontend
    frontend_origin = os.getenv("FRONTEND_URL")
    if frontend_origin:
        frontend_origin = frontend_origin.split(",")[0].strip().rstrip("/")
    elif request.headers.get("Origin"):
        frontend_origin = request.headers.get("Origin").rstrip("/")
    else:
        frontend_origin = "http://localhost:5173"

    redirect_to = f"{frontend_origin}/reset-password"

    # 3. Envoi de l'e-mail de réinitialisation
    try:
        request_password_reset(
            current_app.supabase,
            email=email,
            redirect_to=redirect_to
        )
        return jsonify({
            "success": True,
            "message": "Un lien sécurisé de réinitialisation vous a été envoyé par email."
        }), 200
    except Exception as e:
        error_msg = str(e)
        current_app.logger.error("Erreur forgot_password : %s", error_msg)
        print("🚨 ERREUR FORGOT_PASSWORD :", repr(e))

        return jsonify({
            "error": translate_auth_error(error_msg)
        }), 400


@auth_bp.post("/reset-password")
def reset_password():
    data = request.get_json(silent=True) or {}
    new_password = (data.get("password") or "").strip()
    access_token = (data.get("access_token") or "").strip()
    auth_code = (data.get("code") or "").strip()

    # Si access_token n'est pas dans le corps, vérifier le header Authorization
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ", 1)[1].strip()

    if not new_password:
        return jsonify({
            "error": "Le nouveau mot de passe est obligatoire"
        }), 400

    if len(new_password) < 6:
        return jsonify({
            "error": "Le mot de passe doit comporter au moins 6 caractères"
        }), 400

    if not access_token and not auth_code:
        return jsonify({
            "error": "Jeton ou code de réinitialisation manquant ou invalide"
        }), 400

    try:
        update_password(
            current_app.supabase,
            new_password=new_password,
            access_token=access_token if access_token else None,
            auth_code=auth_code if auth_code else None
        )
        return jsonify({
            "success": True,
            "message": "Votre mot de passe a été réinitialisé avec succès. Vous pouvez maintenant vous connecter."
        }), 200
    except Exception as e:
        err_str = str(e)
        current_app.logger.error("Erreur reset_password : %s", err_str)

        return jsonify({
            "error": translate_auth_error(err_str)
        }), 400


@auth_bp.post("/verify-email")
def verify_email():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    token = (data.get("token") or "").strip()

    if not email:
        return jsonify({
            "error": "L'adresse e-mail est obligatoire"
        }), 400

    if not token or len(token) < 6:
        return jsonify({
            "error": "Veuillez saisir un code de vérification valide"
        }), 400

    try:
        response = verify_email_otp(current_app.supabase, email, token)

        if not response or not response.user:
            return jsonify({
                "error": "Code de confirmation invalide ou expiré."
            }), 400

        user_id = response.user.id
        user_meta = response.user.user_metadata or {}
        user_role = user_meta.get("role", "cooperative_manager")

        # Récupération du rôle dans user_profiles
        if user_id:
            try:
                prof_res = current_app.supabase.table("user_profiles").select("*").eq("id", user_id).execute()
                if prof_res.data and len(prof_res.data) > 0:
                    user_role = prof_res.data[0].get("role") or user_role
            except Exception as pe:
                print("⚠️ Erreur vérification rôle après verify-email :", pe)

        user_dict = response.user.model_dump() if hasattr(response.user, "model_dump") else (response.user if isinstance(response.user, dict) else {})
        user_dict["role"] = user_role

        session_access_token = None
        session_refresh_token = None
        if response.session:
            session_access_token = response.session.access_token
            session_refresh_token = response.session.refresh_token

        return jsonify({
            "success": True,
            "message": "Votre adresse email a été confirmée avec succès !",
            "access_token": session_access_token,
            "refresh_token": session_refresh_token,
            "user": user_dict
        }), 200

    except Exception as e:
        err_str = str(e)
        current_app.logger.error("Erreur verify_email : %s", err_str)
        print("🚨 ERREUR VERIFY_EMAIL :", repr(e))
        return jsonify({
            "error": translate_auth_error(err_str)
        }), 400


@auth_bp.post("/resend-verification-code")
def resend_verification_code():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({
            "error": "L'adresse e-mail est obligatoire"
        }), 400

    try:
        resend_signup_otp(current_app.supabase, email)
        return jsonify({
            "success": True,
            "message": "Un nouveau code de confirmation a été envoyé à votre adresse e-mail."
        }), 200
    except Exception as e:
        err_str = str(e)
        current_app.logger.error("Erreur resend_verification_code : %s", err_str)
        print("🚨 ERREUR RESEND_OTP :", repr(e))
        return jsonify({
            "error": translate_auth_error(err_str)
        }), 400

