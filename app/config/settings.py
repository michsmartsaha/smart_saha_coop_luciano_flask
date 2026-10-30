import os
from dotenv import load_dotenv


load_dotenv()


class Config:
    """
    Configuration générale de Smart Saha.
    """

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "dev-secret-key-change-me"
    )

    DEBUG = os.getenv(
        "FLASK_DEBUG",
        "false"
    ).lower() == "true"

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
