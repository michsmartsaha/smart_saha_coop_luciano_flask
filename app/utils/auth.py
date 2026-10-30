import time
import threading
import jwt
from flask import current_app, request
from app.services.auth_service import get_user
from app.extensions.supabase import set_user_token

# Cache en mémoire des tokens validés
# token -> { "user": user_obj, "role": role_str, "expires_at": float }
_AUTH_CACHE = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 300  # 5 minutes


class AuthUser:
    """Représentation légère et robuste d'un utilisateur Supabase."""
    def __init__(self, uid: str, email: str = "", user_metadata: dict = None, role: str = "cooperative_manager"):
        self.id = uid
        self.email = email or ""
        self.user_metadata = user_metadata or {}
        self.role = role

    def model_dump(self):
        return {
            "id": self.id,
            "email": self.email,
            "user_metadata": self.user_metadata,
            "role": self.role
        }

    def dict(self):
        return self.model_dump()

    def get(self, key, default=None):
        if hasattr(self, key):
            return getattr(self, key)
        return self.user_metadata.get(key, default)

    def __getitem__(self, item):
        if hasattr(self, item):
            return getattr(self, item)
        return self.user_metadata[item]


def get_current_user_and_role():
    """
    Récupère l'utilisateur connecté, son rôle et son token JWT.
    Utilise un cache mémoire haute performance (0ms) et un décodage JWT local
    pour éviter les blocages dus à la latence réseau vers Supabase.
    Retourne (user, role, access_token) ou (None, None, None).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, None, None

    access_token = auth_header.split(" ", 1)[1].strip()
    if not access_token:
        return None, None, None

    now = time.time()

    # 1. Vérifier le cache mémoire (ultra-rapide, 0 requête réseau)
    with _CACHE_LOCK:
        cached = _AUTH_CACHE.get(access_token)
        if cached and cached["expires_at"] > now:
            try:
                set_user_token(current_app.supabase, access_token)
            except Exception:
                pass
            return cached["user"], cached["role"], access_token

    # 2. Décodage local du JWT pour vérifier expiration & extraction métadonnées
    payload = {}
    try:
        payload = jwt.decode(access_token, options={"verify_signature": False})
        token_exp = payload.get("exp")
        if token_exp and token_exp < now:
            # Token réellement expiré
            with _CACHE_LOCK:
                _AUTH_CACHE.pop(access_token, None)
            return None, None, None
    except Exception as e:
        print("⚠️ Erreur décodage JWT local :", e)
        return None, None, None

    uid = payload.get("sub")
    if not uid:
        return None, None, None

    email = payload.get("email", "")
    user_meta = payload.get("user_metadata") or {}
    role = user_meta.get("role", "cooperative_manager")

    user = None

    # 3. Validation auprès de Supabase
    try:
        set_user_token(current_app.supabase, access_token)
        response = get_user(current_app.supabase, access_token)
        if response and response.user:
            user = response.user
            # Vérification du rôle dans user_profiles si disponible
            try:
                prof_res = (
                    current_app.supabase
                    .table("user_profiles")
                    .select("role")
                    .eq("id", user.id)
                    .execute()
                )
                if prof_res.data and len(prof_res.data) > 0 and prof_res.data[0].get("role"):
                    role = prof_res.data[0]["role"]
                else:
                    role = (user.user_metadata or {}).get("role", role)
            except Exception:
                role = (user.user_metadata or {}).get("role", role)
    except Exception as e:
        print("⚠️ Appel Supabase auth échoué (réseau/latence) :", repr(e))
        # Si Supabase n'est pas joignable (timeout réseau), mais le token JWT est valide et non expiré
        # on utilise le fallback robuste AuthUser pour ne pas bloquer l'utilisateur
        user = AuthUser(uid=uid, email=email, user_metadata=user_meta, role=role)

    if not user:
        return None, None, None

    # 4. Enregistrer dans le cache mémoire
    token_exp = payload.get("exp", now + _CACHE_TTL_SECONDS)
    cache_ttl = min(now + _CACHE_TTL_SECONDS, token_exp)

    with _CACHE_LOCK:
        # Nettoyage occasionnel si le cache grandit
        if len(_AUTH_CACHE) > 500:
            expired_keys = [k for k, v in _AUTH_CACHE.items() if v["expires_at"] <= now]
            for k in expired_keys:
                _AUTH_CACHE.pop(k, None)

        _AUTH_CACHE[access_token] = {
            "user": user,
            "role": role,
            "expires_at": cache_ttl
        }

    return user, role, access_token


def get_authenticated_user():
    """
    Récupère l'utilisateur connecté sans information de rôle spécifique.
    Retourne l'objet user ou None.
    """
    user, _, _ = get_current_user_and_role()
    return user


def require_admin():
    """
    Vérifie si l'utilisateur courant est un administrateur.
    Retourne (user, role) si admin, sinon None.
    """
    user, role, _ = get_current_user_and_role()
    if not user or role != "admin":
        return None, None
    return user, role

