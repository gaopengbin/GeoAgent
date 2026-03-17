# GeoAgent — AI 驱动的地理空间分析平台

> 用自然语言操控地图，AI 自动完成数据接入 → 空间分析 → 可视化渲染 → 报告生成

## 核心特性

- **自然语言交互**：对话式操控地图，无需编写代码
- **35+ GIS 工具**：缓冲区分析、空间查询、聚类、核密度、填色图、热力图等
- **高德地图集成**：POI 搜索、周边搜索、地理编码、路径规划、天气查询
- **Cesium 3D 地球**：GeoJSON 渲染、3D Tiles、地形服务、影像服务、轨迹动画
- **智能报告**：自动生成 Markdown 分析报告，支持下载
- **流式输出**：SSE 实时推送 AI 思考过程、工具调用、地图指令

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Cesium + Pinia + ECharts |
| 后端 | Python + FastAPI + LangChain/LangGraph |
| GIS | gis-mcp + 高德地图 API + GeoPandas + Shapely + PyProj |
| 数据库 | SQLite（开发）/ PostGIS（生产） |
| Bridge | cesium-mcp-bridge（npm 包） |

## 快速开始

### 环境要求

- Node.js >= 18
- Python >= 3.11
- LLM API Key（DeepSeek / OpenAI / 通义千问）

### 1. 克隆项目

```bash
git clone https://github.com/gaopengbin/GeoAgent.git
cd GeoAgent
```

### 2. 后端启动

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM API Key

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 前端启动

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

### 4. Docker 部署（可选）

```bash
# 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 LLM API Key 和 Cesium Token

docker-compose up --build
# 前端：http://localhost:5173  后端：http://localhost:8000
```

## 项目结构

```
GeoAgent/
├── backend/                    # Python 后端
│   └── app/
│       ├── agent/              # LangGraph Agent（geo_agent.py）
│       ├── api/                # FastAPI 路由（chat.py, data.py）
│       ├── tools/              # 35+ GIS 工具
│       │   ├── core.py         # 核心工具（geocoding, map_command, report）
│       │   ├── spatial.py      # 空间分析（buffer, query, overlay, clip）
│       │   ├── statistics.py   # 统计（聚类, 核密度, 空间统计）
│       │   ├── visualization.py# 可视化（热力图, 填色图, 图表）
│       │   ├── scene3d.py      # 3D 场景（3D Tiles, 地形, 影像）
│       │   ├── trajectory.py   # 轨迹动画
│       │   ├── amap.py         # 高德地图（POI/路径/天气）
│       │   └── ...
│       └── services/           # 会话管理、数据上下文
├── frontend/                   # Vue 3 前端
│   └── src/
│       ├── components/         # MapView, ChatPanel, ResultPanel 等
│       ├── stores/             # Pinia 状态管理
│       └── api/                # SSE 客户端
├── testdata/                   # 测试数据（GeoJSON/CSV）
└── docs/                       # 设计文档（7 篇）
```

## 演示场景

### 场景1：地铁站密度分析
```
用户：帮我分析北京地铁站的空间分布特征
AI：→ 加载数据 → 聚类分析 → 分色渲染 → 热力图 → 统计图表 → 报告
```

### 场景2：POI 空间查询
```
用户：找出地铁站500米范围内的医院
AI：→ 缓冲区分析 → 空间查询 → 结果渲染
```

### 场景3：轨迹动画
```
用户：播放这条 GPS 轨迹的动画
AI：→ 轨迹动画（移动实体 + 尾迹线 + 相机跟随）
```

### 场景4：3D 场景
```
用户：加载这个区域的 3D 建筑模型
AI：→ load_3dtiles → 自动飞行定位
```

## 工具列表

| 分组 | 工具 |
|------|------|
| 核心 | geocoding, fetch_osm_data, load_uploaded_file, generate_map_command, generate_report |
| 空间分析 | buffer_analysis, spatial_query, overlay_analysis, clip_analysis |
| 测量 | distance_calc, area_calc, field_statistics, enrich_geometry_fields |
| 几何 | centroid, convex_hull, simplify_geometry, voronoi |
| 坐标 | transform_crs, get_utm_zone |
| 统计 | spatial_statistics, kernel_density, cluster_analysis |
| 可视化 | generate_heatmap, generate_choropleth, generate_chart |
| 3D 场景 | load_3dtiles, load_terrain, load_imagery_service |
| 轨迹 | play_trajectory |
| 高德地图 | amap_geocoding, amap_poi_search, amap_around_search, amap_route_planning, amap_weather |

## 架构设计

```
用户 → ChatPanel → SSE → FastAPI → LangGraph Agent → Tools
                                        ↓
                              SessionDataContext (边信道)
                                        ↓
                        map_command / chart_option / report
                                        ↓
                   前端 → CesiumBridge.execute() → Cesium 渲染
```

核心设计决策：
- **边信道机制**：GeoJSON 等大数据通过 `push_map_command` 绕过 LLM 上下文，直接推送前端
- **data_ref_id 引用传递**：工具间通过轻量 ID 传递数据，避免 LLM 处理大 JSON
- **cesium-mcp-bridge**：统一的 Cesium 操控层，支持命令分发和类型安全调用

## 开发文档

- [01-项目总览](docs/01-项目总览.md)
- [02-技术架构设计](docs/02-技术架构设计.md)
- [03-API 接口设计](docs/03-API接口设计.md)
- [04-Agent 工具链设计](docs/04-Agent工具链设计.md)
- [05-前端设计文档](docs/05-前端设计文档.md)
- [06-数据库设计](docs/06-数据库设计.md)
- [07-开发计划](docs/07-开发计划.md)

## License

MIT
