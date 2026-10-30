from dotenv import load_dotenv

from app.services.firms_service import FirmsService


load_dotenv()


fires = FirmsService.get_fires(
    west=43,
    south=-26,
    east=51,
    north=-12,
    days=5
)


print("Nombre de détections :", len(fires))

if fires:
    print("\nPremière détection :")
    print(fires[0])

    print("\nDeuxième détection :")
    print(fires[1])