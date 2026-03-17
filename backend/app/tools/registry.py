"""工具注册表 + 动态工具组管理

核心概念：
- CORE_TOOLS: 始终可见的工具（5+1个）
- TOOLSETS: 按需启用的工具分组
- ToolRegistry: 管理当前会话已启用的工具集
"""

from typing import Callable

# 工具组定义：组名 → 工具函数名列表
TOOLSET_DEFINITIONS = {
    "spatial_analysis": {
        "description": "缓冲区、空间查询、叠加分析、裁剪",
        "tools": ["buffer_analysis", "spatial_query", "overlay_analysis", "clip_analysis"],
    },
    "measurement": {
        "description": "距离计算、面积计算、字段统计",
        "tools": ["distance_calc", "area_calc", "field_statistics", "enrich_geometry_fields"],
    },
    "geometry": {
        "description": "质心、凸包、简化、泰森多边形",
        "tools": ["centroid", "convex_hull", "simplify_geometry", "voronoi"],
    },
    "coordinate": {
        "description": "坐标转换（数据集/单点）、UTM分区",
        "tools": ["transform_crs", "convert_point", "get_utm_zone"],
    },
    "visualization": {
        "description": "热力图、填色图、统计图表",
        "tools": ["generate_heatmap", "generate_choropleth", "generate_chart"],
    },
    "statistics": {
        "description": "空间统计、核密度、聚类分析",
        "tools": ["spatial_statistics", "kernel_density", "cluster_analysis"],
    },
    "scene3d": {
        "description": "3D Tiles、地形服务、影像服务加载",
        "tools": ["load_3dtiles", "load_terrain", "load_imagery_service"],
    },
    "trajectory": {
        "description": "轨迹动画播放",
        "tools": ["play_trajectory"],
    },
    "amap": {
        "description": "高德地图（地理编码、POI搜索、周边搜索、路径规划、天气）",
        "tools": ["amap_geocoding", "amap_poi_search", "amap_around_search", "amap_route_planning", "amap_weather"],
    },
}


class ToolRegistry:
    """管理当前会话已启用的工具集"""

    def __init__(self):
        self._core_tools: dict[str, Callable] = {}
        self._toolset_tools: dict[str, dict[str, Callable]] = {}
        self._active_toolsets: set[str] = set()

    def register_core(self, name: str, tool_fn: Callable):
        """注册核心工具（始终可见）"""
        self._core_tools[name] = tool_fn

    def register_toolset_tool(self, toolset: str, name: str, tool_fn: Callable):
        """注册工具组中的工具"""
        if toolset not in self._toolset_tools:
            self._toolset_tools[toolset] = {}
        self._toolset_tools[toolset][name] = tool_fn

    def enable_toolset(self, toolset_name: str) -> list[str]:
        """启用一个工具组，返回新增的工具名列表"""
        if toolset_name not in TOOLSET_DEFINITIONS:
            return []
        if toolset_name in self._active_toolsets:
            return list(self._toolset_tools.get(toolset_name, {}).keys())

        self._active_toolsets.add(toolset_name)
        return list(self._toolset_tools.get(toolset_name, {}).keys())

    def get_active_tools(self) -> list[Callable]:
        """获取当前所有可用工具（核心 + 已启用的工具组）"""
        tools = list(self._core_tools.values())
        for ts_name in self._active_toolsets:
            ts_tools = self._toolset_tools.get(ts_name, {})
            tools.extend(ts_tools.values())
        return tools

    def enable_all_toolsets(self):
        """启用所有已注册的工具组"""
        for ts_name in self._toolset_tools:
            self._active_toolsets.add(ts_name)

    def get_active_toolsets(self) -> list[str]:
        """获取当前已启用的工具组名列表"""
        return list(self._active_toolsets)

    def get_available_toolsets(self) -> dict[str, str]:
        """获取所有可用工具组及其描述"""
        return {
            name: defn["description"]
            for name, defn in TOOLSET_DEFINITIONS.items()
        }
