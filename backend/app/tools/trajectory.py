"""trajectory 工具：轨迹动画播放

从 LineString 或 Point 序列中提取坐标，通过 map_command 推送 playTrajectory 指令。
前端使用 Cesium SampledPositionProperty + Clock 实现沿路径动画。
"""

from typing import Optional

from langchain_core.tools import tool


@tool
async def play_trajectory(
    data_ref_id: str,
    duration_seconds: float = 30.0,
    trail_seconds: float = 5.0,
    label: Optional[str] = None,
) -> dict:
    """播放轨迹动画：沿路径移动的实体 + 尾迹线。

    使用场景：当用户说"播放轨迹"、"路径动画"、"运动轨迹"时使用。

    数据要求：data_ref_id 对应的数据中应包含 LineString 或 Point 序列。
    - LineString: 直接使用其坐标序列
    - Point 序列: 按 features 顺序提取各点坐标

    参数：
    - duration_seconds: 整段动画时长（秒），默认30秒
    - trail_seconds: 尾迹保留时长（秒），默认5秒
    - label: 移动实体的标注文字

    示例：play_trajectory(data_ref_id="ref_track", duration_seconds=20, label="车辆A")
    """
    from app.tools._context import get_tool_context, push_map_command

    ctx = get_tool_context()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    # 提取坐标序列 [[lon, lat, alt?], ...]
    coords = _extract_trajectory_coords(geojson)
    if len(coords) < 2:
        return {"error": f"轨迹数据至少需要2个点，当前仅有{len(coords)}个"}

    push_map_command({
        "action": "playTrajectory",
        "params": {
            "id": f"trajectory_{data_ref_id}",
            "name": label or f"轨迹 ({len(coords)}点)",
            "coordinates": coords,
            "durationSeconds": duration_seconds,
            "trailSeconds": trail_seconds,
            "label": label,
        },
    })

    return {
        "point_count": len(coords),
        "duration_seconds": duration_seconds,
        "summary": f"已发送轨迹动画指令：{len(coords)}个点，时长{duration_seconds}秒",
    }


def _extract_trajectory_coords(geojson: dict) -> list:
    """从 GeoJSON 提取有序坐标序列"""
    features = geojson.get("features", [])
    if not features:
        return []

    # 策略1: 第一个 feature 是 LineString/MultiLineString → 直接使用
    first_geom = features[0].get("geometry", {})
    gtype = first_geom.get("type", "")

    if gtype == "LineString":
        return [c[:3] for c in first_geom["coordinates"]]

    if gtype == "MultiLineString":
        coords = []
        for line in first_geom["coordinates"]:
            coords.extend(c[:3] for c in line)
        return coords

    # 策略2: Point 序列 → 按 features 顺序提取
    coords = []
    for f in features:
        geom = f.get("geometry", {})
        if geom.get("type") == "Point":
            coords.append(geom["coordinates"][:3])
    if coords:
        return coords

    # 策略3: 混合几何 → 取所有 LineString 拼接
    for f in features:
        geom = f.get("geometry", {})
        if geom.get("type") == "LineString":
            coords.extend(c[:3] for c in geom["coordinates"])

    return coords
