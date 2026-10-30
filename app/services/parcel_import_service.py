import os
import tempfile
import zipfile

import geopandas as gpd
from shapely.geometry import mapping
from shapely import force_2d
from shapely.validation import explain_validity


class ParcelImportService:

    def __init__(self, repository):
        self.repository = repository

    ALLOWED_EXTENSIONS = {
        ".kml",
        ".gpkg",
        ".zip",
    }

    def read_file(self, file_path):
        """
        Lit un fichier géographique.

        Formats supportés :
        - KML
        - GeoPackage
        - ZIP contenant un Shapefile
        """

        extension = os.path.splitext(
            file_path
        )[1].lower()

        if extension not in self.ALLOWED_EXTENSIONS:
            raise ValueError(
                "Format de fichier non supporté. "
                "Formats acceptés : KML, GeoPackage et Shapefile ZIP."
            )

        if extension in (".kml", ".gpkg"):

            try:
                gdf = gpd.read_file(
                    file_path
                )

            except Exception as e:
                raise ValueError(
                    f"Impossible de lire le fichier géographique : {e}"
                )

            if gdf.empty:
                raise ValueError(
                    "Le fichier géographique ne contient aucune donnée."
                )

            return gdf

        if extension == ".zip":

            with tempfile.TemporaryDirectory() as temp_dir:

                try:

                    with zipfile.ZipFile(
                        file_path,
                        "r"
                    ) as zip_ref:

                        # Vérification du ZIP
                        if zip_ref.testzip() is not None:
                            raise ValueError(
                                "Le fichier ZIP est corrompu."
                            )

                        zip_ref.extractall(
                            temp_dir
                        )

                except zipfile.BadZipFile:
                    raise ValueError(
                        "Le fichier ZIP est invalide ou corrompu."
                    )

                # Recherche du fichier .shp
                shapefile_path = None

                for root, dirs, files in os.walk(
                    temp_dir
                ):

                    for filename in files:

                        if filename.lower().endswith(
                            ".shp"
                        ):
                            shapefile_path = os.path.join(
                                root,
                                filename
                            )
                            break

                    if shapefile_path:
                        break

                if not shapefile_path:
                    raise ValueError(
                        "Le fichier ZIP ne contient aucun "
                        "Shapefile (.shp)."
                    )

                try:

                    gdf = gpd.read_file(
                        shapefile_path
                    )

                except Exception as e:
                    raise ValueError(
                        f"Impossible de lire le Shapefile : {e}"
                    )

                if gdf.empty:
                    raise ValueError(
                        "Le Shapefile ne contient aucune donnée."
                    )

                return gdf

    def prepare_geometries(self, gdf):
        """
        Prépare et valide les géométries
        avant leur insertion dans PostGIS.
        """

        if gdf.crs is None:
            raise ValueError(
                "Le fichier ne possède pas de système "
                "de coordonnées (CRS)."
            )

        # Conversion vers WGS84 / EPSG:4326
        if gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        prepared = []

        for index, row in gdf.iterrows():

            geometry = row.geometry

            if geometry is None:
                raise ValueError(
                    f"La géométrie de la ligne {index} est vide."
                )

            if geometry.geom_type not in (
                "Polygon",
                "MultiPolygon"
            ):
                raise ValueError(
                    f"La géométrie de la ligne {index} "
                    f"est de type {geometry.geom_type}. "
                    "Seuls Polygon et MultiPolygon sont acceptés."
                )

            if not geometry.is_valid:
                raise ValueError(
                    f"Géométrie invalide à la ligne {index} : "
                    f"{explain_validity(geometry)}"
                )

            # Suppression de la dimension Z
            geometry_2d = geometry

            if geometry.has_z:
                geometry_2d = force_2d(geometry)

            # Récupération du nom si disponible dans les attributs du fichier SIG
            row_dict = row.to_dict() if hasattr(row, "to_dict") else {}
            feature_name = None
            for key in ("name", "nom", "parcel_name", "nom_parcelle", "NAME", "NOM"):
                val = row_dict.get(key)
                if val and str(val).strip() and str(val).lower() != "nan":
                    feature_name = str(val).strip()
                    break

            prepared.append(
                {
                    "geometry": mapping(
                        geometry_2d
                    ),
                    "name": feature_name
                }
            )

        return prepared

    def import_file(
        self,
        file_path,
        cooperative_id,
        farmer_id,
        owner_id,
        default_name=None
    ):
        """
        Lit le fichier géographique,
        prépare les géométries,
        puis crée les parcelles.
        """

        gdf = self.read_file(
            file_path
        )

        geometries = self.prepare_geometries(
            gdf
        )

        # Vérification d'unicité des noms de parcelles
        for geom_item in geometries:
            item_name = geom_item.get("name") or default_name
            if item_name and str(item_name).strip():
                clean_name = str(item_name).strip()
                existing = self.repository.find_by_name(cooperative_id, clean_name)
                if existing:
                    raise ValueError(
                        f"Une parcelle nommée '{clean_name}' existe déjà dans cette coopérative. Veuillez choisir un autre nom."
                    )

        parcels = self.repository.create_many_with_geojson(
            cooperative_id,
            farmer_id,
            geometries,
            owner_id,
            default_name=default_name
        )

        return parcels