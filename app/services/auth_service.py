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