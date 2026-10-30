from dotenv import load_dotenv

from app import create_app
from app.services.firms_service import FirmsService
from app.services.fire_service import FireService


load_dotenv()

app = create_app()


with app.app_context():

    fires = FirmsService.get_fires(
        west=43,
        south=-26,
        east=51,
        north=-12,
        days=5
    )

    print("Détections récupérées depuis NASA FIRMS :", len(fires))

    if fires:

        # Pour le premier test, on synchronise seulement 2 détections
        test_fires = fires[:2]

        results = FireService.sync_fires(test_fires)

        print("Détections synchronisées :", len(results))

        print("\nPremière détection enregistrée :")
        print(results[0])

        print("\nDeuxième détection enregistrée :")
        print(results[1])

    else:
        print("Aucune détection trouvée.")