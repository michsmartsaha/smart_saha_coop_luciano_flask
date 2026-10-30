from app import create_app

from app.repositories.parcel_repository import ParcelRepository
from app.services.parcel_import_service import ParcelImportService


app = create_app()

with app.app_context():

    repository = ParcelRepository(
        app.supabase
    )

    service = ParcelImportService(
        repository
    )

    file_path = "tests/data/parcelles_test.zip"

    cooperative_id = "33c3adfe-4c3e-462b-872c-e91e7040f522"

    farmer_id = "5af5531f-96ef-48d1-b95e-8e7d4da5858b"

    owner_id = "4796bd80-3f9b-4b3d-b84d-e31580351ef6"

    parcels = service.import_file(
        file_path,
        cooperative_id,
        farmer_id,
        owner_id
    )

    print(
        "Nombre de parcelles créées :",
        len(parcels)
    )

    print("Parcelles :")
    print(parcels)
