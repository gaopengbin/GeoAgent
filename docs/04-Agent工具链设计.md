# Agent工具链设计

## 1. 工具体系总览

GeoAgent 采用 **MCP-first + 动态工具组** 架构：

- **GIS 空间分析**：由 [gis-mcp](https://github.com/mahdin75/gis-mcp)（103个原子工具）通过 MCP Client 调用
- **业务工具**：自建 @tool（geocoding/数据获取/地图指令/报告），直接集成
- **桥接层**：GisToolAdapter 在 data_ref_id 与 gis-mcp 原始数据之间做适配
- **动态加载**：Agent 初始只看到 5+1 个工具，通过 `discover_gis_tools` 元工具按需启用工具组

### 1.1 工具架构

```
LangGraph Agent (ReAct)
  │ 可见：5个核心工具 + discover_gis_tools
  │
  ├─ 自建 @tool ─────────────────────┐
  │   geocoding / fetch_osm_data     │ 直接执行
  │   generate_map_command           │
  │   generate_report                │
  │                                  │
  ├─ discover_gis_tools("spatial")   │ 按需启用
  │   └→ buffer_analysis             │
  │   └→ spatial_query               │
  │   └→ overlay_analysis            │
  │                                  │
  └─ GisToolAdapter ─────────────────┤ data_ref_id 桥接
      │ resolve_ref → 原始数据       │
      │ call_gis_tool → MCP Client   │
      │ store_result → 新 ref_id     │
      └→ gis-mcp Server (103 tools)  │
```

### 1.2 工具分组总表

#### 核心工具（始终可见，5+1个）

| 工具名 | 功能 | 实现方式 |
|--------|------|---------|
| `geocoding` | 地名→坐标 | 自建（天地图/Nominatim API） |
| `fetch_osm_data` | 从OSM获取POI/路网/建筑等 | 自建（Overpass API） |
| `load_uploaded_file` | 加载用户上传的文件 | 自建（文件解析） |
| `generate_map_command` | 生成前端地图操控指令 | 自建（SSE推送） |
| `generate_report` | 生成Markdown分析报告 | 自建（LLM生成） |
| `discover_gis_tools` | 🔑 元工具：按需启用工具组 | 自建（动态注册） |

#### 动态工具组（按需启用）

| 组名 | 工具 | gis-mcp 对应工具 | 优先级 |
|------|------|-----------------|--------|
| **spatial_analysis** | `buffer_analysis` | buffer | MVP |
| | `spatial_query` | sjoin_gpd / point_in_polygon | MVP |
| | `overlay_analysis` | overlay_gpd | MVP |
| | `clip_analysis` | clip_vector | MVP |
| **measurement** | `distance_calc` | calculate_geodetic_distance | MVP |
| | `area_calc` | calculate_geodetic_area | MVP |
| | `field_statistics` | dissolve_gpd | P1 |
| **geometry** | `centroid` | get_centroid | P1 |
| | `convex_hull` | convex_hull | P1 |
| | `simplify` | simplify | P1 |
| | `voronoi` | voronoi | P2 |
| **coordinate** | `transform_crs` | transform_coordinates / project_geometry | P1 |
| | `get_utm_zone` | get_utm_zone | P1 |
| **visualization** | `generate_heatmap` | — (自建，Cesium热力图指令) | MVP |
| | `generate_choropleth` | — (自建，填色图指令) | P1 |
| | `generate_chart` | — (自建，ECharts数据) | P1 |
| **statistics** | `spatial_statistics` | get_bounds / get_area / get_length | MVP |
| | `kernel_density` | — (自建，scipy KDE) | P1 |
| | `cluster_analysis` | — (自建，sklearn DBSCAN/KMeans) | P1 |
| **3d_display** | `load_3dtiles` | — (自建，Cesium指令) | P2 |
| | `load_terrain` | — (自建，Cesium指令) | P2 |
| | `load_imagery_service` | — (自建，Cesium指令) | P2 |

---

## 2. 各工具详细设计

### 2.1 fetch_osm_data — OSM数据获取

**功能：** 通过Overpass API从OpenStreetMap获取指定区域的空间数据。

```python
@tool
def fetch_osm_data(
    data_type: str,      # "poi" | "road" | "building" | "boundary" | "landuse"
    query: str,          # 搜索关键词，如 "地铁站", "医院", "公园"
    area: str,           # 区域名称，如 "北京", "北京市朝阳区"
    bbox: list = None,   # 可选，[west, south, east, north]
    limit: int = 5000    # 最大返回数量
) -> dict:
    """从OpenStreetMap获取空间数据。

    使用场景：需要获取某区域的POI、路网、建筑、边界、用地数据时使用。
    示例：fetch_osm_data("poi", "地铁站", "北京")

    返回：data_ref_id + 摘要（不含全量数据）
    {
        "data_ref_id": "ref_osm_abc12345",
        "feature_count": 326,
        "geometry_type": "Point",
        "bbox": [116.12, 39.68, 116.78, 40.18],
        "properties": ["name", "line", "operator"],
        "summary": "从OSM获取到326个地铁站"
    }
    """
```

**Overpass查询映射：**

| data_type | query示例 | Overpass标签 |
|-----------|----------|-------------|
| poi | 地铁站 | `railway=station` |
| poi | 医院 | `amenity=hospital` |
| poi | 学校 | `amenity=school` |
| poi | 公园 | `leisure=park` |
| road | 高速公路 | `highway=motorway` |
| building | 建筑 | `building=yes` |
| boundary | 北京 | `admin_level=4, name=北京` |
| landuse | 绿地 | `landuse=grass\|forest\|recreation_ground` |

**实现要点：**
- 使用 `osmnx` 或直接调 Overpass API
- 结果缓存到Redis（同一查询24h内复用）
- 大数据量自动简化（> 5000要素时启用Douglas-Peucker）

---

### 2.2 fetch_tianditu — 天地图服务

**功能：** 调用天地图API进行地理编码和POI搜索。

```python
@tool
def fetch_tianditu(
    service: str,        # "geocode" | "search" | "reverse"
    query: str,          # 地名/地址/关键词
    city: str = None,    # 城市限定
    bounds: list = None  # 范围限定 [west, south, east, north]
) -> dict:
    """
    调用天地图API。
    
    geocode返回:
    {
        "location": {"longitude": 116.397, "latitude": 39.908},
        "address": "北京市东城区天安门",
        "level": "poi"
    }
    
    search返回:
    {
        "type": "FeatureCollection",
        "features": [...],
        "total": 156
    }
    """
```

---

### 2.3 load_uploaded_file — 加载上传文件

**功能：** 解析用户上传的空间数据文件。

```python
@tool
def load_uploaded_file(
    file_id: str,        # 上传接口返回的file_id
    crs: str = "EPSG:4326"  # 坐标系
) -> dict:
    """
    加载并解析空间数据文件。
    
    支持格式: GeoJSON, CSV(含经纬度列), Excel(.xlsx/.xls), KML, KMZ, GPX, Shapefile(zip)
    智能能力: 自动识别坐标列、自动检测编码、地址列自动geocoding、坐标系自动推断
    
    返回:
    {
        "type": "FeatureCollection",
        "features": [...],
        "metadata": {
            "filename": "data.geojson",
            "feature_count": 156,
            "geometry_type": "Point",
            "properties": ["name", "type", "value"],
            "bbox": [...]
        }
    }
    """
```

**格式解析逻辑：**

| 格式 | 解析库 | 特殊处理 |
|------|--------|---------|
| GeoJSON | json (内置) | 验证GeoJSON schema；嵌套在普通JSON中时递归扫描提取FeatureCollection |
| CSV | pandas | 自动匹配坐标列（lon/lng/longitude/经度/x 等别名）；chardet检测编码 |
| Excel (.xlsx/.xls) | openpyxl/pandas | 同CSV坐标识别；多Sheet时扫描含坐标列的Sheet |
| KML | fastkml / lxml | 提取Placemark |
| KMZ | zipfile + fastkml | 解压后按KML处理 |
| GPX | gpxpy | 提取Track/Waypoint |
| Shapefile | geopandas + fiona | 需zip打包，自动处理编码 |

**智能识别策略：**

| 场景 | 处理方式 |
|------|----------|
| 坐标列名不统一 | 预设别名表匹配：lon/lng/longitude/经度/x, lat/latitude/纬度/y 等 |
| 只有地址列无坐标 | 检测到文本地址列后，自动批量geocoding（天地图/Nominatim）转为坐标 |
| 文件编码混乱 | chardet自动检测（UTF-8/GBK/GB2312/Latin-1） |
| 坐标系不明 | 根据坐标数值范围自动推断：WGS84/GCJ-02/BD-09/CGCS2000 |
| GeoJSON嵌套 | 递归扫描JSON结构，定位type=FeatureCollection的节点 |

---

### 2.4 buffer_analysis — 缓冲区分析

**功能：** 对输入要素生成指定距离的缓冲区。

**所属工具组：** `spatial_analysis`（需先调用 `discover_gis_tools("spatial_analysis")` 启用）

**gis-mcp 映射：** `buffer`

```python
@tool
def buffer_analysis(
    data_ref_id: str,    # 输入数据引用ID
    distance: float,     # 缓冲距离
    unit: str = "m",     # "m" | "km"
    merge: bool = True   # 是否合并重叠缓冲区
) -> dict:
    """对指定图层创建缓冲区。

    使用场景：当用户说"XX范围内"、"周围XX米"、"服务半径"时使用。
    需要先用 discover_gis_tools("spatial_analysis") 启用此工具。

    示例：
    - "地铁站500米范围内" → buffer_analysis(data_ref_id="ref_001", distance=500)
    - "公园周围2公里" → buffer_analysis(data_ref_id="ref_parks", distance=2, unit="km")

    内部流程：
    1. GisToolAdapter.resolve_ref(data_ref_id) → 取出GeoJSON
    2. 转WKT → MCP Client → gis-mcp: buffer(geometry, distance)
    3. 结果存入SessionDataContext → 返回新data_ref_id

    返回：
    {
        "data_ref_id": "ref_buffer_xyz",
        "feature_count": 1,
        "geometry_type": "Polygon",
        "bbox": [...],
        "summary": "创建了326个地铁站的500m缓冲区，合并后为1个多边形"
    }
    """
```

---

### 2.5 spatial_query — 空间查询

**功能：** 执行空间关系查询。

**所属工具组：** `spatial_analysis`

**gis-mcp 映射：** `sjoin_gpd` / `point_in_polygon`

```python
@tool
def spatial_query(
    method: str,             # "within" | "intersects" | "contains" | "near"
    target_ref: str,         # 被查询数据的 data_ref_id
    mask_ref: str,           # 参考/掩膜数据的 data_ref_id
    distance: float = None   # 仅当method="near"时，指定距离（米）
) -> dict:
    """空间关系查询：筛选满足空间关系的要素。

    使用场景：当用户说"在XX内的"、"与XX相交的"、"离XX最近的"时使用。

    示例：
    - "缓冲区内的住宅" → spatial_query("within", target_ref="ref_residential", mask_ref="ref_buffer")
    - "与河流相交的道路" → spatial_query("intersects", target_ref="ref_roads", mask_ref="ref_rivers")

    返回：
    {
        "data_ref_id": "ref_query_result",
        "feature_count": 1234,
        "geometry_type": "Point",
        "bbox": [...],
        "summary": "5000个住宅中有1234个在缓冲区内（匹配率24.7%）"
    }
    """
```

---

### 2.6 overlay_analysis — 叠加分析

**所属工具组：** `spatial_analysis`

**gis-mcp 映射：** `overlay_gpd`

```python
@tool
def overlay_analysis(
    ref_a: str,          # 数据集A 的 data_ref_id
    ref_b: str,          # 数据集B 的 data_ref_id
    operation: str       # "intersection" | "union" | "difference" | "symmetric_difference"
) -> dict:
    """空间叠加分析。

    使用场景：求两个区域的重叠/合并/差异。
    示例：overlay_analysis(ref_a="ref_green", ref_b="ref_plan", operation="intersection")

    返回：
    {
        "data_ref_id": "ref_overlay_xyz",
        "feature_count": 42,
        "geometry_type": "Polygon",
        "summary": "intersection完成，结果面积45.2km²"
    }
    """
```

---

### 2.7 distance_calc — 距离计算

**所属工具组：** `measurement`

**gis-mcp 映射：** `calculate_geodetic_distance`

```python
@tool
def distance_calc(
    data_ref_id: str,            # 输入数据引用ID
    target_point: list = None,   # 目标点 [lon, lat]，不传则计算要素间距离
    unit: str = "m"              # "m" | "km"
) -> dict:
    """计算空间距离。

    使用场景：当用户说"离XX多远"、"到XX的距离"时使用。
    示例：distance_calc(data_ref_id="ref_001", target_point=[116.4, 39.9])

    返回：
    {
        "data_ref_id": "ref_dist_xyz",
        "statistics": {"min": 123.4, "max": 15678.9, "mean": 4567.8},
        "summary": "326个要素到目标点的平均距离4.6km"
    }
    """
```

---

### 2.8 kernel_density — 核密度估计

**所属工具组：** `statistics`

**gis-mcp 映射：** —（自建，scipy gaussian_kde）

```python
@tool
def kernel_density(
    data_ref_id: str,        # 点数据引用ID
    cell_size: float = 100,  # 网格大小（米）
    radius: float = 1000,    # 搜索半径（米）
    weight_field: str = None # 权重字段
) -> dict:
    """核密度估计，用于分析空间聚集程度。

    使用场景：当用户说"分布密度"、"热力图"、"哪里最集中"时使用。
    示例：kernel_density(data_ref_id="ref_subway", radius=1000)

    返回：
    {
        "data_ref_id": "ref_kde_xyz",
        "hotspots": [{"center": [116.45, 39.92], "density": 0.95}],
        "summary": "核密度估计完成，最高密度区域在国贸附近"
    }
    """
```

---

### 2.9 cluster_analysis — 空间聚类

**所属工具组：** `statistics`

**gis-mcp 映射：** —（自建，sklearn DBSCAN/KMeans）

```python
@tool
def cluster_analysis(
    data_ref_id: str,        # 点数据引用ID
    method: str = "dbscan",  # "dbscan" | "kmeans"
    eps: float = 500,        # DBSCAN邻域距离（米）
    min_samples: int = 5,    # DBSCAN最小点数
    n_clusters: int = None   # KMeans聚类数
) -> dict:
    """空间聚类分析。

    使用场景：当用户说"聚集区域"、"分群"、"聚类"时使用。
    示例：cluster_analysis(data_ref_id="ref_poi", method="dbscan", eps=500)

    返回：
    {
        "data_ref_id": "ref_cluster_xyz",
        "cluster_count": 5,
        "noise_count": 12,
        "clusters": [{"id": 0, "count": 45, "center": [116.45, 39.92]}],
        "summary": "DBSCAN聚类完成，发现5个聚集区域，12个离散点"
    }
    """
```

---

### 2.10 geocoding — 地理编码

**核心工具**（始终可见）

```python
@tool
def geocoding(
    address: str,            # 地名/地址
    provider: str = "tianditu"  # "tianditu" | "nominatim"
) -> dict:
    """地名/地址 → 坐标。

    使用场景：当用户提到地名需要定位时使用（flyTo前置步骤）。
    示例：geocoding("北京天安门") → {"longitude": 116.3975, "latitude": 39.9087}

    返回：
    {
        "longitude": 116.3975,
        "latitude": 39.9087,
        "formatted_address": "北京市东城区天安门广场",
        "level": "poi",
        "confidence": 0.95
    }
    """
```

---

### 2.11 generate_map_command — 地图指令生成

**核心工具**（始终可见）

```python
@tool
def generate_map_command(
    action: str,             # "flyTo" | "addGeoJsonLayer" | "addHeatmap" | "removeLayer" | "setBasemap"
    data_ref_id: str = None, # 需要可视化的数据引用ID（addGeoJsonLayer/addHeatmap时必填）
    longitude: float = None, # flyTo时的经度
    latitude: float = None,  # flyTo时的纬度
    height: float = None,    # flyTo时的高度
    style: dict = None       # 图层样式（颜色/透明度等）
) -> dict:
    """生成前端地图操控指令，通过SSE推送给前端执行。

    使用场景：需要在地图上展示数据、飞行定位、切换底图时使用。

    示例：
    - "飞到北京" → generate_map_command("flyTo", longitude=116.4, latitude=39.9, height=50000)
    - "在地图上显示" → generate_map_command("addGeoJsonLayer", data_ref_id="ref_001")
    - "显示热力图" → generate_map_command("addHeatmap", data_ref_id="ref_kde")

    返回：
    {
        "command": {"action": "flyTo", "params": {...}},
        "summary": "已发送flyTo指令到前端"
    }
    """
```

---

### 2.12 spatial_statistics — 空间统计

**所属工具组：** `statistics`

**gis-mcp 映射：** `get_bounds` / `get_area` / `get_length`

```python
@tool
def spatial_statistics(
    data_ref_id: str,        # 输入数据引用ID
    metrics: list = None     # 需要计算的指标（不传则计算全部）
) -> dict:
    """计算空间统计指标。

    使用场景：当用户说"统计一下"、"分布特征"、"有多少个"时使用。
    示例：spatial_statistics(data_ref_id="ref_subway")

    可选指标：centroid, bbox, total_area, distribution, nearest_neighbor, property_stats

    返回：
    {
        "feature_count": 326,
        "geometry_type": "Point",
        "centroid": [116.42, 39.91],
        "bbox": [116.12, 39.68, 116.78, 40.18],
        "spatial_extent_km2": 1234.5,
        "nearest_neighbor": {"index": 0.65, "interpretation": "显著聚集分布"},
        "property_stats": {"passengers": {"min": 5000, "max": 350000, "mean": 85000}},
        "summary": "326个Point要素，重心[116.42, 39.91]，显著聚集分布"
    }
    """
```

---

### 2.13 generate_report — 生成分析报告

**核心工具**（始终可见）

```python
@tool
def generate_report(
    data_ref_ids: list = None,  # 需要纳入报告的数据引用ID列表
    format: str = "markdown"    # "markdown" | "html"
) -> dict:
    """基于当前会话的分析结果生成结构化报告。

    使用场景：分析流程结束后，用户需要汇总报告时使用。
    会自动从SessionDataContext获取所有步骤的摘要信息，调用LLM生成报告。

    返回：
    {
        "content": "## 北京地铁站空间分布分析报告\n\n### 1. 概述\n...",
        "format": "markdown",
        "word_count": 800,
        "summary": "生成了800字的分析报告"
    }
    """
```

---

## 3. 工具编排策略

### 3.1 ReAct 逐步编排（非 DAG 预规划）

Agent 采用 **ReAct 模式**，每轮只决定并执行一个工具调用，不预先规划完整 DAG。每步拿到真实结果后再决定下一步：

```
用户: "北京五环内距离地铁站500米的住宅小区"

Step 0: discover_gis_tools("spatial_analysis")
  → 启用 buffer_analysis, spatial_query 等工具
  → Agent 现在可以看到空间分析工具

Step 1: fetch_osm_data("poi", "地铁站", "北京")
  → ref_001, 326个地铁站

Step 2: buffer_analysis(data_ref_id="ref_001", distance=500)
  → GisToolAdapter → gis-mcp: buffer()
  → ref_002, 缓冲区

Step 3: fetch_osm_data("poi", "住宅小区", "北京")
  → ref_003, 5000个住宅

Step 4: spatial_query("within", target_ref="ref_003", mask_ref="ref_002")
  → GisToolAdapter → gis-mcp: sjoin_gpd()
  → ref_004, 1234个匹配

Step 5: generate_map_command("addGeoJsonLayer", data_ref_id="ref_004")
  → SSE 推送前端

回复："北京地铁站500米范围内共有1234个住宅小区。"
```

> **关键**：不让LLM一次规划N步（误差累积），而是每步拿到真实结果后再决定下一步。

### 3.2 数据引用传递（data_ref_id）

所有工具通过 `data_ref_id` 传递数据，**Agent 永远不会看到全量 GeoJSON**：

```
工具输出 → SessionDataContext.register(geojson) → 返回 ref_id + 摘要
下游工具 → GisToolAdapter.resolve_ref(ref_id) → 取出原始数据 → 执行
```

**Agent 上下文中看到的**：
```python
# 精简摘要（~100 tokens），不是 GeoJSON（可能 100K+ tokens）
{
    "data_ref_id": "ref_osm_a3f2",
    "feature_count": 326,
    "geometry_type": "Point",
    "bbox": [116.12, 39.68, 116.78, 40.18],
    "properties": ["name", "line", "operator"],
    "summary": "从OSM获取到326个地铁站"
}
```

**存储级别自动决策：**

| 条件 | 存储级别 | 位置 |
|------|---------|------|
| size < 1MB | Level 1 | 内存字典 |
| 1MB ≤ size < 10MB | Level 1 | 内存（标记可升级） |
| size ≥ 10MB | Level 2 | PostGIS |

### 3.3 错误恢复

工具执行失败时，错误信息返回给 LLM，由 Agent 自主决定重试或降级：

```python
RECOVERY_STRATEGIES = {
    "fetch_osm_data": {
        "retry": 2,
        "fallback": "fetch_tianditu",
        "timeout": 30
    },
    "buffer_analysis": {
        "retry": 1,
        "simplify_on_fail": True,
    },
    # gis-mcp 工具通用策略
    "_gis_mcp_default": {
        "retry": 1,
        "timeout": 60,
    }
}
```

---

## 4. Prompt模板

### 4.1 工具描述注入策略

工具描述**不是静态写死**在 System Prompt 中，而是根据当前启用的工具组动态拼接：

```python
def build_tool_prompt(active_toolsets: list[str]) -> str:
    """根据当前启用的工具组，动态生成工具描述"""
    sections = ["## 可用工具\n"]

    # 核心工具（始终包含）
    for tool in CORE_TOOLS:
        sections.append(format_tool_description(tool))

    # 动态启用的工具组
    for toolset_name in active_toolsets:
        tools = TOOLSETS.get(toolset_name, [])
        sections.append(f"\n### {toolset_name} 组（已启用）\n")
        for tool in tools:
            sections.append(format_tool_description(tool))

    return "\n".join(sections)
```

### 4.2 Few-shot示例（ReAct 逐步模式）

```
## 示例

用户: 北京地铁站分布密度
Step 1 → fetch_osm_data("poi", "地铁站", "北京")
  结果: data_ref_id="ref_001", 326个地铁站
Step 2 → discover_gis_tools("statistics")
  结果: 启用了 spatial_statistics, kernel_density, cluster_analysis
Step 3 → spatial_statistics(data_ref_id="ref_001")
  结果: 重心[116.42, 39.91], 显著聚集分布
Step 4 → kernel_density(data_ref_id="ref_001", radius=1000)
  结果: data_ref_id="ref_002", 最高密度在国贸
Step 5 → generate_map_command("addHeatmap", data_ref_id="ref_002")
  结果: SSE推送热力图到前端
回复: "北京共有326个地铁站，整体呈显著聚集分布，密度最高的区域在国贸..."

用户: 上海浦东新区公园有多少个，总面积多大
Step 1 → fetch_osm_data("poi", "公园", "上海浦东新区")
  结果: data_ref_id="ref_001", 89个公园
Step 2 → discover_gis_tools("measurement")
  结果: 启用了 distance_calc, area_calc, field_statistics
Step 3 → area_calc(data_ref_id="ref_001")
  结果: 总面积12.3km², 平均0.14km²
Step 4 → generate_map_command("addGeoJsonLayer", data_ref_id="ref_001")
  结果: SSE推送到前端
回复: "上海浦东新区共有89个公园，总面积12.3平方公里..."
```

---

## 5. 工具开发规范

### 5.1 工具分类与实现模式

工具分为两类，实现模式不同：

#### A类：gis-mcp 代理工具（空间分析类）

通过 GisToolAdapter 代理到 gis-mcp，开发者只需定义 @tool wrapper：

```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class BufferAnalysisInput(BaseModel):
    """缓冲区分析输入参数"""
    data_ref_id: str = Field(description="输入数据引用ID")
    distance: float = Field(description="缓冲距离")
    unit: str = Field(default="m", description="单位：m 或 km")

@tool(args_schema=BufferAnalysisInput)
async def buffer_analysis(data_ref_id: str, distance: float, unit: str = "m") -> dict:
    """对指定图层创建缓冲区。
    使用场景：当用户说"XX范围内"、"周围XX米"时使用。
    示例：buffer_analysis(data_ref_id="ref_001", distance=500)
    """
    adapter = get_gis_adapter()
    d = distance * 1000 if unit == "km" else distance
    return await adapter.call_gis_tool(
        "buffer",
        ref_params={"geometry": data_ref_id},
        extra_params={"distance": d},
    )
```

#### B类：自建工具（业务逻辑类）

直接实现，但产出空间数据时需注册到 SessionDataContext：

```python
@tool
async def fetch_osm_data(data_type: str, query: str, area: str, limit: int = 5000) -> dict:
    """从OpenStreetMap获取空间数据。..."""
    # 1. 调用 Overpass API 获取数据
    geojson = await overpass_query(data_type, query, area, limit)
    # 2. 注册到 SessionDataContext
    ctx = get_session_context()
    ref_id = ctx.register(geojson, source=f"osm:{data_type}:{query}")
    # 3. 返回摘要 + ref_id
    return {"data_ref_id": ref_id, **ctx.summary(ref_id)}
```

### 5.2 统一返回格式

所有产出空间数据的工具，返回值必须包含 `data_ref_id` + 摘要，**不含全量 GeoJSON**：

```python
{
    "data_ref_id": "ref_buffer_xyz",    # 必须
    "feature_count": 1,                  # 必须
    "geometry_type": "Polygon",          # 必须
    "bbox": [116.1, 39.6, 116.8, 40.2], # 必须
    "properties": ["name", "area"],      # 可选
    "summary": "创建了缓冲区，面积45.6km²" # 必须：人类可读摘要
}
```

非空间数据工具（geocoding/generate_report 等）直接返回结果值即可。

### 5.3 工具描述规范

每个工具的 docstring 必须包含：

1. **一句话功能描述**
2. **使用场景**：用户说什么话时应该调用此工具
3. **Few-shot 示例**：至少1个调用示例
4. **参数 ≤ 5个**，必填参数 ≤ 3个
5. **参数用 enum 约束**：能用 Literal 的绝不用 str
