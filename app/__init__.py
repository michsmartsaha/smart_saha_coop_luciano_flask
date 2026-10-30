import os
from flask import Flask
from flask_cors import CORS

from app.config.settings import Config
from app.routes.health import health_bp
from app.routes.supabase_test import supabase_test_bp
from app.extensions.supabase import init_supabase
from app.routes.cooperatives import cooperative_bp
from app.routes.auth import auth_bp
from app.routes.farmers import farmer_bp
from app.routes.farmers import farmer_bp_base
from app.routes.parcels import parcel_bp
from app.routes.parcels import parcel_bp_base
from app.routes.fire import fire_bp
from app.routes.fire_alert import fire_alert_bp
from app.routes.fire_sync import fire_sync_bp
from app.routes.audits import audits_bp
from app.routes.surveys import surveys_bp
from app.routes.reports import reports_bp
from app.routes.admin import admin_bp
from app.services.fire_sync_service import FireSyncScheduler


def create_app():
    app = Flask(__name__)

    # Configuration CORS dynamique (supporte Vercel en prod + dev local)
    allowed_origins = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
    ]
    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        for url in frontend_url.split(","):
            cleaned = url.strip()
            if cleaned and cleaned not in allowed_origins:
                allowed_origins.append(cleaned)

    CORS(
        app,
        origins=allowed_origins,
        supports_credentials=True
    )

    # Configuration
    app.config.from_object(Config)

    # Initialisation Supabase
    app.supabase = init_supabase(app)

    # Blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(supabase_test_bp)
    app.register_blueprint(cooperative_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(farmer_bp)
    app.register_blueprint(farmer_bp_base)
    app.register_blueprint(parcel_bp)
    app.register_blueprint(parcel_bp_base)
    app.register_blueprint(fire_bp)
    app.register_blueprint(fire_alert_bp)
    app.register_blueprint(fire_sync_bp)
    app.register_blueprint(audits_bp)
    app.register_blueprint(surveys_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)

    # Démarrage de la synchronisation automatique NASA FIRMS toutes les 30 minutes (1800 secondes)
    FireSyncScheduler.start(app, interval_seconds=1800)

    return app