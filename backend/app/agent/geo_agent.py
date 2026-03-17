"""GeoAgent 核心：LangGraph ReAct Agent + 动态工具组 + SSE 事件流

职责：
1. 接收用户消息，通过 LLM 逐步决策工具调用
2. 每步工具调用前后发射 tool_call / tool_result SSE 事件
3. 动态工具组：初始 5+1 核心工具，通过 discover_gis_tools 按需启用
4. 多模型路由：根据任务复杂度自动选择 fast/main/enhanced/reasoning
"""

import logging
import time
from typing import Any, AsyncGenerator, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from app.services.llm import get_llm
from app.services.session_context import SessionDataContext, get_session_context
from app.services.gis_adapter import get_gis_adapter
from app.services.runtime_client import push_map_commands
from app.tools._context import set_tool_context
from app.tools.registry import ToolRegistry
from app.tools.core import (
    geocoding,
    fetch_osm_data,
    load_uploaded_file,
    generate_map_command,
    generate_report,
    discover_gis_tools,
)
from app.tools.spatial import (
    buffer_analysis,
    spatial_query,
    overlay_analysis,
    clip_analysis,
)
from app.tools.measurement import distance_calc, area_calc, field_statistics, enrich_geometry_fields
from app.tools.geometry import centroid, convex_hull, simplify_geometry, voronoi
from app.tools.coordinate import transform_crs, convert_point, get_utm_zone
from app.tools.statistics import spatial_statistics, kernel_density, cluster_analysis
from app.tools.visualization import generate_heatmap, generate_choropleth, generate_chart
from app.tools.scene3d import load_3dtiles, load_terrain, load_imagery_service
from app.tools.trajectory import play_trajectory
from app.tools.amap import (
    amap_geocoding,
    amap_poi_search,
    amap_around_search,
    amap_route_planning,
    amap_weather,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是GeoAgent，一个专业的地理空间分析AI助手。

## 工作模式
逐步执行：每次只调用一个工具，等待结果后再决定下一步。
不要一次规划太多步骤，根据每步实际结果动态调整。

## 数据引用规则
- 工具返回结果中包含 data_ref_id，后续步骤通过此ID引用数据
- 绝对不要编造 data_ref_id，只使用系统提供的已有ID
- 当前可用数据：{context_prompt}

## 工具使用规则
所有工具组已激活，可直接调用分析工具：
- **核心**: geocoding, fetch_osm_data, load_uploaded_file, generate_map_command(支持addLabel), generate_report
- **空间分析**: buffer_analysis, spatial_query, overlay_analysis, clip_analysis
- **测量**: distance_calc, area_calc, field_statistics, enrich_geometry_fields
- **几何**: centroid, convex_hull, simplify_geometry, voronoi
- **坐标**: transform_crs, convert_point, get_utm_zone
- **统计**: spatial_statistics, kernel_density, cluster_analysis
- **可视化**: generate_heatmap, generate_choropleth, generate_chart
- **3D场景**: load_3dtiles, load_terrain, load_imagery_service
- **轨迹**: play_trajectory
- **高德地图**: amap_geocoding, amap_poi_search, amap_around_search, amap_route_planning, amap_weather

## 数据源优先级（中国区域）
- **POI搜索**: 必须使用 amap_poi_search / amap_around_search（数据全、中文好、速度快）
- **地理编码**: 必须使用 amap_geocoding（准确率高）
- **路径规划**: 使用 amap_route_planning。起终点坐标必须直接使用 amap_geocoding 返回的坐标或 amap_poi_search 返回的首个POI坐标，**禁止**对搜索结果调用 centroid 计算重心作为起终点
- **天气查询**: 使用 amap_weather
- **行政边界/路网/建筑面**: 仅这类大范围矢量数据才用 fetch_osm_data（Overpass API 国内访问不稳定，非必要不用）
- **国外区域**: POI/地理编码用 geocoding(nominatim) + fetch_osm_data

**关键原则**: 能用高德解决的绝不用 OSM。fetch_osm_data 仅在需要矢量面/线数据（如行政区多边形、路网线段）且高德无法提供时才使用。

## 工具调用示例

### 示例1：加载文件并分析
用户：加载并分析我上传的数据
Step 1 → load_uploaded_file(file_id="xxx") → ref_001（1738个Polygon）
Step 2 → generate_map_command("addGeoJsonLayer", data_ref_id="ref_001") → 地图加载
Step 3 → field_statistics(data_ref_id="ref_001", field="area") → 统计结果
Step 4 → generate_map_command("flyTo", data_ref_id="ref_001") → 飞到数据位置
回复：已加载1738个多边形要素，总面积...

### 示例2：缓冲区查询
用户：北京地铁站500米范围内有多少医院？
Step 1 → fetch_osm_data("poi", "地铁站", "北京") → ref_001
Step 2 → buffer_analysis(data_ref_id="ref_001", distance=500) → ref_002
Step 3 → fetch_osm_data("poi", "医院", "北京") → ref_003
Step 4 → spatial_query("intersects", target_ref="ref_003", mask_ref="ref_002") → ref_004
Step 5 → generate_map_command("addGeoJsonLayer", data_ref_id="ref_004")
回复：北京地铁站500米范围内共有156家医院。

### 示例3：简单操控
用户：飞到上海陆家嘴
Step 1 → geocoding("上海陆家嘴") → 121.4995, 31.2397
Step 2 → generate_map_command("flyTo", longitude=121.4995, latitude=31.2397)
回复：已飞到上海陆家嘴。

### 示例4：路线规划
用户：从天安门到故宫的步行路线
Step 1 → amap_geocoding("天安门") → lon=116.397, lat=39.908
Step 2 → amap_geocoding("故宫") → lon=116.403, lat=39.924
Step 3 → amap_route_planning(origin_longitude=116.397, origin_latitude=39.908, dest_longitude=116.403, dest_latitude=39.924, mode="walking") → ref_route
Step 4 → generate_map_command("addGeoJsonLayer", data_ref_id="ref_route")
回复：已规划步行路线，全程X公里，约X分钟。
**注意**：起终点坐标直接用 amap_geocoding 返回值，不要对 POI 搜索结果算 centroid。

## 上下文数据重用原则（极其重要）
每次调用工具前，必须先检查对话历史中是否已有可直接使用的数据：
1. **坐标值**：前序步骤已返回的经纬度，后续需要时直接引用，不要重新调用 geocoding/amap_geocoding
2. **data_ref_id**：已注册的数据引用可反复使用（缓冲、查询、统计、可视化），不要重新获取同一份数据
3. **计算结果**：距离、面积、统计值等已得到的数值，直接引用，不要重复计算
4. **坐标转换**：已知坐标要转 CRS → 直接调用 convert_point（传入已有坐标值），不要重新地理编码；数据集转 CRS → transform_crs
5. **GeoJSON 属性**：field_statistics 已返回的字段名和值范围，后续 choropleth/chart 直接使用

**反面示例（禁止）**：
- 上一步 amap_geocoding 已返回 (116.39, 39.91)，用户要转 CGCS2000 → ❌ 再调 amap_geocoding → ✅ 直接 convert_point(116.39, 39.91, target_crs="EPSG:4490")
- 上一步 amap_poi_search 已返回 ref_poi_xxx，用户要做缓冲分析 → ❌ 再搜一次 POI → ✅ 直接 buffer_analysis(data_ref_id="ref_poi_xxx")
- 上一步 distance_calc 已返回 5.2km，用户问距离 → ❌ 再算一次 → ✅ 直接引用 5.2km

**注意**：CGCS2000 (EPSG:4490) 与 WGS84 (EPSG:4326) 民用精度差异 <0.1m，可视为相同。

## 注意事项
- 所有坐标使用WGS84 (EPSG:4326)
- 距离计算默认单位为米
- 如果用户没有指定数据源，优先从OSM获取
- 分析结果需要简洁明了，重要数据加粗
- 如果用户要求统计分析（面积、长度等），直接调用对应工具，不需要使用generate_report代替
- 调用 generate_report 时**必须**传入 analysis_summary 参数，写入你对本次分析的完整结论（Markdown 格式），包含分析目的、关键发现、数据特征、空间分布规律等
- 当数据缺少数值字段（如面积、周长）用于可视化时，先调用 enrich_geometry_fields 补充计算字段，再用 generate_choropleth 做专题图
- 用户上传数据后只是存储，你不要主动分析，等用户下达具体指令

## 建议操作（必须遵守）
每次回复最后一行，必须用以下格式给出 2~4 个后续建议操作，帮助用户快速下一步：
<<suggestions:建议操作1|建议操作2|建议操作3>>

示例：
<<suggestions:在地图上展示数据|统计要素面积分布|生成分析报告>>
<<suggestions:缓冲区分析500米|叠加分析医院数据|飞到数据位置>>
"""


def _build_context_prompt(session_ctx: SessionDataContext) -> str:
    """动态注入当前会话已有的数据引用清单"""
    refs = session_ctx.list_refs()
    if not refs:
        return "当前会话中没有已加载的数据。"

    lines = ["当前会话中已有以下数据可供引用："]
    for ref in refs:
        lines.append(
            f"- data_ref_id=\"{ref['data_ref_id']}\" | "
            f"类型: {ref['geometry_type']} | "
            f"要素数: {ref['feature_count']} | "
            f"来源: {ref['source']}"
        )
    lines.append("\n调用工具时，使用 data_ref_id 引用上述数据，不要编造不存在的ID。")
    return "\n".join(lines)


def _build_registry() -> ToolRegistry:
    """构建工具注册表，注册核心工具和工具组工具"""
    registry = ToolRegistry()

    # 核心工具
    registry.register_core("geocoding", geocoding)
    registry.register_core("fetch_osm_data", fetch_osm_data)
    registry.register_core("generate_map_command", generate_map_command)
    registry.register_core("generate_report", generate_report)
    registry.register_core("load_uploaded_file", load_uploaded_file)
    registry.register_core("discover_gis_tools", discover_gis_tools)

    # spatial_analysis 工具组
    registry.register_toolset_tool("spatial_analysis", "buffer_analysis", buffer_analysis)
    registry.register_toolset_tool("spatial_analysis", "spatial_query", spatial_query)
    registry.register_toolset_tool("spatial_analysis", "overlay_analysis", overlay_analysis)
    registry.register_toolset_tool("spatial_analysis", "clip_analysis", clip_analysis)

    # measurement 工具组
    registry.register_toolset_tool("measurement", "distance_calc", distance_calc)
    registry.register_toolset_tool("measurement", "area_calc", area_calc)
    registry.register_toolset_tool("measurement", "field_statistics", field_statistics)
    registry.register_toolset_tool("measurement", "enrich_geometry_fields", enrich_geometry_fields)

    # geometry 工具组
    registry.register_toolset_tool("geometry", "centroid", centroid)
    registry.register_toolset_tool("geometry", "convex_hull", convex_hull)
    registry.register_toolset_tool("geometry", "simplify_geometry", simplify_geometry)
    registry.register_toolset_tool("geometry", "voronoi", voronoi)

    # coordinate 工具组
    registry.register_toolset_tool("coordinate", "transform_crs", transform_crs)
    registry.register_toolset_tool("coordinate", "convert_point", convert_point)
    registry.register_toolset_tool("coordinate", "get_utm_zone", get_utm_zone)

    # statistics 工具组
    registry.register_toolset_tool("statistics", "spatial_statistics", spatial_statistics)
    registry.register_toolset_tool("statistics", "kernel_density", kernel_density)
    registry.register_toolset_tool("statistics", "cluster_analysis", cluster_analysis)

    # visualization 工具组
    registry.register_toolset_tool("visualization", "generate_heatmap", generate_heatmap)
    registry.register_toolset_tool("visualization", "generate_choropleth", generate_choropleth)
    registry.register_toolset_tool("visualization", "generate_chart", generate_chart)

    # scene3d 工具组
    registry.register_toolset_tool("scene3d", "load_3dtiles", load_3dtiles)
    registry.register_toolset_tool("scene3d", "load_terrain", load_terrain)
    registry.register_toolset_tool("scene3d", "load_imagery_service", load_imagery_service)

    # trajectory 工具组
    registry.register_toolset_tool("trajectory", "play_trajectory", play_trajectory)

    # amap 高德地图工具组
    registry.register_toolset_tool("amap", "amap_geocoding", amap_geocoding)
    registry.register_toolset_tool("amap", "amap_poi_search", amap_poi_search)
    registry.register_toolset_tool("amap", "amap_around_search", amap_around_search)
    registry.register_toolset_tool("amap", "amap_route_planning", amap_route_planning)
    registry.register_toolset_tool("amap", "amap_weather", amap_weather)

    return registry


async def run_agent_stream(
    session_id: str,
    user_message: str,
    history: Optional[list[dict]] = None,
    model_override: Optional[str] = None,
    temperature: float = 0.3,
    api_key_override: Optional[str] = None,
    base_url_override: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """运行 Agent 并以 SSE 事件流形式输出

    Yields:
        dict: SSE 事件，格式如 {"type": "tool_call", ...} 或 {"type": "text", ...}
    """
    # 1. 获取会话上下文
    session_ctx = get_session_context(session_id)

    # 2. 构建工具注册表（MVP阶段预激活所有工具组）
    registry = _build_registry()
    registry.enable_all_toolsets()

    # 3. 设置工具执行上下文（contextvars）
    set_tool_context(session_ctx, registry)

    # 4. 构建 System Prompt
    context_prompt = _build_context_prompt(session_ctx)
    system_prompt = SYSTEM_PROMPT.format(context_prompt=context_prompt)

    # 5. 获取 LLM
    llm = get_llm(tier="main", temperature=temperature, user_override=model_override, api_key_override=api_key_override, base_url_override=base_url_override)

    # 6. 构建 Agent（使用当前激活的工具）
    tools = registry.get_active_tools()
    agent = create_react_agent(llm, tools, prompt=system_prompt)

    # 7. 构建历史消息 + 当前用户消息
    step_counter = 0
    messages = []
    if history:
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content:
                continue
            # 截断过长的历史消息以控制 token
            if len(content) > 2000:
                content = content[:2000] + "\n...[truncated]"
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_message))
    input_messages = {"messages": messages}

    try:
        async for event in agent.astream_events(input_messages, version="v2"):
            kind = event.get("event", "")

            # LLM 流式输出
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk:
                    # DeepSeek reasoning_content → thinking 事件
                    rc = getattr(chunk, "additional_kwargs", {}).get("reasoning_content")
                    if rc:
                        yield {"type": "thinking", "content": rc}
                    if hasattr(chunk, "content") and chunk.content:
                        yield {"type": "text", "content": chunk.content, "done": False}

            # 工具调用开始
            elif kind == "on_tool_start":
                step_counter += 1
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                yield {
                    "type": "tool_call",
                    "step": step_counter,
                    "tool_name": tool_name,
                    "tool_args": tool_input,
                    "description": f"正在执行 {tool_name}...",
                }

            # 工具调用完成
            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown")
                output = event.get("data", {}).get("output")
                tool_result = _parse_tool_output(output)

                success = not isinstance(tool_result, dict) or "error" not in tool_result
                # 构建精简版结果（排除大型数据体，保留元信息+采样数据）
                result_detail = None
                if isinstance(tool_result, dict):
                    result_detail = {k: v for k, v in tool_result.items() if k != "geojson"}
                    # 从上下文中提取采样数据（前5条 feature 的 properties）
                    dri = tool_result.get("data_ref_id")
                    if dri:
                        try:
                            from app.tools._context import get_tool_context
                            raw = get_tool_context().get(dri)
                            if isinstance(raw, dict) and "features" in raw:
                                sample = [f.get("properties", {}) for f in raw["features"][:5]]
                                result_detail["sample_data"] = sample
                                result_detail["sample_note"] = f"前{len(sample)}条（共{len(raw['features'])}条）"
                        except Exception:
                            pass
                else:
                    result_detail = {"raw": str(tool_result)[:2000]}
                yield {
                    "type": "tool_result",
                    "step": step_counter,
                    "tool_name": tool_name,
                    "success": success,
                    "summary": tool_result.get("summary", str(tool_result)[:200]) if isinstance(tool_result, dict) else str(tool_result)[:200],
                    "data_ref_id": tool_result.get("data_ref_id") if isinstance(tool_result, dict) else None,
                    "preview": _build_preview(tool_result) if isinstance(tool_result, dict) else None,
                    "error": tool_result.get("error") if isinstance(tool_result, dict) and not success else None,
                    "result": result_detail,
                    "duration_ms": None,
                }

                # generate_report 结果：推送 report 事件
                if tool_name == "generate_report" and isinstance(tool_result, dict) and "content" in tool_result:
                    yield {
                        "type": "report",
                        "content": tool_result["content"],
                        "format": tool_result.get("format", "markdown"),
                    }

                # map_command 通过 cesium-mcp-runtime WebSocket 推送到浏览器
                drained_cmds = session_ctx.drain_map_commands()
                if drained_cmds:
                    logger.info("[map_cmd] drained %d cmds, pushing to runtime...", len(drained_cmds))
                    pushed = await push_map_commands(drained_cmds, session_id)
                    logger.info("[map_cmd] push result: %s", pushed)
                    if not pushed:
                        logger.info("[map_cmd] SSE fallback: yielding %d map_command events", len(drained_cmds))
                        for cmd in drained_cmds:
                            yield {"type": "map_command", "command": cmd}

                # chart_option 自动推送（ECharts 配置走边信道）
                for chart in session_ctx.drain_chart_options():
                    yield {
                        "type": "chart_option",
                        "chart": chart,
                    }

    except Exception as e:
        error_msg = str(e)
        logger.error("Agent 流式执行异常: %s", error_msg)
        if "429" in error_msg or "rate" in error_msg.lower() or "limit" in error_msg.lower():
            yield {
                "type": "error",
                "message": "模型调用频率超限，请稍后重试。如频繁出现，可在设置中切换其他模型。",
            }
        elif "401" in error_msg or "auth" in error_msg.lower():
            yield {
                "type": "error",
                "message": "模型 API Key 无效或已过期，请检查后端 .env 配置。",
            }
        elif "timeout" in error_msg.lower():
            yield {
                "type": "error",
                "message": "模型响应超时，请稍后重试或尝试简化问题。",
            }
        else:
            yield {
                "type": "error",
                "message": f"AI 处理异常：{error_msg[:200]}",
            }

    # 最终 done 事件
    yield {"type": "done", "session_id": session_id}


def _parse_tool_output(output: Any) -> Any:
    """解析工具输出"""
    raw = output
    if hasattr(output, "content"):
        raw = output.content
    if isinstance(raw, str):
        try:
            import json
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
    return raw


def _build_preview(result: dict) -> Optional[dict]:
    """从工具结果构建前端预览信息"""
    if not isinstance(result, dict):
        return None
    preview = {}
    if "feature_count" in result:
        preview["feature_count"] = result["feature_count"]
    if "geometry_type" in result:
        preview["geometry_type"] = result["geometry_type"]
    if "bbox" in result:
        preview["bbox"] = result["bbox"]
    if "properties" in result:
        preview["sample_properties"] = result["properties"][:5]
    return preview if preview else None
