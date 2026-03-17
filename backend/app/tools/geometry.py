"""geometry 工具组：质心、凸包、简化、泰森多边形

本地 shapely 实现，接受 data_ref_id 参数，结果存回 SessionDataContext。
"""

import copy
from typing import Optional

from langchain_core.tools import tool
from shapely.geometry import shape, mapping
from shapely.ops import unary_union, voronoi_diagram


def _get_ctx():
    from app.tools._context import get_tool_context
    return get_tool_context()


def _load_features(data_ref_id: str):
    ctx = _get_ctx()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return None, ctx, []
    return geojson, ctx, geojson.get("features", [])


@tool
async def centroid(data_ref_id: str) -> dict:
    """计算要素的几何质心。

    使用场景：当用户说"中心点"、"重心"时使用。

    示例：centroid(data_ref_id="ref_buildings")
    """
    geojson, ctx, features = _load_features(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    new_features = []
    for f in features:
        geom = f.get("geometry")
        if not geom:
            continue
        c = shape(geom).centroid
        new_features.append({
            "type": "Feature",
            "geometry": mapping(c),
            "properties": copy.deepcopy(f.get("properties") or {}),
        })

    result_geojson = {"type": "FeatureCollection", "features": new_features}
    ref_id = ctx.register(result_geojson, source=f"centroid:{data_ref_id}")
    summary = ctx.summary(ref_id)
    return {
        "data_ref_id": ref_id,
        **summary,
        "summary": f"计算了{len(new_features)}个质心",
    }


@tool
async def convex_hull(data_ref_id: str) -> dict:
    """计算要素集的凸包（最小外接凸多边形）。

    使用场景：当用户说"外包络"、"凸包"、"最小范围"时使用。

    示例：convex_hull(data_ref_id="ref_poi_points")
    """
    geojson, ctx, features = _load_features(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    geoms = [shape(f["geometry"]) for f in features if f.get("geometry")]
    if not geoms:
        return {"error": "数据中没有有效几何"}

    hull = unary_union(geoms).convex_hull
    result_geojson = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": mapping(hull), "properties": {}}],
    }
    ref_id = ctx.register(result_geojson, source=f"convex_hull:{data_ref_id}")
    summary = ctx.summary(ref_id)
    return {"data_ref_id": ref_id, **summary, "summary": "凸包计算完成"}


@tool
async def simplify_geometry(
    data_ref_id: str,
    tolerance: float = 0.001,
) -> dict:
    """简化几何形状，减少顶点数量。

    使用场景：当用户说"简化"、"减少细节"、"降低精度"时使用。
    tolerance 单位为度（WGS84），0.001≈111米。

    示例：simplify_geometry(data_ref_id="ref_boundary", tolerance=0.01)
    """
    geojson, ctx, features = _load_features(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    new_features = []
    for f in features:
        geom = f.get("geometry")
        if not geom:
            continue
        simplified = shape(geom).simplify(tolerance, preserve_topology=True)
        new_features.append({
            "type": "Feature",
            "geometry": mapping(simplified),
            "properties": copy.deepcopy(f.get("properties") or {}),
        })

    result_geojson = {"type": "FeatureCollection", "features": new_features}
    ref_id = ctx.register(result_geojson, source=f"simplify:{data_ref_id}")
    summary = ctx.summary(ref_id)
    return {
        "data_ref_id": ref_id,
        **summary,
        "summary": f"几何简化完成（tolerance={tolerance}），{len(new_features)}个要素",
    }


@tool
async def voronoi(data_ref_id: str) -> dict:
    """为点集生成泰森多边形（Voronoi图）。

    使用场景：当用户说"服务范围划分"、"最近分配"、"泰森多边形"时使用。

    示例：voronoi(data_ref_id="ref_stations")
    """
    geojson, ctx, features = _load_features(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    geoms = [shape(f["geometry"]) for f in features if f.get("geometry")]
    if not geoms:
        return {"error": "数据中没有有效几何"}

    merged = unary_union(geoms)
    diagram = voronoi_diagram(merged)
    vor_features = [
        {"type": "Feature", "geometry": mapping(g), "properties": {"index": i}}
        for i, g in enumerate(diagram.geoms)
    ]
    result_geojson = {"type": "FeatureCollection", "features": vor_features}
    ref_id = ctx.register(result_geojson, source=f"voronoi:{data_ref_id}")
    summary = ctx.summary(ref_id)
    return {
        "data_ref_id": ref_id,
        **summary,
        "summary": f"泰森多边形生成完成，{len(vor_features)}个区域",
    }
