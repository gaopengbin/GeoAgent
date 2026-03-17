"""核心工具（始终可见）+ discover_gis_tools 元工具

包含：
- geocoding: 地理编码（天地图/Nominatim）
- fetch_osm_data: OSM 数据获取（Overpass API）
- load_uploaded_file: 加载用户上传的文件
- generate_map_command: 生成前端地图操控指令
- generate_report: 生成分析报告
- discover_gis_tools: 元工具，按需启用工具组
"""

import json
import logging
from typing import Literal, Optional

import httpx
from langchain_core.tools import tool

from app.config import settings
from app.tools.registry import TOOLSET_DEFINITIONS

logger = logging.getLogger(__name__)

# --- Overpass 查询映射 ---

OSM_TAG_MAP = {
    ("poi", "地铁站"): "railway=station",
    ("poi", "医院"): "amenity=hospital",
    ("poi", "学校"): "amenity=school",
    ("poi", "公园"): "leisure=park",
    ("poi", "超市"): "shop=supermarket",
    ("poi", "餐厅"): "amenity=restaurant",
    ("poi", "银行"): "amenity=bank",
    ("poi", "加油站"): "amenity=fuel",
    ("poi", "停车场"): "amenity=parking",
    ("road", "高速公路"): "highway=motorway",
    ("road", "主干道"): "highway=trunk|primary",
    ("building", "建筑"): "building=yes",
    ("boundary", ""): "admin_level=4",
    ("landuse", "绿地"): "landuse=grass|forest|recreation_ground",
}

# Overpass 镜像列表：用户配置的优先，其余作为降级备选
_OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def _get_overpass_urls() -> list[str]:
    """返回去重的 Overpass 端点列表，用户配置的排最前"""
    configured = settings.OVERPASS_URL
    urls = [configured] if configured else []
    for m in _OVERPASS_MIRRORS:
        if m not in urls:
            urls.append(m)
    return urls


async def _overpass_query(client: httpx.AsyncClient, query: str) -> list:
    """向 Overpass 发送查询，自动尝试多个镜像"""
    urls = _get_overpass_urls()
    last_err = None
    for url in urls:
        try:
            resp = await client.post(url, data={"data": query})
            if resp.status_code == 200:
                return resp.json().get("elements", [])
            logger.warning("[Overpass] %s HTTP %d", url, resp.status_code)
        except Exception as e:
            logger.warning("[Overpass] %s 失败: %s", url, e)
            last_err = e
    logger.error("[Overpass] 所有镜像均失败, last_err=%s", last_err)
    return []


@tool
async def geocoding(
    address: str,
    provider: Literal["tianditu", "nominatim"] = "tianditu",
) -> dict:
    """地名/地址 → 坐标。

    使用场景：当用户提到地名需要定位时使用（flyTo的前置步骤）。
    示例：geocoding("北京天安门") → {"longitude": 116.3975, "latitude": 39.9087}
    """
    async with httpx.AsyncClient(timeout=15) as client:
        if provider == "tianditu" and settings.TIANDITU_TOKEN:
            resp = await client.get(
                "http://api.tianditu.gov.cn/geocoder",
                params={
                    "ds": json.dumps({"keyWord": address}),
                    "tk": settings.TIANDITU_TOKEN,
                },
            )
            data = resp.json()
            loc = data.get("location", {})
            return {
                "longitude": loc.get("lon"),
                "latitude": loc.get("lat"),
                "formatted_address": data.get("formatted_address", address),
                "level": data.get("level", "unknown"),
                "confidence": data.get("score", 0) / 100.0 if data.get("score") else 0.8,
            }
        else:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": address, "format": "json", "limit": 1},
                headers={"User-Agent": "GeoAgent/1.0"},
            )
            results = resp.json()
            if not results:
                return {"error": f"未找到地点: {address}"}
            r = results[0]
            return {
                "longitude": float(r["lon"]),
                "latitude": float(r["lat"]),
                "formatted_address": r.get("display_name", address),
                "level": r.get("type", "unknown"),
                "confidence": 0.8,
            }


