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
from app.agent.prompts.system_prompt import get_system_prompt, get_context_labels
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


def _build_context_prompt(session_ctx: SessionDataContext, locale: str = "zh-CN") -> str:
    """动态注入当前会话已有的数据引用清单"""
    i = get_context_labels(locale)
    refs = session_ctx.list_refs()
    if not refs:
        return i["empty"]

    labels = i["labels"]
    lines = [i["header"]]
    for ref in refs:
        lines.append(
            f"- data_ref_id=\"{ref['data_ref_id']}\" | "
            f"{labels['type']}: {ref['geometry_type']} | "
            f"{labels['features']}: {ref['feature_count']} | "
            f"{labels['source']}: {ref['source']}"
        )
    lines.append(i["footer"])
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
    locale: Optional[str] = "zh-CN",
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
    context_prompt = _build_context_prompt(session_ctx, locale or "zh-CN")
    system_prompt = get_system_prompt(locale or "zh-CN").format(context_prompt=context_prompt)

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
