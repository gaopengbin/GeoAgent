"""visualization 工具组：热力图、填色图、统计图表配置生成

这些工具不做 GIS 计算，而是将 data_ref_id 对应的数据转换为前端渲染配置。
- generate_heatmap → Cesium Heatmap 配置（通过 map_command 推送）
- generate_choropleth → Cesium 填色图样式配置
- generate_chart → ECharts option JSON（通过 SSE 推送给 ResultPanel）
"""

import logging
from typing import Literal, Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def generate_heatmap(
    data_ref_id: str,
    weight_field: Optional[str] = None,
    radius: int = 30,
    opacity: float = 0.7,
) -> dict:
    """将点数据生成热力图配置，推送到前端地图渲染。

    使用场景：当用户说"热力图"、"密度可视化"时使用。
    需要先用 discover_gis_tools("visualization") 启用此工具。

    示例：generate_heatmap(data_ref_id="ref_poi", weight_field="population")
    """
    from app.tools._context import get_tool_context

    ctx = get_tool_context()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    features = geojson.get("features", [])
    points = []
    for f in features:
        geom = f.get("geometry", {})
        if geom.get("type") != "Point":
            continue
        coords = geom["coordinates"]
        weight = 1.0
        if weight_field:
            w = f.get("properties", {}).get(weight_field)
            if isinstance(w, (int, float)):
                weight = float(w)
        points.append({"longitude": coords[0], "latitude": coords[1], "weight": weight})

    from app.tools._context import push_map_command
    push_map_command({
        "action": "addHeatmap",
        "params": {
            "id": f"heatmap_{data_ref_id}",
            "name": f"热力图 ({len(points)}点)",
            "data": geojson,
            "style": {
                "radius": radius,
                "opacity": opacity,
                "color": "#FF4500",
            },
        },
    })

    return {
        "point_count": len(points),
        "summary": f"热力图配置已生成：{len(points)}个点，半径{radius}px",
    }


@tool
async def generate_choropleth(
    data_ref_id: str,
    value_field: str,
    color_scheme: Literal["blue", "red", "green", "yellow", "diverging"] = "blue",
    classes: int = 5,
) -> dict:
    """将面数据生成填色（等值区域）图配置。

    使用场景：当用户说"填色图"、"专题地图"、"按XX着色"时使用。

    示例：generate_choropleth(data_ref_id="ref_districts", value_field="population")
    """
    from app.tools._context import get_tool_context

    ctx = get_tool_context()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    features = geojson.get("features", [])

    # 提取字段值
    values = []
    for f in features:
        v = f.get("properties", {}).get(value_field)
        if isinstance(v, (int, float)):
            values.append(float(v))

    if not values:
        # 收集可用的数值字段
        numeric_fields = set()
        for f in features[:20]:
            for k, v in f.get("properties", {}).items():
                if isinstance(v, (int, float)):
                    numeric_fields.add(k)
        return {
            "error": f"字段 '{value_field}' 中没有有效数值",
            "available_numeric_fields": sorted(numeric_fields),
            "hint": "请从 available_numeric_fields 中选择一个有效的数值字段重试",
        }

    # 计算分级断点（等间隔）
    v_min, v_max = min(values), max(values)
    step = (v_max - v_min) / classes if v_max > v_min else 1
    breaks = [v_min + i * step for i in range(classes + 1)]

    # 色阶
    SCHEMES = {
        "blue": ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"],
        "red": ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"],
        "green": ["#edf8e9", "#bae4b3", "#74c476", "#31a354", "#006d2c"],
        "yellow": ["#ffffcc", "#ffeda0", "#feb24c", "#f03b20", "#bd0026"],
        "diverging": ["#2166ac", "#67a9cf", "#f7f7f7", "#ef8a62", "#b2182b"],
    }
    colors = SCHEMES.get(color_scheme, SCHEMES["blue"])

    from app.tools._context import push_map_command
    push_map_command({
        "action": "addGeoJsonLayer",
        "params": {
            "id": f"choropleth_{data_ref_id}",
            "name": f"填色图 - {value_field}",
            "data": geojson,
            "style": {
                "color": colors[-1],
                "opacity": 0.7,
                "choropleth": {
                    "field": value_field,
                    "breaks": breaks,
                    "colors": colors,
                },
            },
        },
    })

    return {
        "value_field": value_field,
        "value_range": [v_min, v_max],
        "classes": classes,
        "breaks": breaks,
        "feature_count": len(features),
        "summary": f"填色图配置已生成：{len(features)}个要素，{value_field} 分{classes}级",
    }


