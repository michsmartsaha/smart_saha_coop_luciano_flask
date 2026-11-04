from supabase import Client


def register_user(
    supabase: Client,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    phone: str | None = None,
    role: str = "cooperative_manager",
    metadata: dict | None = None
):
    """
    Crée un utilisateur dans Supabase Auth avec le rôle spécifié
    (par défaut 'cooperative_manager' pour l'inscription web).
    """

    user_data = {
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "role": role
    }
    if metadata:
        user_data.update(metadata)

    response = supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": {
            "data": user_data
        }
    })

    return response


def login_user(
    supabase: Client,
    email: str,
    password: str
):
    """
    Authentifie un utilisateur avec son email et son mot de passe.
    """

    response = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })

    return response


def get_user(
    supabase: Client,
    access_token: str
):
    """
    Récupère l'utilisateur Supabase à partir
    de son access token.
    """

    response = supabase.auth.get_user(access_token)

    return response

def logout_user(
    supabase: Client,
    access_token: str,
    refresh_token: str
):
    """
    Déconnecte l'utilisateur de sa session Supabase.
    """

    supabase.auth.set_session(
        access_token,
        refresh_token
    )

    response = supabase.auth.sign_out()

    return response


def request_password_reset(
    supabase: Client,
    email: str,
    redirect_to: str | None = None
):
    """
    Envoie un email de réinitialisation de mot de passe via Supabase Auth.
    """
    options = {}
    if redirect_to:
        options["redirect_to"] = redirect_to

    return supabase.auth.reset_password_for_email(email, options=options)


def update_password(
    supabase: Client,
    new_password: str,
    access_token: str | None = None,
    auth_code: str | None = None
):
    """
    Met à jour le mot de passe d'un utilisateur après validation
    de son jeton de récupération (access_token ou auth_code PKCE).
    """
    if auth_code:
        exchange_res = supabase.auth.exchange_code_for_session({"auth_code": auth_code})
        if exchange_res and exchange_res.session:
            access_token = exchange_res.session.access_token

    if not access_token:
        raise ValueError("Jeton ou code de réinitialisation manquant ou expiré.")

    # 1. Mise à jour via l'API Auth de Supabase avec le token JWT de l'utilisateur
    try:
        res = supabase.auth._request(
            "PUT",
            "user",
            body={"password": new_password},
            jwt=access_token
        )
        return res
    except Exception as user_err:
        # 2. Fallback via admin.update_user_by_id si une clé service_role est configurée
        try:
            user_res = supabase.auth.get_user(access_token)
            if user_res and user_res.user:
                return supabase.auth.admin.update_user_by_id(
                    user_res.user.id,
                    {"password": new_password}
                )
        except Exception:
            pass
        raise user_err


def verify_email_otp(
    supabase: Client,
    email: str,
    token: str
):
    """
    Valide le code OTP à 6 chiffres envoyé par email lors de l'inscription.
    """
    response = supabase.auth.verify_otp({
        "email": email,
        "token": token,
        "type": "signup"
    })
    return response


def resend_signup_otp(
    supabase: Client,
    email: str
):
    """
    Renvoie un nouveau code OTP d'inscription par email.
    """
    response = supabase.auth.resend({
        "type": "signup",
        "email": email
    })
    return response

