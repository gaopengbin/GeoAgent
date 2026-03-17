# Cesium MCP 产品规划

> 市场空白期机会：Cesium 官方正在社区征集 MCP 方案，但尚无可用产品发布。

## 1. 产品矩阵

| 产品 | 定位 | 技术栈 | 发布形式 |
|------|------|--------|---------|
| **GeoAgent** | AI 驱动的地理空间分析平台（主产品） | Python + Vue3 + Cesium | GitHub 开源 |
| **cesium-mcp-dev** | Cesium 开发时 AI 助手 | TypeScript | npm 包 + GitHub |
| **cesium-mcp-runtime** | AI Agent 运行时操控 Cesium | TypeScript/Python + WebSocket | npm 包 + GitHub |

三个项目互相独立又协同，GeoAgent 使用 cesium-mcp-runtime 作为地图控制层。

---

## 2. cesium-mcp-dev（开发时 MCP）

为 IDE 中的 AI 助手（Cursor / Windsurf / Claude Desktop）提供 Cesium 最新 API 文档、代码示例和最佳实践上下文。

### 2.1 Tools（7个）

| Tool | 功能 | 输入 | 输出 |
|------|------|------|------|
| `cesium_api_lookup` | 查询 API 签名和用法 | class + method | API 文档 + 参数 + 示例 |
| `cesium_code_gen` | 生成代码片段 | 自然语言描述 | 可运行代码 |
| `cesium_entity_builder` | 生成 Entity 配置 | 实体类型 + 样式参数 | Entity 创建代码 |
| `cesium_imagery_config` | 底图配置助手 | 提供商 + 类型 | ImageryProvider 配置 |
| `cesium_3dtiles_config` | 3DTiles 加载配置 | URL + 样式条件 | Cesium3DTileset 配置 |
| `cesium_czml_gen` | CZML 文档生成 | 实体列表 + 时间范围 | 完整 CZML JSON |
| `cesium_version_migrate` | 版本迁移建议 | 源版本 → 目标版本 | Breaking changes + 迁移代码 |

### 2.2 Resources

| Resource URI | 内容 |
|-------------|------|
| `cesium://api/{class}` | 指定类的完整 API 文档 |
| `cesium://examples/{category}` | 分类代码示例 |
| `cesium://changelog` | 最新版本变更 |

### 2.3 项目结构

```
cesium-mcp-dev/
├── src/
│   ├── index.ts
│   ├── tools/
│   │   ├── api-lookup.ts
│   │   ├── code-gen.ts
│   │   ├── entity-builder.ts
│   │   ├── imagery-config.ts
│   │   ├── tiles3d-config.ts
│   │   ├── czml-gen.ts
│   │   └── migration.ts
│   └── resources/
│       ├── api/
│       ├── examples/
│       └── changelog/
├── scripts/
│   └── scrape-docs.ts
├── package.json
├── tsconfig.json
└── README.md
```

---

## 3. cesium-mcp-runtime（运行时 MCP）

让后端 AI Agent 通过标准 MCP 协议直接操控浏览器中运行的 Cesium 实例。

### 3.1 架构

```
┌──────────────┐      MCP协议        ┌──────────────────┐     WebSocket      ┌─────────────┐
│  AI Agent    │ ←──────────────────→ │ cesium-mcp       │ ←────────────────→ │  Browser    │
│ (LangGraph)  │   tool_call/result  │ -runtime         │   command/event   │  (Cesium)   │
└──────────────┘                      └──────────────────┘                    └─────────────┘
```

### 3.2 Tools（~25个）

**视图控制（View）：**

| Tool | 功能 | 关键参数 |
|------|------|---------|
| `flyTo` | 飞行到指定位置 | lon, lat, height, heading, pitch, duration |
| `flyToEntity` | 飞行到实体 | entityId |
| `setView` | 设置视角 | lon, lat, height, heading, pitch, roll |
| `zoomToExtent` | 缩放到范围 | bbox |
| `getView` | 获取当前视角 | — |

**图层管理（Layer）：**

| Tool | 功能 |
|------|------|
| `addGeoJsonLayer` | 添加 GeoJSON 图层 |
| `addImageryLayer` | 添加影像图层 (TMS/WMTS/WMS) |
| `add3DTileset` | 添加 3DTiles |
| `addTerrainProvider` | 设置地形服务 |
| `removeLayer` | 移除图层 |
| `setLayerVisibility` | 图层显隐 |
| `setLayerStyle` | 设置样式 |
| `listLayers` | 列出所有图层 |

**实体操作（Entity）：**

| Tool | 功能 |
|------|------|
| `addMarker` | 添加标注点 |
| `addPolyline` | 添加折线 |
| `addPolygon` | 添加多边形 |
| `addLabel` | 添加文字标注 |
| `addHeatmap` | 添加热力图 |
| `addClusterLayer` | 添加聚类图层 |
| `removeEntity` | 移除实体 |

**交互（Interaction）：**

| Tool | 功能 |
|------|------|
| `screenshot` | 截图（返回 base64） |
| `highlight` | 高亮实体 |
| `measure` | 测量距离/面积 |
| `getEntityInfo` | 获取实体属性 |

**动画（Animation）：**

| Tool | 功能 |
|------|------|
| `playTrack` | 轨迹动画回放 |
| `setTimeline` | 设置时间轴 |
| `setClockSpeed` | 动画速度 |

### 3.3 前端 Bridge SDK

```typescript
// cesium-mcp-bridge — 前端引入的轻量 SDK
import { CesiumMCPBridge } from 'cesium-mcp-bridge'

const bridge = new CesiumMCPBridge({
  viewer: cesiumViewer,
  serverUrl: 'ws://localhost:8001',
  sessionId: 'xxx',
})

bridge.connect()
// 自动注册命令处理器，后端 MCP 发什么就执行什么
// 执行结果自动回传
```

### 3.4 关键技术方案

| 挑战 | 方案 |
|------|------|
| Cesium 在浏览器，MCP Server 在后端 | WebSocket 桥接 |
| 大数据传输 | HTTP 上传 → data_ref_id 引用（不走 WebSocket） |
| 异步操作（flyTo 动画） | 等待完成回调后才返回 tool result |
| 多浏览器实例 | session_id 路由 |

---

## 4. 开发时间线

| 阶段 | GeoAgent | cesium-mcp-dev | cesium-mcp-runtime |
|------|----------|---------------|-------------------|
| **Phase 1 (MVP)** | SSE + CommandExecutor | — | — |
| **Phase 2** | 空间分析工具 | 搭建骨架 + 核心 tools | 搭建骨架 + Bridge SDK |
| **Phase 3** | 迁移到 cesium-mcp-runtime | 完善 + npm 发布 | 完善 + npm 发布 |
| **发布** | GitHub 开源 | GitHub + npm | GitHub + npm |

## 5. 市场策略

- Cesium 社区论坛发帖回应官方征集（附项目链接）
- GitHub 仓库建立后第一时间 Cesium Discord 推广
- 配套技术文章："Building the First Cesium MCP Server"
- GeoAgent 作为 cesium-mcp-runtime 的 showcase 演示项目
