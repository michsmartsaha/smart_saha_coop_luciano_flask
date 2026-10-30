from app.services.parcel_import_service import ParcelImportService


service = ParcelImportService(
    repository=None
)


file_path = "tests/data/parcelles_test.zip"


gdf = service.read_file(
    file_path
)


print("Nombre de lignes :", len(gdf))

print("CRS :", gdf.crs)

print("Type de géométrie :")
print(gdf.geometry.geom_type.tolist())


geometries = service.prepare_geometries(
    gdf
)


print("Nombre de géométries :", len(geometries))

print("Première géométrie :")
print(geometries[0])
