"""measurement 工具组：距离计算、面积计算、字段统计

本地 pyproj/shapely 实现。
"""

from typing import Literal, Optional

from langchain_core.tools import tool


@tool
async def distance_calc(
    ref_a: str,
    ref_b: str,
    unit: Literal["m", "km"] = "m",
) -> dict:
    """计算两组要素质心之间的测地线距离。

    使用场景：当用户说"两点之间的距离"、"A到B有多远"时使用。

    示例：distance_calc(ref_a="ref_schools", ref_b="ref_hospitals", unit="km")
    """
    from pyproj import Geod
    from shapely.geometry import shape
    from app.tools._context import get_tool_context

    ctx = get_tool_context()
    geojson_a = ctx.get(ref_a)
    geojson_b = ctx.get(ref_b)
    if geojson_a is None:
        return {"error": f"data_ref_id '{ref_a}' 不存在"}
    if geojson_b is None:
        return {"error": f"data_ref_id '{ref_b}' 不存在"}

    # 取各数据集的质心
    def _centroid(geojson):
        from shapely.ops import unary_union
        geoms = [shape(f["geometry"]) for f in geojson.get("features", []) if f.get("geometry")]
        return unary_union(geoms).centroid if geoms else None

    ca, cb = _centroid(geojson_a), _centroid(geojson_b)
    if ca is None or cb is None:
        return {"error": "无法计算质心，数据中没有有效几何"}

    geod = Geod(ellps="WGS84")
    _, _, dist_m = geod.inv(ca.x, ca.y, cb.x, cb.y)
    dist_m = abs(dist_m)
    dist = dist_m / 1000 if unit == "km" else dist_m

    return {
        "distance": round(dist, 4),
        "unit": unit,
        "point_a": [round(ca.x, 6), round(ca.y, 6)],
        "point_b": [round(cb.x, 6), round(cb.y, 6)],
        "summary": f"两组数据质心距离: {dist:.2f} {unit}",
    }


@tool
async def area_calc(
    data_ref_id: str,
    unit: Literal["m2", "km2", "ha"] = "m2",
) -> dict:
    """计算面要素的面积。

    使用场景：当用户说"面积是多少"、"这个区域有多大"时使用。

    示例：area_calc(data_ref_id="ref_buffer", unit="km2")
    """
    from shapely.geometry import shape
    from pyproj import Geod
    from app.tools._context import get_tool_context

    ctx = get_tool_context()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    geod = Geod(ellps="WGS84")
    features = geojson.get("features", [])
    areas = []
    for f in features:
        geom = f.get("geometry")
        if not geom:
            continue
        try:
            s = shape(geom)
            abs_area, _ = geod.geometry_area_perimeter(s)
            areas.append(abs(abs_area))
        except Exception:
            continue

    total_m2 = sum(areas)
    divisor = {"m2": 1, "km2": 1e6, "ha": 1e4}.get(unit, 1)
    total = total_m2 / divisor
    avg = total / len(areas) if areas else 0

    return {
        "feature_count": len(areas),
        "total_area": round(total, 4),
        "average_area": round(avg, 4),
        "min_area": round(min(areas) / divisor, 4) if areas else 0,
        "max_area": round(max(areas) / divisor, 4) if areas else 0,
        "unit": unit,
        "summary": f"面积统计：{len(areas)}个要素，总面积 {total:.2f} {unit}，均值 {avg:.2f} {unit}",
    }


