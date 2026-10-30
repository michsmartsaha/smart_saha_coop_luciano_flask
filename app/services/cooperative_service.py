class CooperativeService:

    def __init__(self, repository):
        self.repository = repository

    def get_all_cooperatives(self, owner_id):
        return self.repository.get_all(owner_id)

    def get_cooperative(self, cooperative_id, owner_id):
        return self.repository.get_by_id(
            cooperative_id,
            owner_id
        )

    def create_cooperative(self, data, owner_id):

        if not data.get("name"):
            raise ValueError(
                "Le nom de la coopérative est obligatoire"
            )

        if not data.get("president_name"):
            raise ValueError(
                "Le nom du président est obligatoire"
            )

        if not data.get("legal_status"):
            raise ValueError(
                "Le statut juridique est obligatoire"
            )

        if not data.get("year_of_creation"):
            raise ValueError(
                "L'année de création est obligatoire"
            )

        if not data.get("status"):
            raise ValueError(
                "Le statut de la coopérative est obligatoire"
            )

        if not data.get("main_crop"):
            raise ValueError(
                "La culture principale est obligatoire"
            )

        # L'utilisateur connecté devient automatiquement
        # propriétaire de la coopérative.
        data["owner"] = owner_id

        return self.repository.create(data)

    def update_cooperative(
        self,
        cooperative_id,
        owner_id,
        data
    ):

        if not data:
            raise ValueError(
                "Aucune donnée à modifier"
            )

        # Ces champs ne doivent jamais être modifiés
        # par le client.
        data.pop("owner", None)
        data.pop("uuid", None)
        data.pop("created_at", None)

        return self.repository.update(
            cooperative_id,
            owner_id,
            data
        )

    def delete_cooperative(
        self,
        cooperative_id,
        owner_id
    ):
        return self.repository.delete(
            cooperative_id,
            owner_id
        )