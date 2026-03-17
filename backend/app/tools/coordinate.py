"""coordinate 工具组：坐标转换、UTM分区

本地 geopandas/pyproj 实现。
"""

import json

import geopandas as gpd
from langchain_core.tools import tool


@tool
async def transform_crs(
    data_ref_id: str,
    target_crs: str = "EPSG:4326",
) -> dict:
    """坐标参考系转换。

    使用场景：当用户说"转换坐标"、"投影变换"、"转WGS84"时使用。

    示例：transform_crs(data_ref_id="ref_data", target_crs="EPSG:3857")
    """
    from app.tools._context import get_tool_context

    ctx = get_tool_context()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    gdf = gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")
    gdf_proj = gdf.to_crs(target_crs)
    result_geojson = json.loads(gdf_proj.to_json())
    ref_id = ctx.register(result_geojson, source=f"transform_crs:{data_ref_id}→{target_crs}")
    summary = ctx.summary(ref_id)
    return {
        "data_ref_id": ref_id,
        **summary,
        "summary": f"坐标转换到 {target_crs} 完成，{summary.get('feature_count', '?')}个要素",
    }


@tool
async def convert_point(
    longitude: float,
    latitude: float,
    source_crs: str = "EPSG:4326",
    target_crs: str = "EPSG:3857",
) -> dict:
    """单点坐标转换：将一个经纬度坐标从源坐标系转换到目标坐标系。

    使用场景：当用户已知某个点的坐标，想转到其他坐标系（如CGCS2000、UTM、Web墨卡托等）时使用。
    不需要 data_ref_id，直接传入坐标即可。

    常用 EPSG 代码：
    - EPSG:4326  = WGS84 经纬度
    - EPSG:4490  = CGCS2000 经纬度（与WGS84差异 <0.1m，实际可视为相同）
    - EPSG:3857  = Web 墨卡托（米）
    - EPSG:4547  = CGCS2000 / 3-degree Gauss-Kruger zone 39（适用于116°E附近）
    - EPSG:32650 = WGS84 / UTM zone 50N

    示例：convert_point(longitude=116.3912, latitude=39.9078, target_crs="EPSG:4490")
    """
    from pyproj import Transformer

    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    x, y = transformer.transform(longitude, latitude)

    return {
        "source_crs": source_crs,
        "target_crs": target_crs,
        "input": {"longitude": longitude, "latitude": latitude},
        "output": {"x": round(x, 8), "y": round(y, 8)},
        "summary": f"({longitude}, {latitude}) [{source_crs}] → ({round(x, 8)}, {round(y, 8)}) [{target_crs}]",
    }


@tool
async def get_utm_zone(
    longitude: float,
    latitude: float,
) -> dict:
    """根据经纬度获取UTM分区号和EPSG代码。

    使用场景：当用户需要知道某个位置应该使用哪个UTM投影时使用。

    示例：get_utm_zone(longitude=116.39, latitude=39.91)
    """
    zone_number = int((longitude + 180) / 6) + 1
    is_north = latitude >= 0
    epsg = 32600 + zone_number if is_north else 32700 + zone_number
    hemisphere = "N" if is_north else "S"
    return {
        "zone_number": zone_number,
        "hemisphere": hemisphere,
        "zone_letter": f"{zone_number}{hemisphere}",
        "epsg": f"EPSG:{epsg}",
        "summary": f"UTM Zone {zone_number}{hemisphere} (EPSG:{epsg})",
    }
