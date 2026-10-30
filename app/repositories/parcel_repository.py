class ParcelRepository:

    def __init__(self, supabase):
        self.supabase = supabase

    def get_all(self, cooperative_id):

        response = (
            self.supabase
            .table("parcels")
            .select("*")
            .eq("cooperative_id", cooperative_id)
            .order("created_at", desc=True)
            .execute()
        )

        return response.data

    def get_by_id(self, parcel_id, cooperative_id):
        response = (
            self.supabase
            .table("parcels")
            .select("""
                *,
                cooperative:cooperatives(
                    uuid,
                    name,
                    president_name
                ),
                farmer:farmers(
                    uuid,
                    full_name,
                    gender,
                    year_of_birth,
                    id_card,
                    status
                )
            """)
            .eq("uuid", parcel_id)
            .eq("cooperative_id", cooperative_id)
            .execute()
        )

        return response.data

    def create(self, data):

        response = (
            self.supabase
            .table("parcels")
            .insert(data)
            .execute()
        )

        return response.data

    def create_with_geojson(
        self,
        cooperative_id,
        farmer_id,
        geom,
        owner_id,
        name=None
    ):
        try:
            params = {
                "p_cooperative_id": cooperative_id,
                "p_farmer_id": farmer_id,
                "p_geom": geom,
                "p_owner": owner_id,
            }
            if name is not None:
                params["p_name"] = name

            response = (
                self.supabase
                .rpc("insert_parcel", params)
                .execute()
            )
            return response.data
        except Exception as e:
            err_msg = str(e).lower()
            # Si la fonction insert_parcel dans Postgres n'a pas encore le paramètre p_name
            if "p_name" in err_msg or "schema cache" in err_msg or "could not find" in err_msg:
                fallback_response = (
                    self.supabase
                    .rpc(
                        "insert_parcel",
                        {
                            "p_cooperative_id": cooperative_id,
                            "p_farmer_id": farmer_id,
                            "p_geom": geom,
                            "p_owner": owner_id
                        }
                    )
                    .execute()
                )
                data = fallback_response.data
                if name and isinstance(data, dict) and "uuid" in data:
                    try:
                        self.update(data["uuid"], cooperative_id, {"name": name})
                        data["name"] = name
                    except Exception:
                        pass
                return data
            raise e

    def create_many_with_geojson(
        self,
        cooperative_id,
        farmer_id,
        geometries,
        owner_id,
        default_name=None
    ):

        parcels = []

        for geometry in geometries:
            item_name = geometry.get("name") or default_name
            parcel = self.create_with_geojson(
                cooperative_id,
                farmer_id,
                geometry["geometry"],
                owner_id,
                name=item_name
            )

            parcels.append(parcel)

        return parcels

    def update_with_geojson(
        self,
        parcel_id,
        cooperative_id,
        geom
    ):

        response = (
            self.supabase
            .rpc(
                "update_parcel",
                {
                    "p_parcel_id": parcel_id,
                    "p_cooperative_id": cooperative_id,
                    "p_geom": geom
                }
            )
            .execute()
        )

        return response.data

    def update(
        self,
        parcel_id,
        cooperative_id,
        data
    ):

        response = (
            self.supabase
            .table("parcels")
            .update(data)
            .eq("uuid", parcel_id)
            .eq("cooperative_id", cooperative_id)
            .execute()
        )

        return response.data

    def delete(
        self,
        parcel_id,
        cooperative_id
    ):

        response = (
            self.supabase
            .table("parcels")
            .delete()
            .eq("uuid", parcel_id)
            .eq("cooperative_id", cooperative_id)
            .execute()
        )

        return response.data

    def farmer_belongs_to_cooperative(
        self,
        farmer_id,
        cooperative_id
    ):
        response = (
            self.supabase
            .table("farmers")
            .select("uuid")
            .eq("uuid", farmer_id)
            .eq("cooperative_id", cooperative_id)
            .execute()
        )

        return bool(response.data)

    def find_by_name(self, cooperative_id, name, exclude_parcel_id=None):
        """
        Vérifie si une parcelle portant ce nom existe déjà dans la coopérative
        (comparaison insensible à la casse et aux espaces superflus).
        """
        if not name or not str(name).strip():
            return None

        clean_name = str(name).strip()
        try:
            query = (
                self.supabase
                .table("parcels")
                .select("uuid, name")
                .eq("cooperative_id", cooperative_id)
                .ilike("name", clean_name)
            )
            if exclude_parcel_id:
                query = query.neq("uuid", exclude_parcel_id)

            res = query.execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as e:
            print("⚠️ Exception find_by_name :", e)
            try:
                records = self.get_all(cooperative_id) or []
                for p in records:
                    if exclude_parcel_id and p.get("uuid") == exclude_parcel_id:
                        continue
                    if (p.get("name") or "").strip().lower() == clean_name.lower():
                        return p
            except Exception:
                pass
            return None

    def get_all_by_owner(self, owner_id=None):
        query = (
            self.supabase
            .table("parcels")
            .select("""
                *,
                cooperative:cooperatives(
                    uuid,
                    name,
                    president_name
                ),
                farmer:farmers(
                    uuid,
                    full_name,
                    gender,
                    year_of_birth,
                    id_card,
                    phone,
                    status
                )
            """)
            .order("created_at", desc=True)
        )
        if owner_id:
            query = query.eq("owner", owner_id)

        response = query.execute()
        return response.data

    def get_details(self, parcel_id, cooperative_id):
        try:
            response = (
                self.supabase
                .rpc(
                    "get_parcel_details",
                    {
                        "p_parcel_id": parcel_id,
                        "p_cooperative_id": cooperative_id
                    }
                )
                .execute()
            )

            data = response.data
            if data and isinstance(data, dict) and "name" not in data:
                try:
                    p_row = self.supabase.table("parcels").select("name").eq("uuid", parcel_id).execute()
                    if p_row.data and len(p_row.data) > 0:
                        data["name"] = p_row.data[0].get("name")
                except Exception:
                    pass

            return data
        except Exception:
            records = self.get_by_id(parcel_id, cooperative_id)
            return records[0] if records else None