@tool
async def fetch_osm_data(
    data_type: Literal["poi", "road", "building", "boundary", "landuse"],
    query: str,
    area: str,
    longitude: Optional[float] = None,
    latitude: Optional[float] = None,
    radius: int = 5000,
    limit: int = 5000,
) -> dict:
    """从OpenStreetMap获取空间数据。

    使用场景：需要获取某区域的POI、路网、建筑、边界、用地数据时使用。

    参数说明：
    - area: 区域名称（如"北京"、"上海浦东"）。对于大城市/行政区效果好。
    - longitude/latitude: 可选中心坐标，提供后将以此为圆心按radius(米)范围搜索，忽略area。
    - radius: 搜索半径（米），默认5000。仅在提供经纬度时生效。

    示例：
    - fetch_osm_data("poi", "地铁站", "北京") — 按行政区搜索
    - fetch_osm_data("poi", "餐厅", "天安门", longitude=116.3975, latitude=39.9087, radius=1000) — 按坐标+半径搜索

    返回：data_ref_id + 摘要（不含全量数据）
    """
    tag = OSM_TAG_MAP.get((data_type, query))
    if not tag:
        tag = _guess_osm_tag(data_type, query)

    key, value = tag.split("=", 1) if "=" in tag else (tag, "yes")

    # 多值 tag 处理（如 highway=trunk|primary）
    if "|" in value:
        tag_filter = "|".join(f'["{key}"="{v}"]' for v in value.split("|"))
    else:
        tag_filter = f'["{key}"="{value}"]'

    elements = []

    async with httpx.AsyncClient(timeout=60) as client:
        # 策略1：有经纬度 → 坐标+半径 around 查询
        if longitude is not None and latitude is not None:
            elements = await _overpass_around(client, tag_filter, latitude, longitude, radius, limit)
        else:
            # 策略2：area name 查询（适合大城市/行政区）
            elements = await _overpass_area(client, tag_filter, area, limit)
            # 策略3：area 查询返回 0 → fallback geocode + around
            if not elements:
                logger.info("area查询[%s]返回0结果，尝试geocode fallback", area)
                coords = await _geocode_for_overpass(area)
                if coords:
                    elements = await _overpass_around(
                        client, tag_filter, coords[1], coords[0], radius, limit
                    )

    features = []
    for elem in elements:
        lon = elem.get("lon") or elem.get("center", {}).get("lon")
        lat = elem.get("lat") or elem.get("center", {}).get("lat")
        if lon is None or lat is None:
            continue
        tags = elem.get("tags", {})
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "osm_id": elem.get("id"),
                "name": tags.get("name", ""),
                **{k: v for k, v in tags.items() if k != "name"},
            },
        })

    if not features:
        return {
            "error": f"从OSM获取到0个{query}（Overpass API可能不可达）",
            "suggestion": "请改用 amap_poi_search 或 amap_around_search 获取数据（国内更稳定）",
            "feature_count": 0,
        }

    geojson = {"type": "FeatureCollection", "features": features}

    from app.tools._context import get_tool_context
    ctx = get_tool_context()
    ref_id = ctx.register(geojson, source=f"osm:{data_type}:{query}")
    summary = ctx.summary(ref_id)
    return {
        "data_ref_id": ref_id,
        **summary,
        "summary": f"从OSM获取到{len(features)}个{query}",
    }


async def _overpass_area(client: httpx.AsyncClient, tag_filter: str, area: str, limit: int) -> list:
    """Overpass area name 查询"""
    q = f"""
    [out:json][timeout:30];
    area["name"~"{area}"]->.searchArea;
    nwr{tag_filter}(area.searchArea);
    out center {limit};
    """
    return await _overpass_query(client, q)


async def _overpass_around(
    client: httpx.AsyncClient, tag_filter: str,
    lat: float, lon: float, radius: int, limit: int,
) -> list:
    """Overpass 坐标+半径 around 查询"""
    q = f"""
    [out:json][timeout:30];
    nwr{tag_filter}(around:{radius},{lat},{lon});
    out center {limit};
    """
    return await _overpass_query(client, q)


