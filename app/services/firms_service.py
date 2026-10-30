import csv
import io
import os
from datetime import date, timedelta

import requests
from dotenv import load_dotenv


load_dotenv()


class FirmsService:
    """
    Service d'accès à NASA FIRMS.

    Périodes supportées :
    - 1 jour
    - 7 jours

    Les données sont récupérées depuis VIIRS NOAA-21 NRT.
    """

    BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    SOURCE = "VIIRS_NOAA21_NRT"
    MAX_DAY_RANGE = 5

    @staticmethod
    def get_map_key():
        """
        Récupère la clé NASA FIRMS depuis les variables d'environnement.
        """
        map_key = os.getenv("FIRMS_MAP_KEY")

        if not map_key:
            raise ValueError(
                "FIRMS_MAP_KEY n'est pas configurée dans .env"
            )

        return map_key

    @staticmethod
    def build_url(
        map_key,
        west,
        south,
        east,
        north,
        day_range,
        requested_date=None
    ):
        """
        Construit une URL NASA FIRMS pour une période précise.
        """

        area = f"{west},{south},{east},{north}"

        if requested_date:
            return (
                f"{FirmsService.BASE_URL}/"
                f"{map_key}/"
                f"{FirmsService.SOURCE}/"
                f"{area}/"
                f"{day_range}/"
                f"{requested_date}"
            )

        return (
            f"{FirmsService.BASE_URL}/"
            f"{map_key}/"
            f"{FirmsService.SOURCE}/"
            f"{area}/"
            f"{day_range}"
        )

    @staticmethod
    def request_fires(
        map_key,
        west,
        south,
        east,
        north,
        day_range,
        requested_date=None
    ):
        """
        Effectue une requête vers NASA FIRMS et retourne
        les détections sous forme de liste de dictionnaires.
        """

        url = FirmsService.build_url(
            map_key=map_key,
            west=west,
            south=south,
            east=east,
            north=north,
            day_range=day_range,
            requested_date=requested_date
        )

        print(
            "🔥 NASA FIRMS - requête :",
            day_range,
            "jour(s)",
            "- date :",
            requested_date or "Dernières disponibles"
        )

        response = requests.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        reader = csv.DictReader(
            io.StringIO(response.text)
        )

        fires = list(reader)

        print(
            "🔥 NASA FIRMS - détections reçues :",
            len(fires)
        )

        return fires

    @staticmethod
    def get_fires(
        west,
        south,
        east,
        north,
        days=1
    ):
        """
        Récupère les détections NASA FIRMS dans une zone.

        days :
        - 1 : 24 dernières heures
        - 7 : 7 derniers jours
        - 30 : 30 derniers jours
        """

        if days not in (1, 7, 30) and not (1 <= days <= 30):
            raise ValueError(
                "La période doit être comprise entre 1 et 30 jours (ex: 1, 7 ou 30)."
            )

        map_key = FirmsService.get_map_key()
        today = date.today()
        all_fires = []

        def get_fire_key(f):
            return (
                f.get("satellite", ""),
                f.get("instrument", ""),
                f.get("acq_date", ""),
                f.get("acq_time", ""),
                f.get("latitude", ""),
                f.get("longitude", "")
            )

        # ==========================================================
        # 1 JOUR (24 heures)
        # ==========================================================
        if days == 1:
            try:
                # Requête sans date pour avoir les données NRT les plus récentes
                fires = FirmsService.request_fires(
                    map_key=map_key,
                    west=west,
                    south=south,
                    east=east,
                    north=north,
                    day_range=1
                )
                all_fires.extend(fires)
            except Exception as e:
                print("⚠️ Erreur récupération 1 jour NRT :", e)

            # Si aucune détection aujourd'hui (ex: tôt le matin avant le passage satellite),
            # interroger également hier pour couvrir les dernières 24h effectives
            if len(all_fires) == 0:
                yesterday = today - timedelta(days=1)
                try:
                    fires_yesterday = FirmsService.request_fires(
                        map_key=map_key,
                        west=west,
                        south=south,
                        east=east,
                        north=north,
                        day_range=1,
                        requested_date=yesterday.strftime("%Y-%m-%d")
                    )
                    all_fires.extend(fires_yesterday)
                except Exception as e:
                    print("⚠️ Erreur récupération hier :", e)

        # ==========================================================
        # 2 JOURS (48 heures)
        # ==========================================================
        elif days == 2:
            try:
                fires_48h = FirmsService.request_fires(
                    map_key=map_key,
                    west=west,
                    south=south,
                    east=east,
                    north=north,
                    day_range=2
                )
                all_fires.extend(fires_48h)
            except Exception as e:
                print("⚠️ Erreur récupération 48h NRT :", e)

        # ==========================================================
        # 7 JOURS
        # ==========================================================
        elif days == 7:
            # Période 1 : 5 jours les plus récents (sans forcer de date future)
            try:
                fires_first_period = FirmsService.request_fires(
                    map_key=map_key,
                    west=west,
                    south=south,
                    east=east,
                    north=north,
                    day_range=5
                )
                all_fires.extend(fires_first_period)
            except Exception as e:
                print("⚠️ Erreur récupération 5 premiers jours :", e)

            # Période 2 : 2 jours précédents (date = aujourd'hui - 5j)
            second_date = today - timedelta(days=5)
            try:
                fires_second_period = FirmsService.request_fires(
                    map_key=map_key,
                    west=west,
                    south=south,
                    east=east,
                    north=north,
                    day_range=2,
                    requested_date=second_date.strftime("%Y-%m-%d")
                )
                all_fires.extend(fires_second_period)
            except Exception as e:
                print("⚠️ Erreur récupération 2 jours suivants :", e)

        # ==========================================================
        # 30 JOURS (ou personnalisé jusqu'à 30)
        # ==========================================================
        else:
            # 6 tranches de 5 jours
            num_chunks = (days + 4) // 5
            for i in range(num_chunks):
                chunk_days = min(5, days - (i * 5))
                if chunk_days <= 0:
                    break

                try:
                    if i == 0:
                        chunk_fires = FirmsService.request_fires(
                            map_key=map_key,
                            west=west,
                            south=south,
                            east=east,
                            north=north,
                            day_range=chunk_days
                        )
                    else:
                        chunk_date = today - timedelta(days=i * 5)
                        chunk_fires = FirmsService.request_fires(
                            map_key=map_key,
                            west=west,
                            south=south,
                            east=east,
                            north=north,
                            day_range=chunk_days,
                            requested_date=chunk_date.strftime("%Y-%m-%d")
                        )
                    all_fires.extend(chunk_fires)
                except Exception as e:
                    print(f"⚠️ Erreur récupération tranche {i} :", e)

        # Déduplication
        deduped = {}
        for fire in all_fires:
            key = get_fire_key(fire)
            if key not in deduped:
                deduped[key] = fire

        unique_fires = list(deduped.values())

        print(
            "🔥 NASA FIRMS - total détections uniques :",
            len(unique_fires)
        )

        return unique_fires