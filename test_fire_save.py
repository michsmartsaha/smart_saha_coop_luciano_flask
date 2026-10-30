from dotenv import load_dotenv

from app import create_app
from app.services.fire_service import FireService


load_dotenv()

app = create_app()

fire = {
    "latitude": "-25.44065",
    "longitude": "45.35389",
    "bright_ti4": "331.87",
    "scan": "0.56",
    "track": "0.43",
    "acq_date": "2026-09-28",
    "acq_time": "1019",
    "satellite": "N21",
    "instrument": "VIIRS",
    "confidence": "l",
    "version": "2.0NRT",
    "bright_ti5": "304.62",
    "frp": "1.82",
    "daynight": "D",
}

with app.app_context():
    result = FireService.save_fire(fire)

    print("Résultat de l'enregistrement :")
    print(result)
