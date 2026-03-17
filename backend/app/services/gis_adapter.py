"""GisToolAdapter: gis-mcp 与 SessionDataContext 之间的 data_ref_id 桥接层

职责：
1. resolve_ref: data_ref_id → GeoJSON（从 SessionDataContext 取出原始数据）
2. call_gis_tool: 代理调用 gis-mcp 工具（自动处理 WKT / 文件路径 / JSON 格式转换）
3. store_result: 执行结果 → SessionDataContext → 返回新 data_ref_id + 摘要

gis-mcp 工具有三类输入格式：
- WKT:  shapely wkt.loads(geometry)  → get_centroid, buffer, convex_hull, simplify, voronoi, project_geometry ...
- FILE: gpd.read_file(path)          → sjoin_gpd, overlay_gpd, clip_vector, dissolve_gpd, merge_gpd ...
- JSON: json.loads(data)             → 默认（少数工具）
"""

import json
import logging
import os
import tempfile
from typing import Any, Literal, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

from app.services.session_context import SessionDataContext

logger = logging.getLogger(__name__)

GIS_MCP_SERVER = StdioServerParameters(
    command="python",
    args=["-c", "from gis_mcp.main import gis_mcp; gis_mcp.run(transport='stdio')"],
)

# gis-mcp 工具按输入格式分类
_WKT_TOOLS = {
    "get_centroid", "buffer", "convex_hull", "simplify", "voronoi",
    "project_geometry", "envelope", "minimum_rotated_rectangle",
    "is_valid", "make_valid", "normalize_geometry",
    "rotate_geometry", "scale_geometry", "translate_geometry", "snap_geometry",
    "difference", "intersection", "union", "symmetric_difference",
    "unary_union_geometries", "triangulate_geometry",
    "nearest_point_on_geometry", "get_coordinates", "get_geometry_type",
    "get_area", "get_length", "get_bounds",
}

_FILE_TOOLS = {
    "sjoin_gpd", "sjoin_nearest_gpd", "overlay_gpd", "clip_vector",
    "dissolve_gpd", "merge_gpd", "append_gpd", "explode_gpd",
    "read_file_gpd", "write_file_gpd", "concat_bands",
}

RefFormat = Literal["wkt", "file", "json"]