@tool
async def generate_chart(
    data_ref_id: str,
    chart_type: Literal["bar", "pie", "line", "scatter"] = "bar",
    x_field: Optional[str] = None,
    y_field: Optional[str] = None,
    group_field: Optional[str] = None,
    title: str = "",
) -> dict:
    """从数据生成 ECharts 图表配置。

    使用场景：当用户说"柱状图"、"饼图"、"趋势图"、"统计图表"时使用。

    示例：generate_chart(data_ref_id="ref_poi", chart_type="bar", group_field="type")
    """
    from collections import Counter
    from app.tools._context import get_tool_context

    ctx = get_tool_context()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    features = geojson.get("features", [])
    props_list = [f.get("properties", {}) for f in features]

    if chart_type in ("bar", "pie") and group_field:
        # 分组计数
        counter = Counter(p.get(group_field, "未知") for p in props_list)
        categories = list(counter.keys())
        values = list(counter.values())

        if chart_type == "bar":
            option = {
                "title": {"text": title or f"{group_field} 分布"},
                "xAxis": {"type": "category", "data": categories},
                "yAxis": {"type": "value"},
                "series": [{"type": "bar", "data": values}],
            }
        else:  # pie
            option = {
                "title": {"text": title or f"{group_field} 占比"},
                "series": [{
                    "type": "pie",
                    "data": [{"name": k, "value": v} for k, v in counter.items()],
                }],
            }
    elif x_field and y_field:
        xs = [p.get(x_field) for p in props_list if p.get(x_field) is not None]
        ys = [p.get(y_field) for p in props_list if p.get(y_field) is not None]

        if chart_type == "scatter":
            option = {
                "title": {"text": title or f"{x_field} vs {y_field}"},
                "xAxis": {"name": x_field},
                "yAxis": {"name": y_field},
                "series": [{"type": "scatter", "data": list(zip(xs, ys))}],
            }
        else:  # line
            option = {
                "title": {"text": title or f"{y_field} 趋势"},
                "xAxis": {"type": "category", "data": xs},
                "yAxis": {"type": "value"},
                "series": [{"type": "line", "data": ys}],
            }
    else:
        # 自动推断：找第一个分类字段做分组计数
        sample = props_list[:20]
        string_fields = set()
        numeric_fields = set()
        for p in sample:
            for k, v in p.items():
                if isinstance(v, str):
                    string_fields.add(k)
                elif isinstance(v, (int, float)):
                    numeric_fields.add(k)
        if string_fields:
            auto_field = sorted(string_fields)[0]
            from collections import Counter as AutoCounter
            counter = AutoCounter(p.get(auto_field, "未知") for p in props_list)
            categories = list(counter.keys())
            values = list(counter.values())
            option = {
                "title": {"text": title or f"{auto_field} 分布"},
                "xAxis": {"type": "category", "data": categories},
                "yAxis": {"type": "value"},
                "series": [{"type": "bar", "data": values}],
            }
        else:
            return {
                "error": "请指定 group_field（分组字段）或 x_field + y_field（数值字段）",
                "available_string_fields": sorted(string_fields),
                "available_numeric_fields": sorted(numeric_fields),
            }

    from app.tools._context import push_chart_option
    push_chart_option({
        "option": option,
        "chart_type": chart_type,
        "title": option.get("title", {}).get("text", f"{chart_type} 图表"),
    })

    return {
        "chart_type": chart_type,
        "data_points": len(features),
        "summary": f"{chart_type}图表配置已生成，包含{len(features)}条数据，已推送到前端渲染",
    }
