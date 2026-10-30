from dotenv import load_dotenv
from app import create_app
from app.repositories.fire_repository import FireRepository

load_dotenv()

app = create_app()

test_data = {
    "p_latitude": -25.44065,
    "p_longitude": 45.35389,
    "p_detected_at": "2026-09-28T10:19:00+00:00",
    "p_satellite": "N21",
    "p_instrument": "VIIRS",
    "p_confidence": "l",
    "p_frp": 1.82,
    "p_daynight": "D",
    "p_source": "NASA_FIRMS",
    "p_external_id": "TEST-REPOSITORY-N21-20260928-1019",
    "p_bright_ti4": 331.87,
    "p_bright_ti5": 304.62,
    "p_scan": 0.56,
    "p_track": 0.43,
    "p_version": "2.0NRT",
}

with app.app_context():

    result = FireRepository.insert_detection(test_data)

    print("Résultat du Repository :")
    print(result)