class GisToolAdapter:
    """gis-mcp 与 SessionDataContext 之间的桥接层"""

    def __init__(self, session_ctx: SessionDataContext):
        self.ctx = session_ctx
        self._mcp_session: Optional[ClientSession] = None
        self._temp_files: list[str] = []

    async def connect(self):
        """建立与 gis-mcp Server 的 MCP 连接"""
        if self._mcp_session is not None:
            return
        self._stdio_ctx = stdio_client(GIS_MCP_SERVER)
        self._streams = await self._stdio_ctx.__aenter__()
        read_stream, write_stream = self._streams
        self._mcp_session_ctx = ClientSession(read_stream, write_stream)
        self._mcp_session = await self._mcp_session_ctx.__aenter__()
        await self._mcp_session.initialize()
        logger.info("gis-mcp MCP 连接已建立")

    async def disconnect(self):
        """关闭 MCP 连接"""
        if self._mcp_session is not None:
            await self._mcp_session_ctx.__aexit__(None, None, None)
            await self._stdio_ctx.__aexit__(None, None, None)
            self._mcp_session = None
            logger.info("gis-mcp MCP 连接已关闭")
        self._cleanup_temp_files()

    def _cleanup_temp_files(self):
        for path in self._temp_files:
            try:
                os.unlink(path)
            except OSError:
                pass
        self._temp_files.clear()

    async def list_tools(self) -> list[dict]:
        """列出 gis-mcp 提供的所有工具"""
        await self.connect()
        result = await self._mcp_session.list_tools()
        return [
            {"name": t.name, "description": t.description}
            for t in result.tools
        ]

    def resolve_ref(self, ref_id: str) -> dict:
        """data_ref_id → GeoJSON dict，失败时抛出 ValueError"""
        geojson = self.ctx.get(ref_id)
        if geojson is None:
            available = [r["data_ref_id"] for r in self.ctx.list_refs()]
            raise ValueError(
                f"data_ref_id '{ref_id}' 不存在。可用: {available}"
            )
        return geojson

    def _geojson_to_wkt(self, geojson: dict) -> str:
        """GeoJSON FeatureCollection → unary_union → WKT 字符串"""
        features = geojson.get("features", [])
        geoms = [shape(f["geometry"]) for f in features if f.get("geometry")]
        if not geoms:
            raise ValueError("GeoJSON 中没有有效几何要素")
        return unary_union(geoms).wkt

    def _geojson_to_file(self, geojson: dict) -> str:
        """GeoJSON → 临时 .geojson 文件路径"""
        fd, path = tempfile.mkstemp(suffix=".geojson", prefix="gis_mcp_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(geojson, f)
        self._temp_files.append(path)
        return path

    def _detect_format(self, gis_tool_name: str) -> RefFormat:
        """根据工具名自动判断参数格式"""
        if gis_tool_name in _WKT_TOOLS:
            return "wkt"
        if gis_tool_name in _FILE_TOOLS:
            return "file"
        return "json"

    def _wkt_result_to_geojson(self, result_data: dict) -> dict | None:
        """将 gis-mcp WKT 结果转为 GeoJSON FeatureCollection"""
        wkt_str = result_data.get("geometry")
        if not wkt_str or not isinstance(wkt_str, str):
            return None
        from shapely import wkt
        geom = wkt.loads(wkt_str)
        if geom.geom_type in ("GeometryCollection", "MultiPoint", "MultiLineString", "MultiPolygon"):
            features = [
                {"type": "Feature", "geometry": mapping(g), "properties": {"index": i}}
                for i, g in enumerate(geom.geoms)
            ]
        else:
            features = [{"type": "Feature", "geometry": mapping(geom), "properties": {}}]
        return {"type": "FeatureCollection", "features": features}

    def store_result(self, geojson: dict, source: str) -> dict:
        """GeoJSON → 存入 SessionDataContext → 返回 summary dict"""
        ref_id = self.ctx.register(geojson, source=source)
        summary = self.ctx.summary(ref_id)
        return {"data_ref_id": ref_id, **summary}

    async def call_gis_tool(
        self,
        gis_tool_name: str,
        ref_params: dict[str, str],
        extra_params: dict[str, Any],
        source_label: Optional[str] = None,
        ref_format: Optional[RefFormat] = None,
    ) -> dict:
        """代理调用 gis-mcp 工具

        Args:
            gis_tool_name: gis-mcp 工具名（如 "buffer", "sjoin_gpd"）
            ref_params: 需要解析的引用参数 {"geometry": "ref_001"}
            extra_params: 直接传递的参数 {"distance": 500}
            source_label: 存储来源标签，不传则自动生成
            ref_format: 强制指定格式（不传则自动检测）

        Returns:
            {"data_ref_id": "ref_xxx", "feature_count": N, ...}
        """
        await self.connect()

        fmt = ref_format or self._detect_format(gis_tool_name)

        # 1. data_ref_id → 按格式转换
        resolved = {}
        for param_name, ref_id in ref_params.items():
            geojson = self.resolve_ref(ref_id)
            if fmt == "wkt":
                resolved[param_name] = self._geojson_to_wkt(geojson)
            elif fmt == "file":
                resolved[param_name] = self._geojson_to_file(geojson)
            else:
                resolved[param_name] = json.dumps(geojson)

        # 2. 合并参数，调用 gis-mcp
        call_args = {**resolved, **extra_params}
        logger.info("gis-mcp call: %s(%s) format=%s", gis_tool_name, list(call_args.keys()), fmt)

        try:
            result = await self._mcp_session.call_tool(gis_tool_name, call_args)
        except Exception as e:
            logger.exception("gis-mcp %s 调用异常", gis_tool_name)
            return {"error": f"gis-mcp 工具 {gis_tool_name} 调用失败: {e}"}

        # 3. 拼接所有 content 块的文本
        texts = []
        for block in (result.content or []):
            texts.append(block.text if hasattr(block, "text") else str(block))
        result_text = "\n".join(texts).strip()

        # 4. MCP 协议级错误
        if getattr(result, "isError", False):
            logger.warning("gis-mcp %s 返回错误: %s", gis_tool_name, result_text[:300])
            return {"error": f"gis-mcp {gis_tool_name} 执行失败", "detail": result_text}

        # 5. 空响应
        if not result_text:
            logger.warning("gis-mcp %s 返回空响应", gis_tool_name)
            return {"error": f"gis-mcp 工具 {gis_tool_name} 返回空响应，可能参数不匹配或工具内部错误"}

        # 6. JSON 解析
        try:
            result_data = json.loads(result_text)
        except json.JSONDecodeError:
            logger.warning("gis-mcp %s 返回非JSON: %s", gis_tool_name, result_text[:300])
            return {"error": f"gis-mcp {gis_tool_name} 返回非JSON结果", "detail": result_text[:1000]}

        # 7. 结果后处理
        label = source_label or f"gis-mcp:{gis_tool_name}({','.join(ref_params.values())})"

        # 7a. 已经是 GeoJSON → 直接存
        if self._is_geojson(result_data):
            return self.store_result(result_data, source=label)

        # 7b. WKT 结果（含 "geometry" 字段为 WKT 字符串）→ 转 GeoJSON 存
        if fmt == "wkt" and "geometry" in result_data and isinstance(result_data.get("geometry"), str):
            geojson = self._wkt_result_to_geojson(result_data)
            if geojson:
                stored = self.store_result(geojson, source=label)
                # 保留原始结果中的非几何字段（status, message 等）
                for k, v in result_data.items():
                    if k != "geometry" and k not in stored:
                        stored[k] = v
                return stored

        # 7c. FILE 工具返回了 output_path → 读取文件存入
        output_path = result_data.get("output_path") or result_data.get("output")
        if fmt == "file" and output_path and os.path.isfile(output_path):
            import geopandas as _gpd
            gdf = _gpd.read_file(output_path)
            geojson = json.loads(gdf.to_json())
            stored = self.store_result(geojson, source=label)
            for k, v in result_data.items():
                if k not in ("output_path", "output") and k not in stored:
                    stored[k] = v
            return stored

        # 非空间结果直接返回
        return result_data

    @staticmethod
    def _is_geojson(data: Any) -> bool:
        """判断数据是否为 GeoJSON FeatureCollection 或 Feature"""
        if not isinstance(data, dict):
            return False
        dtype = data.get("type", "")
        return dtype in ("FeatureCollection", "Feature", "GeometryCollection")


# --- 全局 Adapter 实例管理 ---

_adapters: dict[str, GisToolAdapter] = {}


def get_gis_adapter(session_ctx: SessionDataContext) -> GisToolAdapter:
    """获取指定会话的 GisToolAdapter（复用连接）"""
    sid = session_ctx.session_id
    if sid not in _adapters:
        _adapters[sid] = GisToolAdapter(session_ctx)
    return _adapters[sid]


async def cleanup_gis_adapter(session_id: str):
    """清理指定会话的 Adapter 连接"""
    adapter = _adapters.pop(session_id, None)
    if adapter:
        await adapter.disconnect()