async def _geocode_for_overpass(place: str) -> Optional[tuple[float, float]]:
    """简易 geocode 获取坐标，用于 Overpass fallback"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if settings.TIANDITU_TOKEN:
                resp = await client.get(
                    "http://api.tianditu.gov.cn/geocoder",
                    params={"ds": json.dumps({"keyWord": place}), "tk": settings.TIANDITU_TOKEN},
                )
                loc = resp.json().get("location", {})
                lon, lat = loc.get("lon"), loc.get("lat")
                if lon and lat:
                    return (float(lon), float(lat))
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": place, "format": "json", "limit": 1},
                headers={"User-Agent": "GeoAgent/1.0"},
            )
            results = resp.json()
            if results:
                return (float(results[0]["lon"]), float(results[0]["lat"]))
    except Exception as e:
        logger.warning("geocode fallback 失败: %s", e)
    return None


@tool
async def load_uploaded_file(
    file_id: str,
    crs: str = "EPSG:4326",
) -> dict:
    """加载用户上传的文件，解析为GeoJSON并注册到会话数据中。

    使用场景：当用户上传了文件并说"加载这个文件"、"分析上传的数据"时使用。
    file_id 由前端上传接口返回。

    示例：load_uploaded_file(file_id="abc123")
    """
    import os
    from app.tools._context import get_tool_context
    from app.services.file_parser import parse_file

    ctx = get_tool_context()

    # 查找文件路径（遍历 uploads 目录）
    upload_dir = settings.UPLOAD_DIR
    file_path = None
    for root, dirs, files in os.walk(upload_dir):
        for fname in files:
            if fname.startswith(file_id):
                file_path = os.path.join(root, fname)
                break
        if file_path:
            break

    if not file_path or not os.path.exists(file_path):
        return {"error": f"文件 {file_id} 未找到，请确认已上传"}

    try:
        geojson = parse_file(file_path, crs=crs)
    except ValueError as e:
        return {"error": f"文件解析失败: {str(e)}"}
    except Exception as e:
        logger.exception("文件解析异常")
        return {"error": f"文件解析异常: {str(e)}"}

    ref_id = ctx.register(geojson, source=f"upload:{os.path.basename(file_path)}")
    summary = ctx.summary(ref_id)

    return {
        "data_ref_id": ref_id,
        **summary,
        "summary": f"已加载文件，{summary['feature_count']}个{summary['geometry_type']}要素",
    }


@tool
async def generate_map_command(
    action: Literal["flyTo", "addGeoJsonLayer", "addHeatmap", "addLabel", "removeLayer", "setBasemap", "updateLayerStyle"],
    data_ref_id: Optional[str] = None,
    longitude: Optional[float] = None,
    latitude: Optional[float] = None,
    height: Optional[float] = None,
    style: Optional[dict] = None,
    label_field: Optional[str] = None,
    category_field: Optional[str] = None,
    layer_id: Optional[str] = None,
) -> dict:
    """生成前端地图操控指令，通过SSE推送给前端执行。

    使用场景：需要在地图上展示数据、飞行定位、切换底图、添加标注、修改图层样式时使用。

    示例：
    - "飞到北京" → generate_map_command("flyTo", longitude=116.4, latitude=39.9, height=50000)
    - "在地图上显示" → generate_map_command("addGeoJsonLayer", data_ref_id="ref_001")
    - "显示并设置点位大小" → generate_map_command("addGeoJsonLayer", data_ref_id="ref_001", style={"color": "#FF0000", "opacity": 0.8, "pointSize": 14})
    - "显示点位并标注名称" → generate_map_command("addGeoJsonLayer", data_ref_id="ref_001", label_field="name")
    - "聚类结果分色" → generate_map_command("addGeoJsonLayer", data_ref_id="ref_cluster", category_field="cluster_id")
    - "添加金色标注" → generate_map_command("addLabel", data_ref_id="ref_001", label_field="name", style={"fillColor": "#FFD700", "font": "bold 16px 宋体", "outlineColor": "#000000"})
    - "修改标注样式" → generate_map_command("updateLayerStyle", layer_id="label_ref_xxx", style={"labelStyle": {"fillColor": "#FF0000", "fontSize": 16, "font": "bold 18px 宋体"}})
    - "修改图层颜色/点位大小" → generate_map_command("updateLayerStyle", layer_id="ref_xxx", style={"layerStyle": {"color": "#FF0000", "opacity": 0.8, "pointSize": 16}})

    addLabel style 字段说明：
    - fillColor: 文字颜色（CSS颜色值，如 "#FFD700", "gold"）
    - font: 字体（CSS字体格式，如 "bold 16px 宋体", "14px sans-serif"）
    - outlineColor: 描边颜色
    - outlineWidth: 描边宽度（数字）
    - showBackground: 是否显示背景（布尔值）
    - backgroundColor: 背景颜色
    - scale: 缩放比例（数字）
    """
    params = {}

    if action == "flyTo":
        params = {
            "longitude": longitude,
            "latitude": latitude,
            "height": height or 50000,
            "pitch": -45,
            "duration": 2,
        }
    elif action in ("addGeoJsonLayer", "addHeatmap"):
        if not data_ref_id:
            return {"error": f"action={action} 需要提供 data_ref_id"}
        from app.tools._context import get_tool_context
        ctx = get_tool_context()
        geojson = ctx.get(data_ref_id)
        if geojson is None:
            return {"error": f"data_ref_id '{data_ref_id}' 不存在"}
        layer_style = style or {"color": "#3388ff", "opacity": 0.6}
        if category_field:
            layer_style["category"] = {"field": category_field}
        params = {
            "id": data_ref_id,
            "name": data_ref_id,
            "data": geojson,
            "style": layer_style,
            "dataRefId": data_ref_id,
        }
        # 支持圆点+文字同图层：label_field 传递到前端 addGeoJsonLayer
        if label_field:
            params["labelField"] = label_field
            # 标注样式从 style 中提取 labelStyle 子对象（如有）
            if style and "labelStyle" in style:
                params["labelStyle"] = style.pop("labelStyle")
        from app.tools._context import push_map_command
        push_map_command({"action": action, "params": params})
        extras = []
        if category_field:
            extras.append(f"按{category_field}分色")
        if label_field:
            extras.append(f"标注字段: {label_field}")
        suffix = f"（{'，'.join(extras)}）" if extras else ""
        return {"summary": f"已发送{action}指令到前端{suffix}，数据引用: {data_ref_id}"}
    elif action == "addLabel":
        if not data_ref_id:
            return {"error": "addLabel 需要提供 data_ref_id"}
        if not label_field:
            return {"error": "addLabel 需要提供 label_field（标注字段名）"}
        from app.tools._context import get_tool_context
        ctx = get_tool_context()
        geojson = ctx.get(data_ref_id)
        if geojson is None:
            return {"error": f"data_ref_id '{data_ref_id}' 不存在"}
        # 标准化 style 字段名（LLM 常见的别名 → 前端期望字段）
        raw_style = dict(style) if style else {}
        _LABEL_ALIASES = {
            "color": "fillColor", "textColor": "fillColor", "fontColor": "fillColor",
            "fontFamily": "font", "fontSize": "font",
            "borderColor": "outlineColor", "strokeColor": "outlineColor",
            "borderWidth": "outlineWidth", "strokeWidth": "outlineWidth",
            "bgColor": "backgroundColor", "background": "showBackground",
        }
        label_style: dict = {}
        for k, v in raw_style.items():
            mapped = _LABEL_ALIASES.get(k, k)
            if mapped == "font" and k == "fontSize":
                # fontSize 数字 → CSS font 字符串
                existing_font = label_style.get("font", "")
                family = raw_style.get("fontFamily", "sans-serif")
                label_style["font"] = f"{v}px {family}" if not existing_font else existing_font
            else:
                label_style[mapped] = v
        params = {
            "dataRefId": data_ref_id,
            "data": geojson,
            "field": label_field,
            "style": label_style,
        }
        from app.tools._context import push_map_command
        push_map_command({"action": "addLabel", "params": params})
        return {"summary": f"已发送标注指令到前端，字段: {label_field}，数据引用: {data_ref_id}"}
    elif action == "updateLayerStyle":
        lid = layer_id or data_ref_id
        if not lid:
            return {"error": "updateLayerStyle 需要提供 layer_id"}
        if not style:
            return {"error": "updateLayerStyle 需要提供 style（含 labelStyle 或 layerStyle）"}
        params = {"layerId": lid, **style}
        from app.tools._context import push_map_command
        push_map_command({"action": "updateLayerStyle", "params": params})
        return {"summary": f"已发送样式修改指令，目标图层: {lid}"}
    elif action == "removeLayer":
        params = {"id": data_ref_id}
    elif action == "setBasemap":
        params = {"basemap": data_ref_id}

    command = {"action": action, "params": params}
    from app.tools._context import push_map_command
    push_map_command(command)
    return {"summary": f"已发送{action}指令到前端"}


@tool
async def generate_report(
    data_ref_ids: Optional[list[str]] = None,
    format: Literal["markdown", "html"] = "markdown",
    analysis_summary: Optional[str] = None,
    sections: Optional[list[str]] = None,
) -> dict:
    """基于当前会话的分析结果生成结构化报告。

    使用场景：分析流程结束后，用户需要汇总报告时使用。

    Args:
        data_ref_ids: 要包含在报告中的数据集 ID 列表，不传则包含所有数据集。
        format: 输出格式，固定为 markdown。
        analysis_summary: **重要** — 你对本次分析的完整结论与洞察（Markdown 格式）。
            应包含：分析目的、关键发现、数据特征总结、空间分布规律等。
            此内容将作为报告的核心"分析结论"章节，请尽量详细。
        sections: 可选，指定报告包含哪些章节，默认全部。
            可选值：overview, spatial, details, statistics, conclusion
    """
    from app.tools._context import get_tool_context
    from collections import Counter

    ctx = get_tool_context()

    refs = ctx.list_refs()
    if data_ref_ids:
        refs = [r for r in refs if r["data_ref_id"] in data_ref_ids]

    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    all_sections = sections or ["overview", "spatial", "details", "statistics", "conclusion"]
    lines = [f"# GeoAgent 分析报告\n\n> 生成时间：{now}\n"]

    # ---- 数据概览 ----
    if "overview" in all_sections:
        lines.append(f"## 数据概览\n\n本次分析共涉及 **{len(refs)}** 个数据集。\n")
        if refs:
            lines.append("| 数据集 | 来源 | 类型 | 要素数 | 属性字段 |")
            lines.append("|--------|------|------|--------|----------|")
            for ref in refs:
                fields = "、".join(ref.get("properties", [])[:5])
                if not fields:
                    fields = "-"
                lines.append(
                    f"| `{ref['data_ref_id']}` | {ref.get('source', '-')} | "
                    f"{ref.get('geometry_type', '-')} | {ref.get('feature_count', '-')} | {fields} |"
                )
            lines.append("")

    # ---- 空间范围 ----
    if "spatial" in all_sections:
        has_bbox = any(ref.get("bbox") for ref in refs)
        if has_bbox:
            lines.append("## 空间范围\n")
            for ref in refs:
                bbox = ref.get("bbox")
                if bbox and len(bbox) == 4:
                    lines.append(
                        f"- **{ref['data_ref_id']}**: 经度 {bbox[0]:.4f}° ~ {bbox[2]:.4f}°，"
                        f"纬度 {bbox[1]:.4f}° ~ {bbox[3]:.4f}°"
                    )
            lines.append("")

    # ---- 数据详情 + 属性统计 ----
    if "details" in all_sections or "statistics" in all_sections:
        lines.append("## 数据详情\n")
        for ref in refs:
            geojson = ctx.get(ref["data_ref_id"])
            if not geojson:
                continue
            features = geojson.get("features", [])
            lines.append(f"### {ref['data_ref_id']}\n")
            lines.append(f"- **要素数量**: {len(features)}")
            lines.append(f"- **几何类型**: {ref.get('geometry_type', '-')}")
            lines.append(f"- **数据来源**: {ref.get('source', '-')}")
            if features:
                props = features[0].get("properties", {})
                field_names = list(props.keys())[:8]
                lines.append(f"- **属性字段**: {', '.join(field_names) if field_names else '无'}")

            # 属性值 Top 统计
            if "statistics" in all_sections and features:
                lines.append("")
                cat_fields = []
                for key in list(features[0].get("properties", {}).keys())[:6]:
                    vals = [f.get("properties", {}).get(key) for f in features if f.get("properties", {}).get(key)]
                    if vals and all(isinstance(v, str) for v in vals[:10]):
                        cat_fields.append((key, vals))
                for key, vals in cat_fields[:3]:
                    counter = Counter(vals)
                    top5 = counter.most_common(5)
                    lines.append(f"**{key}** 分布（Top 5）：\n")
                    lines.append(f"| 值 | 数量 | 占比 |")
                    lines.append(f"|-----|------|------|")
                    for val, cnt in top5:
                        pct = cnt / len(vals) * 100
                        lines.append(f"| {val} | {cnt} | {pct:.1f}% |")
                    lines.append("")

            lines.append("")

    # ---- 分析结论（LLM 提供） ----
    if "conclusion" in all_sections and analysis_summary:
        lines.append("## 分析结论\n")
        lines.append(analysis_summary)
        lines.append("")

    content = "\n".join(lines)
    return {
        "content": content,
        "format": "markdown",
        "word_count": len(content),
        "dataset_count": len(refs),
        "summary": f"报告已生成（{len(refs)}个数据集，{len(content)}字）",
    }


@tool
async def discover_gis_tools(
    category: Literal[
        "spatial_analysis", "measurement", "geometry",
        "coordinate", "visualization", "statistics", "scene3d", "trajectory", "amap",
    ],
) -> dict:
    """按需启用GIS工具组。

    可用类别：
    - spatial_analysis: 缓冲区、空间查询、叠加分析、裁剪
    - measurement: 距离计算、面积计算、字段统计
    - geometry: 质心、凸包、简化、泰森多边形
    - coordinate: 坐标转换、UTM分区
    - visualization: 热力图、填色图、统计图表
    - statistics: 空间统计、核密度、聚类分析
    - scene3d: 3D Tiles、地形服务、影像服务加载
    - trajectory: 轨迹动画播放
    - amap: 高德地图（地理编码、POI搜索、周边搜索、路径规划、天气）

    调用时机：当核心工具不足以完成任务时，用此工具启用对应分组。
    示例：用户要做缓冲区分析 → discover_gis_tools("spatial_analysis")
    """
    from app.tools._context import get_tool_registry

    registry = get_tool_registry()
    enabled_tools = registry.enable_toolset(category)
    defn = TOOLSET_DEFINITIONS.get(category, {})

    return {
        "category": category,
        "description": defn.get("description", ""),
        "enabled_tools": enabled_tools,
        "count": len(enabled_tools),
        "summary": f"已启用 {category} 工具组（{len(enabled_tools)}个工具）: {', '.join(enabled_tools)}",
    }


def _guess_osm_tag(data_type: str, query: str) -> str:
    """根据 data_type 和 query 猜测 OSM 标签"""
    if data_type == "poi":
        return f"name~{query}"
    elif data_type == "road":
        return "highway=*"
    elif data_type == "building":
        return "building=yes"
    elif data_type == "boundary":
        return "admin_level=4"
    elif data_type == "landuse":
        return "landuse=*"
    return "name=*"
