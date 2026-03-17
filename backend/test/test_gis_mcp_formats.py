"""检查 gis-mcp 各工具的 geometry 参数解析方式（WKT vs GeoJSON vs GeoDataFrame）"""
import inspect
from gis_mcp import (
    get_centroid, buffer, convex_hull, simplify, voronoi,
    project_geometry, calculate_geodetic_distance, sjoin_gpd,
    overlay_gpd, clip_vector,
)

tools = [
    get_centroid, buffer, convex_hull, simplify, voronoi,
    project_geometry, calculate_geodetic_distance, sjoin_gpd,
    overlay_gpd, clip_vector,
]

for t in tools:
    src = inspect.getsource(t.fn)
    # 检查解析方式
    uses_wkt = "wkt.loads" in src or "wkt_loads" in src
    uses_gpd = "gpd.read_file" in src or "GeoDataFrame" in src or "from_geojson" in src
    uses_json = "json.loads" in src or "geojson" in src.lower()
    print(f"[{t.name}]  WKT={uses_wkt}  GPD={uses_gpd}  JSON={uses_json}")
    # 显示前5行函数体
    lines = src.strip().split("\n")
    for line in lines[:15]:
        print(f"  {line}")
    print()
