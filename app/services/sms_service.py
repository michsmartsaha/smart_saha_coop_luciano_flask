import os
import re
import time
import uuid
import requests
from flask import current_app


class SmsService:
    """
    Service d'envoi de SMS via la passerelle mapi.mg (Ibonia Madagascar).
    Routage multi-opérateurs à Madagascar (Telma/Yas, Orange, Airtel).
    """

    _cached_token = None
    _token_expires_at = 0

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """
        Normalise un numéro de téléphone malgache au format local à 10 chiffres (ex: 0341234567)
        tel qu'attendu par l'API mapi.mg.
        Exemples:
          - '+261341234567' -> '0341234567'
          - '261341234567'  -> '0341234567'
          - '034 12 345 67' -> '0341234567'
          - '341234567'     -> '0341234567'
          - '0321234567'    -> '0321234567'
        """
        if not phone:
            return ""

        cleaned = re.sub(r"[^\d+]", "", str(phone).strip())

        # Supprimer indicatif international Madagascar (+261 ou 261)
        if cleaned.startswith("+261"):
            cleaned = cleaned[4:]
        elif cleaned.startswith("261") and len(cleaned) == 12:
            cleaned = cleaned[3:]

        # Ajouter le 0 initial si nécessaire (format 9 chiffres commençant par 3)
        if len(cleaned) == 9 and cleaned.startswith("3"):
            cleaned = f"0{cleaned}"

        return cleaned

    @staticmethod
    def get_api_config():
        """
        Récupère la configuration mapi.mg depuis l'environnement ou Flask config.
        """
        if not os.getenv("MAPI_USERNAME"):
            try:
                from dotenv import load_dotenv
                # Chargement du fichier .env du backend
                env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
                load_dotenv(env_path)
            except Exception:
                pass

        username = os.getenv("MAPI_USERNAME") or (
            current_app.config.get("MAPI_USERNAME") if current_app else None
        )
        password = os.getenv("MAPI_PASSWORD") or (
            current_app.config.get("MAPI_PASSWORD") if current_app else None
        )
        api_url = os.getenv("MAPI_API_URL", "https://messaging.mapi.mg/api").rstrip("/")
        sender_id = os.getenv("MAPI_SENDER_ID", "SmartSaha")

        # Mode simulation si identifiants non renseignés ou forcé par flag
        is_simulation = (
            not username
            or not password
            or username.strip() in ("", "votre_identifiant", "CHANGEME")
            or password.strip() in ("", "votre_mot_de_passe", "CHANGEME")
            or os.getenv("MAPI_SIMULATION_MODE", "false").lower() == "true"
            or os.getenv("SMS_SIMULATION_MODE", "false").lower() == "true"
        )

        return {
            "username": username,
            "password": password,
            "api_url": api_url,
            "sender_id": sender_id,
            "is_simulation": is_simulation,
        }

    @classmethod
    def authenticate(cls, force_refresh: bool = False) -> str:
        """
        Authentifie l'application auprès de mapi.mg (/authentication/login)
        et conserve le token JWT en mémoire (valide 15 minutes).
        """
        cfg = cls.get_api_config()
        if cfg["is_simulation"]:
            return "simulated_token"

        now = time.time()
        if not force_refresh and cls._cached_token and now < cls._token_expires_at:
            return cls._cached_token

        login_url = f"{cfg['api_url']}/authentication/login"
        files = {
            "Username": (None, cfg["username"]),
            "Password": (None, cfg["password"]),
        }

        try:
            res = requests.post(login_url, files=files, timeout=12)
            data = res.json() if res.status_code == 200 else {}
        except Exception as e:
            raise RuntimeError(f"Connexion impossible au serveur d'authentification mapi.mg : {e}")

        if res.status_code != 200 or not (data.get("status") is True or "token" in data):
            err_msg = data.get("message") or data.get("error") or res.text
            raise RuntimeError(f"Échec d'authentification mapi.mg (Code {res.status_code}) : {err_msg}")

        token = data.get("token")
        if not token:
            raise RuntimeError("Réponse mapi.mg invalide : aucun jeton reçu.")

        cls._cached_token = token
        # Le token mapi expire au bout de 15 min, on renouvelle après 12 minutes (720s)
        cls._token_expires_at = now + 720
        return token

    @classmethod
    def send_sms(cls, recipient: str, message: str) -> dict:
        """
        Envoie un SMS à un agriculteur via la passerelle mapi.mg (/msg/send).
        """
        norm_phone = cls.normalize_phone(recipient)
        if not norm_phone or len(norm_phone) != 10:
            raise ValueError(f"Numéro de téléphone malgache invalide ({recipient}). Format attendu : 034xxxxxxx")

        if not message or not message.strip():
            raise ValueError("Le message SMS ne peut pas être vide.")

        cfg = cls.get_api_config()
        msg_text = message.strip()

        # MODE SIMULATION (tests et démo sans coût)
        if cfg["is_simulation"]:
            sim_id = f"mapi_sim_{uuid.uuid4().hex[:8]}"
            print("=" * 64)
            print("📱 [MAPI.MG SIMULATION] Envoi de SMS (Passerelle Madagascar)")
            print(f"👉 Destinataire : {norm_phone} (Origine: {recipient})")
            print(f"👉 Expéditeur   : {cfg['sender_id']}")
            print(f"👉 Message ({len(msg_text)} car.) : {msg_text}")
            print(f"👉 ID Message   : {sim_id}")
            print("=" * 64)
            return {
                "success": True,
                "simulated": True,
                "message_id": sim_id,
                "recipient": norm_phone,
                "message": msg_text,
                "provider": "mapi.mg",
                "status": "delivered_simulated",
            }

        # ENVOI RÉEL VIA L'API mapi.mg
        def _dispatch(token_val: str):
            send_url = f"{cfg['api_url']}/msg/send"
            headers = {
                "Authorization": token_val,
                "Accept": "application/json",
            }
            files = {
                "Recipient": (None, norm_phone),
                "Message": (None, msg_text),
                "Channel": (None, "sms"),
                "dryRun": (None, "false"),
            }
            return requests.post(send_url, files=files, headers=headers, timeout=15)

        token = cls.authenticate()
        response = _dispatch(token)

        # Si expiration de token (401), renouveler et réessayer 1 fois
        if response.status_code == 401:
            print("🔄 Token mapi.mg expiré, régénération du jeton...")
            token = cls.authenticate(force_refresh=True)
            response = _dispatch(token)

        res_json = {}
        try:
            res_json = response.json()
        except Exception:
            res_json = {"raw": response.text}

        is_ok = response.status_code in (200, 201) and (res_json.get("status") is True or "id" in res_json or res_json.get("success") is True)

        if is_ok:
            return {
                "success": True,
                "simulated": False,
                "recipient": norm_phone,
                "provider": "mapi.mg",
                "response": res_json,
                "message_id": res_json.get("id") or res_json.get("message_id"),
            }
        else:
            err_msg = res_json.get("result") or res_json.get("message") or res_json.get("error") or response.text
            print(f"❌ [MAPI.MG ERROR] Code {response.status_code} : {err_msg}")
            return {
                "success": False,
                "simulated": False,
                "recipient": norm_phone,
                "provider": "mapi.mg",
                "error": err_msg,
                "status_code": response.status_code,
            }

    @classmethod
    def send_bulk_sms(cls, recipients: list, message: str) -> dict:
        """
        Envoie un même SMS d'alerte à une liste d'agriculteurs.
        """
        results = []
        sent_count = 0
        failed_count = 0

        unique_phones = []
        seen = set()
        for r in recipients:
            n = cls.normalize_phone(r)
            if n and n not in seen:
                seen.add(n)
                unique_phones.append((r, n))

        for original, norm in unique_phones:
            res = cls.send_sms(norm, message)
            results.append(res)
            if res.get("success"):
                sent_count += 1
            else:
                failed_count += 1

        return {
            "total": len(unique_phones),
            "sent": sent_count,
            "failed": failed_count,
            "provider": "mapi.mg",
            "results": results,
        }

    @classmethod
    def format_fire_alert_sms(
        cls,
        farmer_name: str = None,
        parcel_name: str = None,
        distance_m: float = None,
        coop_name: str = "SmartSaha"
    ) -> str:
        """
        Formate un SMS d'alerte incendie concis (< 160 caractères)
        adapté aux téléphones mobiles basiques des agriculteurs.
        """
        dist_str = f"{int(distance_m)}m" if distance_m is not None else "proche"
        p_name = f" [{parcel_name}]" if parcel_name else ""
        name_str = f" {farmer_name}" if farmer_name else ""

        # SMS clair en français/malgache accessible
        msg = f"ALERTE FEU {coop_name}:{name_str}, foyer actif a {dist_str} de votre parcelle{p_name}. Verifiez d'urgence vos coupe-feux et vos terres."

        # Tronquer à 160 caractères max pour rester dans 1 seul SMS standard
        if len(msg) > 160:
            msg = msg[:157] + "..."

        return msg
