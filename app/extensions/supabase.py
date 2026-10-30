import httpx
from supabase import create_client, Client, ClientOptions


def init_supabase(app) -> Client:
    """
    Initialise le client Supabase à partir
    de la configuration Flask avec transport résilient (auto-reconnect et retry).
    """

    supabase_url = app.config["SUPABASE_URL"]
    supabase_key = app.config["SUPABASE_KEY"]

    if not supabase_url:
        raise ValueError("SUPABASE_URL est manquante")

    if not supabase_key:
        raise ValueError("SUPABASE_KEY est manquante")

    # Configuration HTTP avec reconnexion automatique en cas de déconnexion distante
    custom_http = httpx.Client(
        timeout=httpx.Timeout(30.0, connect=10.0),
        transport=httpx.HTTPTransport(retries=3)
    )

    options = ClientOptions(
        postgrest_client_timeout=30.0,
        storage_client_timeout=30.0,
        httpx_client=custom_http
    )

    client = create_client(
        supabase_url,
        supabase_key,
        options=options
    )

    return client


def set_user_token(
    supabase: Client,
    access_token: str
):
    """
    Configure le JWT de l'utilisateur connecté
    pour les requêtes Supabase/PostgREST.
    """

    supabase.postgrest.auth(access_token)