from shapely.geometry import shape
from shapely.validation import explain_validity


class ParcelService:

    def __init__(self, repository):
        self.repository = repository

    def get_all_parcels(self, cooperative_id):

        return self.repository.get_all(
            cooperative_id
        )

    def get_all_parcels_by_owner(self, owner_id):
        return self.repository.get_all_by_owner(owner_id)

    def get_parcel(
        self,
        parcel_id,
        cooperative_id
    ):

        return self.repository.get_by_id(
            parcel_id,
            cooperative_id
        )

    def create_parcel(
        self,
        data,
        cooperative_id,
        owner_id
    ):

        if not data.get("farmer_id"):
            raise ValueError(
                "L'agriculteur est obligatoire"
            )

        if not data.get("geom"):
            raise ValueError(
                "La géométrie de la parcelle est obligatoire"
            )

        geom = data["geom"]

        # Vérification du type de géométrie
        if geom.get("type") not in (
            "Polygon",
            "MultiPolygon"
        ):
            raise ValueError(
                "La parcelle doit être un Polygon ou un MultiPolygon"
            )

        # Validation de la géométrie avec Shapely
        try:
            geometry = shape(geom)
        except Exception:
            raise ValueError(
                "La géométrie GeoJSON est invalide"
            )

        if geometry.is_empty:
            raise ValueError(
                "La géométrie de la parcelle est vide"
            )

        if not geometry.is_valid:
            raise ValueError(
                f"Géométrie invalide : {explain_validity(geometry)}"
            )

        # Préparation des données
        farmer_id = data["farmer_id"]
        name = data.get("name")
        if name and str(name).strip():
            clean_name = str(name).strip()
            existing = self.repository.find_by_name(cooperative_id, clean_name)
            if existing:
                raise ValueError(
                    f"Une parcelle nommée '{clean_name}' existe déjà dans cette coopérative. Veuillez choisir un autre nom."
                )
            name = clean_name

        return self.repository.create_with_geojson(
            cooperative_id,
            farmer_id,
            geom,
            owner_id,
            name=name
        )

    def update_parcel(self, parcel_id, cooperative_id, data):

        if not data:
            raise ValueError("Aucune donnée à modifier")

        # ---------------------------------------------------------
        # Champs qui ne doivent jamais être modifiés directement
        # ---------------------------------------------------------

        data.pop("uuid", None)
        data.pop("cooperative_id", None)
        data.pop("owner", None)
        data.pop("created_at", None)
        data.pop("area_ha", None)

        # ---------------------------------------------------------
        # Modification de l'agriculteur
        # ---------------------------------------------------------

        if "farmer_id" in data:

            if not data["farmer_id"]:
                raise ValueError(
                    "L'agriculteur est obligatoire"
                )

            farmer_id = data["farmer_id"]

            # Le repository devra vérifier que
            # l'agriculteur appartient bien à la coopérative.
            if not self.repository.farmer_belongs_to_cooperative(
                farmer_id,
                cooperative_id
            ):
                raise ValueError(
                    "L'agriculteur n'appartient pas à cette coopérative"
                )

        # ---------------------------------------------------------
        # Modification du nom
        # ---------------------------------------------------------

        if "name" in data:
            raw_name = data.get("name")
            if raw_name and str(raw_name).strip():
                clean_name = str(raw_name).strip()
                existing = self.repository.find_by_name(
                    cooperative_id, clean_name, exclude_parcel_id=parcel_id
                )
                if existing:
                    raise ValueError(
                        f"Une parcelle nommée '{clean_name}' existe déjà dans cette coopérative. Veuillez choisir un autre nom."
                    )
                data["name"] = clean_name
            else:
                data["name"] = None

        # ---------------------------------------------------------
        # Modification de la géométrie
        # ---------------------------------------------------------

        if "geom" in data:

            geom = data["geom"]

            if not isinstance(geom, dict):
                raise ValueError(
                    "La géométrie doit être un objet GeoJSON"
                )

            if geom.get("type") not in (
                "Polygon",
                "MultiPolygon"
            ):
                raise ValueError(
                    "La parcelle doit être un Polygon ou un MultiPolygon"
                )

            try:
                geometry = shape(geom)
            except Exception:
                raise ValueError(
                    "La géométrie GeoJSON est invalide"
                )

            if geometry.is_empty:
                raise ValueError(
                    "La géométrie de la parcelle est vide"
                )

            if not geometry.is_valid:
                raise ValueError(
                    f"Géométrie invalide : "
                    f"{explain_validity(geometry)}"
                )

        # ---------------------------------------------------------
        # Rien à modifier
        # ---------------------------------------------------------

        if not data:
            raise ValueError(
                "Aucune donnée valide à modifier"
            )

        # ---------------------------------------------------------
        # Géométrie présente
        # ---------------------------------------------------------

        if "geom" in data:

            geom = data.pop("geom")

            parcel = self.repository.update_with_geojson(
                parcel_id,
                cooperative_id,
                geom
            )

            # Si d'autres données sont également modifiées (ex: name, farmer_id)
            if data:
                parcel = self.repository.update(
                    parcel_id,
                    cooperative_id,
                    data
                )

            return parcel

        # ---------------------------------------------------------
        # Modification classique
        # ---------------------------------------------------------

        return self.repository.update(
            parcel_id,
            cooperative_id,
            data
        )

    def delete_parcel(
        self,
        parcel_id,
        cooperative_id
    ):

        return self.repository.delete(
            parcel_id,
            cooperative_id
        )

    def get_parcel_details(self, parcel_id, cooperative_id):
        return self.repository.get_details(
            parcel_id,
            cooperative_id
        )