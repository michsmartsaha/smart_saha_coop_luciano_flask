import os
import tempfile

from flask import Blueprint, current_app, request
from werkzeug.utils import secure_filename

from app.services.auth_service import get_user
from app.extensions.supabase import set_user_token

from app.repositories.parcel_repository import ParcelRepository
from app.services.parcel_service import ParcelService
from app.services.parcel_import_service import ParcelImportService
from app.utils.auth import get_current_user_and_role, get_authenticated_user


parcel_bp = Blueprint(
    "parcels",
    __name__,
    url_prefix="/api/cooperatives"
)

parcel_bp_base = Blueprint(
    "user_parcels",
    __name__,
    url_prefix="/api/parcels"
)


def get_service():

    repository = ParcelRepository(
        current_app.supabase
    )

    return ParcelService(repository)

@parcel_bp_base.get("")
def get_all_user_parcels():

    user, role, _ = get_current_user_and_role()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    service = get_service()

    try:
        owner_id = None if role in ("admin", "bio_auditor") else user.id

        parcels = service.get_all_parcels_by_owner(
            owner_id
        )

        return {
            "success": True,
            "data": parcels
        }, 200

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400


@parcel_bp.get("/<cooperative_id>/parcels")
def get_parcels(cooperative_id):

    user = get_authenticated_user()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    service = get_service()

    try:

        parcels = service.get_all_parcels(
            cooperative_id
        )

        return {
            "success": True,
            "data": parcels
        }, 200

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400


def get_all_by_owner(self, owner_id):
    response = (
        self.supabase
        .table("parcels")
        .select("*")
        .eq("owner", owner_id)
        .order("created_at", desc=True)
        .execute()
    )

    return response.data


@parcel_bp.post("/<cooperative_id>/parcels")
def create_parcel(cooperative_id):

    user, role, _ = get_current_user_and_role()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    if role == "bio_auditor":
        return {
            "success": False,
            "error": "Accès refusé : l'auditeur bio a un accès en lecture seule."
        }, 403

    # ---------------------------------------------------------
    # Cas 1 : import d'un fichier géographique
    # ---------------------------------------------------------

    if "file" in request.files:

        file = request.files["file"]

        if not file.filename:
            return {
                "success": False,
                "error": "Nom de fichier manquant"
            }, 400

        farmer_id = request.form.get(
            "farmer_id"
        )
        parcel_name = request.form.get(
            "name"
        )

        if not farmer_id:
            return {
                "success": False,
                "error": "L'agriculteur est obligatoire"
            }, 400

        repository = ParcelRepository(
            current_app.supabase
        )

        import_service = ParcelImportService(
            repository
        )

        extension = os.path.splitext(
            file.filename
        )[1].lower()

        allowed_extensions = {
            ".kml",
            ".gpkg",
            ".zip"
        }

        if extension not in allowed_extensions:
            return {
                "success": False,
                "error": (
                    "Format de fichier non supporté. "
                    "Formats acceptés : KML, GeoPackage et Shapefile ZIP."
                )
            }, 400

        try:

            with tempfile.TemporaryDirectory() as temp_dir:

                filename = secure_filename(
                    file.filename
                )

                file_path = os.path.join(
                    temp_dir,
                    filename
                )

                file.save(
                    file_path
                )

                parcels = import_service.import_file(
                    file_path,
                    cooperative_id,
                    farmer_id,
                    user.id,
                    default_name=parcel_name
                )

            return {
                "success": True,
                "message": "Parcelle(s) enregistrée(s) avec succès",
                "count": len(parcels),
                "data": parcels
            }, 201

        except ValueError as e:

            return {
                "success": False,
                "error": str(e)
            }, 400

        except Exception as e:

            return {
                "success": False,
                "error": str(e)
            }, 500

    # ---------------------------------------------------------
    # Cas 2 : création avec une géométrie GeoJSON
    # ---------------------------------------------------------

    data = request.get_json()

    if not data:
        return {
            "success": False,
            "error": "Données manquantes"
        }, 400

    service = get_service()

    try:

        parcel = service.create_parcel(
            data,
            cooperative_id,
            user.id
        )

        return {
            "success": True,
            "data": parcel
        }, 201

    except ValueError as e:

        return {
            "success": False,
            "error": str(e)
        }, 400

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 500


@parcel_bp.get("/<cooperative_id>/parcels/<parcel_id>")
def get_parcel(cooperative_id, parcel_id):

    user = get_authenticated_user()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    service = get_service()

    try:
        parcel = service.get_parcel_details(
            parcel_id,
            cooperative_id
        )

        if not parcel:
            return {
                "success": False,
                "error": "Parcelle introuvable"
            }, 404

        return {
            "success": True,
            "data": parcel
        }, 200

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400


@parcel_bp.put("/<cooperative_id>/parcels/<parcel_id>")
def update_parcel(
    cooperative_id,
    parcel_id
):

    user, role, _ = get_current_user_and_role()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    if role == "bio_auditor":
        return {
            "success": False,
            "error": "Accès refusé : l'auditeur bio a un accès en lecture seule."
        }, 403

    data = request.get_json()

    if not data:

        return {
            "success": False,
            "error": "Données manquantes"
        }, 400

    service = get_service()

    try:

        parcel = service.update_parcel(
            parcel_id,
            cooperative_id,
            data
        )

        if not parcel:

            return {
                "success": False,
                "error": "Parcelle introuvable"
            }, 404

        return {
            "success": True,
            "data": parcel
        }, 200

    except ValueError as e:

        return {
            "success": False,
            "error": str(e)
        }, 400

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400


@parcel_bp.delete("/<cooperative_id>/parcels/<parcel_id>")
def delete_parcel(
    cooperative_id,
    parcel_id
):

    user, role, _ = get_current_user_and_role()

    if not user:
        return {
            "success": False,
            "error": "Utilisateur non authentifié"
        }, 401

    if role == "bio_auditor":
        return {
            "success": False,
            "error": "Accès refusé : l'auditeur bio a un accès en lecture seule."
        }, 403

    service = get_service()

    try:

        deleted = service.delete_parcel(
            parcel_id,
            cooperative_id
        )

        if not deleted:

            return {
                "success": False,
                "error": "Parcelle introuvable"
            }, 404

        return {
            "success": True,
            "message": "Parcelle supprimée avec succès"
        }, 200

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }, 400

