from app.services.parcel_import_service import ParcelImportService


service = ParcelImportService()

file_path = "tests/data/parcelle_test.kml"

gdf = service.read_file(file_path)

print("Nombre de lignes :", len(gdf))
print("CRS :", gdf.crs)

geometries = service.prepare_geometries(gdf)

print("Nombre de géométries :", len(geometries))
print("Première géométrie :")
print(geometries[0])