@tool
async def field_statistics(
    data_ref_id: str,
    field_name: str = "",
    stat_type: Literal["sum", "mean", "min", "max", "count", "std", "all"] = "all",
) -> dict:
    """对要素属性字段进行统计。如果 field_name 为空，返回所有可用字段列表。

    使用场景：当用户说"平均值"、"总计"、"最大最小"、"有哪些字段"时使用。

    示例：field_statistics(data_ref_id="ref_poi", field_name="population", stat_type="sum")
    """
    from app.tools._context import get_tool_context

    ctx = get_tool_context()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    features = geojson.get("features", [])
    if not features:
        return {"error": "数据中没有要素"}

    all_fields = {}
    for f in features[:100]:
        for k, v in (f.get("properties") or {}).items():
            if k not in all_fields:
                all_fields[k] = type(v).__name__ if v is not None else "null"

    if not field_name:
        return {
            "fields": all_fields,
            "feature_count": len(features),
            "summary": f"共{len(features)}个要素，{len(all_fields)}个属性字段: {', '.join(list(all_fields.keys())[:15])}",
        }

    values = []
    for f in features:
        v = (f.get("properties") or {}).get(field_name)
        if v is not None:
            try:
                values.append(float(v))
            except (ValueError, TypeError):
                pass

    if not values:
        str_values = []
        for f in features:
            v = (f.get("properties") or {}).get(field_name)
            if v is not None:
                str_values.append(str(v))
        unique = list(set(str_values))
        return {
            "field": field_name,
            "type": "categorical",
            "count": len(str_values),
            "unique_count": len(unique),
            "sample_values": unique[:20],
            "summary": f"字段 {field_name} 为分类型，共{len(str_values)}条，{len(unique)}个唯一值",
        }

    import statistics as stat_mod
    result = {
        "field": field_name,
        "type": "numeric",
        "count": len(values),
        "sum": round(sum(values), 4),
        "mean": round(stat_mod.mean(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "std": round(stat_mod.stdev(values), 4) if len(values) > 1 else 0,
    }
    result["summary"] = (
        f"字段 {field_name}：计数{result['count']}，"
        f"合计{result['sum']}，均值{result['mean']}，"
        f"范围[{result['min']}, {result['max']}]"
    )
    return result


@tool
async def enrich_geometry_fields(
    data_ref_id: str,
    fields: list[str] = ["_area_m2", "_perimeter_m", "_centroid_lon", "_centroid_lat"],
) -> dict:
    """为每个要素计算几何属性（面积、周长、长度、质心坐标）并写入 properties。

    使用场景：当数据缺少面积/长度等数值字段时，用此工具补充计算字段，
    之后可用于 generate_choropleth 或 generate_chart 做可视化。

    可选 fields：_area_m2, _area_km2, _perimeter_m, _length_m, _centroid_lon, _centroid_lat

    示例：enrich_geometry_fields(data_ref_id="ref_001", fields=["_area_m2", "_perimeter_m"])
    """
    import copy
    from shapely.geometry import shape
    from pyproj import Geod
    from app.tools._context import get_tool_context

    ctx = get_tool_context()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    geod = Geod(ellps="WGS84")
    enriched = copy.deepcopy(geojson)
    features = enriched.get("features", [])
    computed_count = 0

    field_set = set(fields)

    for f in features:
        geom = f.get("geometry")
        if not geom:
            continue
        props = f.setdefault("properties", {})
        try:
            s = shape(geom)
        except Exception:
            continue

        computed_count += 1
        geom_type = geom.get("type", "")

        # 面积 + 周长（面要素）
        if geom_type in ("Polygon", "MultiPolygon"):
            area_m2, perimeter_m = geod.geometry_area_perimeter(s)
            area_m2 = abs(area_m2)
            perimeter_m = abs(perimeter_m)
            if "_area_m2" in field_set:
                props["_area_m2"] = round(area_m2, 2)
            if "_area_km2" in field_set:
                props["_area_km2"] = round(area_m2 / 1e6, 6)
            if "_perimeter_m" in field_set:
                props["_perimeter_m"] = round(perimeter_m, 2)

        # 长度（线要素）
        if geom_type in ("LineString", "MultiLineString"):
            length_m = geod.geometry_length(s)
            if "_length_m" in field_set:
                props["_length_m"] = round(abs(length_m), 2)

        # 质心坐标（所有几何类型）
        c = s.centroid
        if "_centroid_lon" in field_set:
            props["_centroid_lon"] = round(c.x, 6)
        if "_centroid_lat" in field_set:
            props["_centroid_lat"] = round(c.y, 6)

    ref_id = ctx.register(enriched, source=f"enriched:{data_ref_id}")
    summary = ctx.summary(ref_id)
    added_fields = [f for f in fields if f.startswith("_")]
    return {
        "data_ref_id": ref_id,
        **summary,
        "added_fields": added_fields,
        "enriched_count": computed_count,
        "summary": f"已为{computed_count}个要素计算并写入字段: {', '.join(added_fields)}",
    }
