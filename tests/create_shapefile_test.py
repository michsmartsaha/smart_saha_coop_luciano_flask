import geopandas as gpd
from shapely.geometry import Polygon


polygon = Polygon([
    (47.2231, -21.4502),
    (47.2260, -21.4502),
    (47.2260, -21.4515),
    (47.2231, -21.4515),
    (47.2231, -21.4502)
])


gdf = gpd.GeoDataFrame(
    {
        "name": ["Parcelle Test ZIP"]
    },
    geometry=[polygon],
    crs="EPSG:4326"
)


output_path = "tests/data/parcelles_test.shp"

gdf.to_file(
    output_path,
    driver="ESRI Shapefile"
)

print("Shapefile créé :", output_path)
