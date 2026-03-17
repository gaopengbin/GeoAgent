"""spatial_analysis 工具组：缓冲区、空间查询、叠加分析、裁剪

本地 geopandas 实现，接受 data_ref_id 参数，结果存回 SessionDataContext。
"""

import json
import logging
from typing import Literal

import geopandas as gpd
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_ctx():
    from app.tools._context import get_tool_context
    return get_tool_context()


def _ref_to_gdf(ctx, ref_id: str) -> gpd.GeoDataFrame | None:
    """data_ref_id → GeoDataFrame"""
    geojson = ctx.get(ref_id)
    if geojson is None:
        return None
    return gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")


def _gdf_to_ref(ctx, gdf: gpd.GeoDataFrame, source: str) -> dict:
    """GeoDataFrame → 存回 SessionDataContext → 返回 summary dict"""
    geojson = json.loads(gdf.to_json())
    ref_id = ctx.register(geojson, source=source)
    summary = ctx.summary(ref_id)
    return {"data_ref_id": ref_id, **summary}


@tool
async def buffer_analysis(
    data_ref_id: str,
    distance: float,
    unit: Literal["m", "km"] = "m",
) -> dict:
    """对指定图层创建缓冲区。

    使用场景：当用户说"XX范围内"、"周围XX米"、"服务半径"时使用。

    示例：
    - "地铁站500米范围内" → buffer_analysis(data_ref_id="ref_001", distance=500)
    - "公园周围2公里" → buffer_analysis(data_ref_id="ref_parks", distance=2, unit="km")
    """
    ctx = _get_ctx()
    gdf = _ref_to_gdf(ctx, data_ref_id)
    if gdf is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    d_meters = distance * 1000 if unit == "km" else distance

    # 投影到 UTM 做缓冲（米为单位），再转回 WGS84
    utm_crs = gdf.estimate_utm_crs()
    gdf_utm = gdf.to_crs(utm_crs)
    gdf_utm["geometry"] = gdf_utm.geometry.buffer(d_meters)
    gdf_result = gdf_utm.to_crs("EPSG:4326")

    result = _gdf_to_ref(ctx, gdf_result, source=f"buffer:{data_ref_id}:{distance}{unit}")
    result["summary"] = f"创建了{distance}{unit}缓冲区，{result.get('feature_count', '?')}个要素"
    return result


@tool
async def spatial_query(
    method: Literal["within", "intersects", "contains"],
    target_ref: str,
    mask_ref: str,
) -> dict:
    """空间关系查询：筛选满足空间关系的要素。

    使用场景：当用户说"在XX内的"、"与XX相交的"时使用。

    示例：
    - "缓冲区内的住宅" → spatial_query("within", target_ref="ref_res", mask_ref="ref_buf")
    - "与河流相交的道路" → spatial_query("intersects", target_ref="ref_roads", mask_ref="ref_rivers")
    """
    ctx = _get_ctx()
    gdf_target = _ref_to_gdf(ctx, target_ref)
    gdf_mask = _ref_to_gdf(ctx, mask_ref)
    if gdf_target is None:
        return {"error": f"data_ref_id '{target_ref}' 不存在"}
    if gdf_mask is None:
        return {"error": f"data_ref_id '{mask_ref}' 不存在"}

    total = len(gdf_target)
    joined = gpd.sjoin(gdf_target, gdf_mask, how="inner", predicate=method)
    # sjoin 可能产生重复行（一个 target 匹配多个 mask），去重保留原索引
    joined = joined[~joined.index.duplicated(keep="first")]
    # 只保留 target 原有列
    result_gdf = gdf_target.loc[joined.index]

    result = _gdf_to_ref(ctx, result_gdf, source=f"sjoin:{method}:{target_ref}∩{mask_ref}")
    matched = result.get("feature_count", "?")
    result["summary"] = f"{total}个要素中有{matched}个满足{method}条件"
    return result


@tool
async def overlay_analysis(
    ref_a: str,
    ref_b: str,
    operation: Literal["intersection", "union", "difference", "symmetric_difference"],
) -> dict:
    """空间叠加分析。

    使用场景：求两个区域的重叠/合并/差异。
    示例：overlay_analysis(ref_a="ref_green", ref_b="ref_plan", operation="intersection")
    """
    ctx = _get_ctx()
    gdf_a = _ref_to_gdf(ctx, ref_a)
    gdf_b = _ref_to_gdf(ctx, ref_b)
    if gdf_a is None:
        return {"error": f"data_ref_id '{ref_a}' 不存在"}
    if gdf_b is None:
        return {"error": f"data_ref_id '{ref_b}' 不存在"}

    result_gdf = gpd.overlay(gdf_a, gdf_b, how=operation)
    result = _gdf_to_ref(ctx, result_gdf, source=f"overlay:{operation}:{ref_a}∩{ref_b}")
    result["summary"] = f"{operation}叠加分析完成，{result.get('feature_count', '?')}个要素"
    return result


@tool
async def clip_analysis(
    data_ref_id: str,
    mask_ref: str,
) -> dict:
    """用掩膜裁剪数据。

    使用场景：当用户说"XX区域内的"、"裁剪到XX范围"时使用。
    示例：clip_analysis(data_ref_id="ref_all_roads", mask_ref="ref_boundary")
    """
    ctx = _get_ctx()
    gdf_data = _ref_to_gdf(ctx, data_ref_id)
    gdf_mask = _ref_to_gdf(ctx, mask_ref)
    if gdf_data is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}
    if gdf_mask is None:
        return {"error": f"data_ref_id '{mask_ref}' 不存在"}

    result_gdf = gpd.clip(gdf_data, gdf_mask)
    result = _gdf_to_ref(ctx, result_gdf, source=f"clip:{data_ref_id}∩{mask_ref}")
    result["summary"] = f"裁剪完成，保留{result.get('feature_count', '?')}个要素"
    return result
