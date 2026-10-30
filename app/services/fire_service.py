from math import cos, radians

from flask import current_app
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform

from app.repositories.fire_repository import FireRepository
from app.repositories.parcel_repository import ParcelRepository
from app.services.firms_service import FirmsService


class FireService:

    @staticmethod
    def transform_fire(fire):
        from datetime import datetime, timezone

        detected_at = datetime.strptime(
            f"{fire['acq_date']} {fire['acq_time']}",
            "%Y-%m-%d %H%M"
        ).replace(tzinfo=timezone.utc)

        external_id = (
            f"{fire['satellite']}-"
            f"{fire['instrument']}-"
            f"{fire['acq_date']}-"
            f"{fire['acq_time']}-"
            f"{fire['latitude']}-"
            f"{fire['longitude']}-"
            f"{fire['scan']}-"
            f"{fire['track']}"
        )

        return {
            "p_latitude": float(fire["latitude"]),
            "p_longitude": float(fire["longitude"]),
            "p_detected_at": detected_at.isoformat(),
            "p_satellite": fire.get("satellite"),
            "p_instrument": fire.get("instrument"),
            "p_confidence": fire.get("confidence"),
            "p_frp": (
                float(fire["frp"])
                if fire.get("frp")
                else None
            ),
            "p_daynight": fire.get("daynight"),
            "p_source": "NASA_FIRMS",
            "p_external_id": external_id,
            "p_bright_ti4": (
                float(fire["bright_ti4"])
                if fire.get("bright_ti4")
                else None
            ),
            "p_bright_ti5": (
                float(fire["bright_ti5"])
                if fire.get("bright_ti5")
                else None
            ),
            "p_scan": (
                float(fire["scan"])
                if fire.get("scan")
                else None
            ),
            "p_track": (
                float(fire["track"])
                if fire.get("track")
                else None
            ),
            "p_version": fire.get("version"),
        }

    @staticmethod
    def save_fire(fire):
        data = FireService.transform_fire(fire)

        return FireRepository.insert_detection(data)

    @staticmethod
    def get_fires_from_db(owner_id, radius_km=5, days=1):
        """
        Récupère les détections de feux à proximité des parcelles
        directement depuis PostGIS via spatial index GIST en quelques millisecondes (< 50ms).
        """
        radius_m = radius_km * 1000
        period_hours = max(days * 24, 24)

        try:
            records = FireRepository.get_nearby_parcels(
                radius_m=radius_m,
                period_hours=period_hours
            )
        except Exception as e:
            print("⚠️ Erreur appel RPC PostGIS get_nearby_parcels :", e)
            records = []

        if not records:
            return []

        # Enrichissement avec le nom des parcelles et les coordonnées de l'agriculteur (téléphone)
        parcel_ids = list({row.get("parcel_id") for row in records if row.get("parcel_id")})
        parcel_info_map = {}
        if parcel_ids:
            try:
                p_res = (
                    current_app.supabase
                    .table("parcels")
                    .select("uuid, name, farmer_id, farmers(uuid, full_name, phone)")
                    .in_("uuid", parcel_ids)
                    .execute()
                )
                for p in (p_res.data or []):
                    parcel_info_map[p["uuid"]] = p
            except Exception as pe:
                print("⚠️ Erreur enrichissement parcelles/agriculteurs :", pe)

        fires_by_id = {}
        for row in records:
            f_id = row.get("fire_id")
            p_data = parcel_info_map.get(row.get("parcel_id")) or {}
            farmer_data = p_data.get("farmers") or {}

            p_item = {
                "parcel_id": row.get("parcel_id"),
                "parcel_name": p_data.get("name") or "Parcelle",
                "farmer_id": p_data.get("farmer_id"),
                "farmer_name": farmer_data.get("full_name") or "Agriculteur",
                "farmer_phone": farmer_data.get("phone"),
                "cooperative_id": row.get("cooperative_id"),
                "distance_m": float(row.get("distance_m", 0)),
            }

            if f_id not in fires_by_id:
                fires_by_id[f_id] = {
                    "fire_id": f_id,
                    "external_id": f_id,
                    "parcel_id": row.get("parcel_id"),
                    "parcel_name": p_item["parcel_name"],
                    "farmer_id": p_item["farmer_id"],
                    "farmer_name": p_item["farmer_name"],
                    "farmer_phone": p_item["farmer_phone"],
                    "cooperative_id": row.get("cooperative_id"),
                    "distance_m": float(row.get("distance_m", 0)),
                    "latitude": row.get("fire_latitude"),
                    "longitude": row.get("fire_longitude"),
                    "fire_latitude": row.get("fire_latitude"),
                    "fire_longitude": row.get("fire_longitude"),
                    "detected_at": row.get("fire_detected_at"),
                    "fire_detected_at": row.get("fire_detected_at"),
                    "confidence": row.get("fire_confidence") or "nominal",
                    "frp": row.get("fire_frp"),
                    "fire_frp": row.get("fire_frp"),
                    "affected_parcels": [p_item],
                }
            else:
                fires_by_id[f_id]["affected_parcels"].append(p_item)
                if float(row.get("distance_m", 0)) < fires_by_id[f_id]["distance_m"]:
                    fires_by_id[f_id]["parcel_id"] = row.get("parcel_id")
                    fires_by_id[f_id]["parcel_name"] = p_item["parcel_name"]
                    fires_by_id[f_id]["farmer_id"] = p_item["farmer_id"]
                    fires_by_id[f_id]["farmer_name"] = p_item["farmer_name"]
                    fires_by_id[f_id]["farmer_phone"] = p_item["farmer_phone"]
                    fires_by_id[f_id]["cooperative_id"] = row.get("cooperative_id")
                    fires_by_id[f_id]["distance_m"] = float(row.get("distance_m", 0))

        return list(fires_by_id.values())

    @staticmethod
    def get_parcels(owner_id):
        """
        Récupère toutes les parcelles géométriques
        appartenant à l'utilisateur.
        """

        repository = ParcelRepository(
            current_app.supabase
        )

        parcels = repository.get_all_by_owner(owner_id)

        if not parcels:
            raise ValueError(
                "Aucune parcelle trouvée pour cet utilisateur"
            )

        result = []

        for parcel in parcels:

            geom = parcel.get("geom")

            if not geom:
                continue

            try:
                geometry = shape(geom)
            except Exception:
                continue

            if geometry.is_empty:
                continue

            if not geometry.is_valid:
                continue

            result.append({
                "parcel": parcel,
                "geometry": geometry,
            })

        if not result:
            raise ValueError(
                "Aucune géométrie de parcelle disponible"
            )

        return result

    @staticmethod
    def get_parcel_bbox(
        geometry,
        radius_km
    ):
        """
        Construit une bounding box autour d'une parcelle
        avec une marge correspondant au rayon demandé.
        """

        min_x, min_y, max_x, max_y = geometry.bounds

        center_latitude = (
            min_y + max_y
        ) / 2

        radius_m = radius_km * 1000

        lat_margin = radius_m / 111320

        cos_lat = cos(
            radians(center_latitude)
        )

        if abs(cos_lat) < 0.01:
            raise ValueError(
                "Latitude incompatible avec le calcul de la zone"
            )

        lon_margin = (
            radius_m
            / (111320 * abs(cos_lat))
        )

        return {
            "west": min_x - lon_margin,
            "south": min_y - lat_margin,
            "east": max_x + lon_margin,
            "north": max_y + lat_margin,
        }

    @staticmethod
    def get_utm_transformer(
        geometry
    ):
        """
        Détermine automatiquement la zone UTM
        correspondant à la parcelle.
        """

        centroid = geometry.centroid

        longitude = centroid.x
        latitude = centroid.y

        zone = int(
            (longitude + 180) / 6
        ) + 1

        if latitude >= 0:
            epsg = 32600 + zone
        else:
            epsg = 32700 + zone

        return Transformer.from_crs(
            "EPSG:4326",
            f"EPSG:{epsg}",
            always_xy=True
        )

    @staticmethod
    def calculate_fire_distance(
        fire_latitude,
        fire_longitude,
        parcel_geometry
    ):
        """
        Calcule la distance en mètres entre un feu
        et la géométrie de la parcelle.
        """

        transformer = FireService.get_utm_transformer(
            parcel_geometry
        )

        projected_parcel = transform(
            transformer.transform,
            parcel_geometry
        )

        fire_point = Point(
            fire_longitude,
            fire_latitude
        )

        projected_fire = transform(
            transformer.transform,
            fire_point
        )

        return projected_parcel.distance(
            projected_fire
        )

    @staticmethod
    def create_external_id(fire):
        """
        Crée un identifiant stable pour une détection NASA.
        """

        return (
            f"{fire['satellite']}-"
            f"{fire['instrument']}-"
            f"{fire['acq_date']}-"
            f"{fire['acq_time']}-"
            f"{fire['latitude']}-"
            f"{fire['longitude']}-"
            f"{fire['scan']}-"
            f"{fire['track']}"
        )

    @staticmethod
    def filter_fire_for_parcel(
        fire,
        parcel,
        geometry,
        radius_km
    ):
        """
        Vérifie si un feu est suffisamment proche
        d'une parcelle.

        Retourne le feu enrichi si le feu est dans
        le rayon, sinon None.
        """

        try:
            latitude = float(
                fire["latitude"]
            )

            longitude = float(
                fire["longitude"]
            )

        except (
            KeyError,
            TypeError,
            ValueError
        ):
            return None

        try:
            distance_m = (
                FireService.calculate_fire_distance(
                    latitude,
                    longitude,
                    geometry
                )
            )
        except Exception:
            return None

        radius_m = radius_km * 1000

        if distance_m > radius_m:
            return None

        result = dict(fire)

        result["parcel_id"] = parcel.get(
            "uuid"
        )

        result["cooperative_id"] = parcel.get(
            "cooperative_id"
        )

        result["distance_m"] = round(
            distance_m,
            2
        )

        result["external_id"] = (
            FireService.create_external_id(
                fire
            )
        )

        return result

    @staticmethod
    def fetch_fires_for_parcel(
        parcel,
        geometry,
        radius_km,
        days
    ):
        """
        Interroge NASA FIRMS uniquement autour
        d'une parcelle.
        """

        bbox = FireService.get_parcel_bbox(
            geometry,
            radius_km
        )

        print(
            "📍 Recherche NASA autour de la parcelle :",
            parcel.get("uuid")
        )

        print(
            "   Bounding box :",
            bbox
        )

        fires = FirmsService.get_fires(
            west=bbox["west"],
            south=bbox["south"],
            east=bbox["east"],
            north=bbox["north"],
            days=days
        )

        print(
            "🔥 NASA :",
            len(fires),
            "détections pour cette parcelle"
        )

        return fires

    @staticmethod
    def get_fires_from_nasa(
        owner_id,
        radius_km=5,
        days=1
    ):
        """
        Recherche les feux NASA autour des parcelles
        de l'utilisateur.

        Étapes :
        1. Récupération des parcelles géométriques.
        2. Détermination de l'emprise géographique globale.
        3. Requête NASA FIRMS groupée ou par parcelle.
        4. Filtrage précis par distance métrique (projection UTM).
        5. Suppression des doublons et sélection de la parcelle la plus proche.
        6. Enregistrement des détections dans la base de données.
        7. Déclenchement automatique des alertes pour les parcelles impactées.
        8. Retour des feux enrichis au frontend.
        """

        try:
            parcels = FireService.get_parcels(owner_id)
        except ValueError as e:
            print("ℹ️ Aucune parcelle géométrique trouvée :", e)
            return []

        if not parcels:
            return []

        # -------------------------------------------------------------
        # Étape 2 & 3 : Calcul de l'emprise globale
        # -------------------------------------------------------------
        min_x = min(item["geometry"].bounds[0] for item in parcels)
        min_y = min(item["geometry"].bounds[1] for item in parcels)
        max_x = max(item["geometry"].bounds[2] for item in parcels)
        max_y = max(item["geometry"].bounds[3] for item in parcels)

        center_lat = (min_y + max_y) / 2
        radius_m = radius_km * 1000
        lat_margin = radius_m / 111320
        cos_lat = max(abs(cos(radians(center_lat))), 0.01)
        lon_margin = radius_m / (111320 * cos_lat)

        span_x = (max_x - min_x) + (2 * lon_margin)
        span_y = (max_y - min_y) + (2 * lat_margin)

        all_nasa_fires = []

        if span_x <= 4.0 and span_y <= 4.0:
            unified_west = min_x - lon_margin
            unified_south = min_y - lat_margin
            unified_east = max_x + lon_margin
            unified_north = max_y + lat_margin

            print(f"📍 Recherche NASA FIRMS globale (emprise {span_x:.2f}° x {span_y:.2f}°) : {days}j")
            try:
                all_nasa_fires = FirmsService.get_fires(
                    west=unified_west,
                    south=unified_south,
                    east=unified_east,
                    north=unified_north,
                    days=days
                )
            except Exception as e:
                print("❌ Erreur NASA FIRMS globale :", e)
                all_nasa_fires = []
        else:
            # Si les parcelles sont très dispersées, requêtes par parcelle
            print(f"📍 Parcelles dispersées ({len(parcels)} parcelles), requêtes individuelles...")
            seen_external_ids = set()
            for item in parcels:
                p_fires = FireService.fetch_fires_for_parcel(
                    parcel=item["parcel"],
                    geometry=item["geometry"],
                    radius_km=radius_km,
                    days=days
                )
                for f in p_fires:
                    ext_id = FireService.create_external_id(f)
                    if ext_id not in seen_external_ids:
                        seen_external_ids.add(ext_id)
                        all_nasa_fires.append(f)

        print(f"🔥 NASA FIRMS : {len(all_nasa_fires)} détections brutes dans la zone")

        # -------------------------------------------------------------
        # Étape 4 : Filtrage précis par distance avec les parcelles
        # -------------------------------------------------------------
        all_nearby_fires = {}

        for item in parcels:
            parcel = item["parcel"]
            geometry = item["geometry"]
            p_min_x, p_min_y, p_max_x, p_max_y = geometry.bounds

            p_lat_margin = radius_m / 111320
            p_lon_margin = radius_m / (111320 * max(abs(cos(radians((p_min_y + p_max_y) / 2))), 0.01))

            bbox_west = p_min_x - p_lon_margin
            bbox_south = p_min_y - p_lat_margin
            bbox_east = p_max_x + p_lon_margin
            bbox_north = p_max_y + p_lat_margin

            for fire in all_nasa_fires:
                try:
                    f_lat = float(fire["latitude"])
                    f_lon = float(fire["longitude"])
                except (KeyError, TypeError, ValueError):
                    continue

                # Pré-filtrage rapide Bounding Box
                if not (bbox_west <= f_lon <= bbox_east and bbox_south <= f_lat <= bbox_north):
                    continue

                nearby_fire = FireService.filter_fire_for_parcel(
                    fire=fire,
                    parcel=parcel,
                    geometry=geometry,
                    radius_km=radius_km
                )

                if nearby_fire is None:
                    continue

                ext_id = nearby_fire["external_id"]
                p_item = {
                    "parcel_id": parcel.get("uuid"),
                    "parcel_name": parcel.get("name"),
                    "distance_m": nearby_fire["distance_m"]
                }

                existing = all_nearby_fires.get(ext_id)
                if existing is None:
                    nearby_fire["affected_parcels"] = [p_item]
                    all_nearby_fires[ext_id] = nearby_fire
                else:
                    existing_parcels = existing.setdefault("affected_parcels", [])
                    if not any(ap.get("parcel_id") == p_item["parcel_id"] for ap in existing_parcels):
                        existing_parcels.append(p_item)
                    if nearby_fire["distance_m"] < existing["distance_m"]:
                        existing["parcel_id"] = parcel.get("uuid")
                        existing["cooperative_id"] = parcel.get("cooperative_id")
                        existing["distance_m"] = nearby_fire["distance_m"]

        nearby_fires = list(all_nearby_fires.values())
        print(f"🔥 Feux dans le rayon ({radius_km} km) : {len(nearby_fires)}")

        # -------------------------------------------------------------
        # Étape 5 & 6 : Normalisation et Enregistrement dans Supabase
        # -------------------------------------------------------------
        saved_count = 0
        for fire in nearby_fires:
            # Normalisation des champs pour compatibilité frontend
            f_lat = float(fire.get("latitude", 0))
            f_lon = float(fire.get("longitude", 0))
            acq_date = fire.get("acq_date", "")
            acq_time = fire.get("acq_time", "")
            iso_detected = f"{acq_date}T{acq_time[:2]}:{acq_time[2:]}:00Z" if len(acq_time) >= 4 else None

            fire["fire_latitude"] = f_lat
            fire["fire_longitude"] = f_lon
            fire["latitude"] = f_lat
            fire["longitude"] = f_lon
            fire["fire_frp"] = fire.get("frp")
            fire["fire_confidence"] = fire.get("confidence")
            fire["fire_detected_at"] = iso_detected
            fire["detected_at"] = iso_detected

            try:
                saved = FireService.save_fire(fire)
                if saved and isinstance(saved, dict) and "uuid" in saved:
                    fire["fire_id"] = saved["uuid"]
                    if saved.get("detected_at"):
                        fire["fire_detected_at"] = saved["detected_at"]
                        fire["detected_at"] = saved["detected_at"]
                saved_count += 1
            except Exception as error:
                print("❌ Erreur enregistrement feu :", repr(error))

        print(f"💾 Feux enregistrés : {saved_count}")

        # -------------------------------------------------------------
        # Étape 7 : Déclenchement automatique des alertes
        # -------------------------------------------------------------
        if nearby_fires:
            try:
                from app.repositories.fire_alert_repository import FireAlertRepository
                alert_count = FireAlertRepository.create_alerts(
                    radius_m=radius_km * 1000,
                    period_hours=max(days * 24, 24)
                )
                print(f"🔔 Alertes créées automatiquement : {alert_count}")
            except Exception as alert_err:
                print("⚠️ Erreur création automatique alertes :", alert_err)

        return nearby_fires