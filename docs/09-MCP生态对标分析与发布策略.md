# Cesium-MCP 生态对标分析与发布策略

> 2026.03 分析报告 — 基于 MCP 协议规范(2025-06-18)、主流 MCP Server 实践、GIS 领域竞品调研

---

## 一、市场态势

### 1.1 Cesium MCP 竞品现状

| 领域 | 已有 MCP 实现 | 状态 |
|------|-------------|------|
| GDAL（栅格/矢量处理） | GDAL MCP (@Wayfinder-Foundry) | 活跃，有 reasoning guidance |
| QGIS（桌面 GIS） | QGIS MCP (@jjsantos01) | 活跃，支持图层加载/代码执行 |
| STAC（时空资产目录） | STAC MCP (@Wayfinder-Foundry) | 活跃 |
| OlaMaps（地图服务） | OlaMaps MCP（官方） | 官方实现 |
| **Cesium（3D 地球）** | **仅本项目，无竞品** | **市场空白** |
| MapboxGL | 无 | — |
| Leaflet | 无 | — |
| OpenLayers | 无 | — |
| deck.gl | 无 | — |

**结论**：WebGL 3D 地图渲染库领域 MCP 实现接近空白。Cesium 官方正在社区征集 MCP 方案但尚无产品，本项目具有显著先发优势。

### 1.2 ArcGIS AI 策略

ArcGIS 5.0 推出了 AI 组件（`<arcgis-assistant>`），但走的是**平台闭环路线**（Copilot for ArcGIS），未采用 MCP 开放协议。开源 GIS 工具链正在快速拥抱 MCP，Esri 的闭环策略反而为开源 MCP 方案留出了生态位。

---

## 二、当前产品评估

### 2.1 三包成熟度

| 包 | 评分 | 发布就绪 | 核心能力 |
|----|------|---------|---------|
| cesium-mcp-bridge | 8.7/10 | 90% | 双模式调用 + 16+ 命令 + 完善类型系统 |
| cesium-mcp-dev | 7.0/10 | 60% | 3 个工具 + 31 条资源数据 |
| cesium-mcp-runtime | 5.7/10 | 40% | 8 个 MCP 工具 + stdio/WS/HTTP 三协议 |

### 2.2 Bridge 详细能力

已实现 19+ 命令：

| 类别 | 命令 | 状态 |
|------|------|------|
| 视图 | flyTo, setView, getView, zoomToExtent | 完整 |
| 图层 | addGeoJsonLayer (含聚合/choropleth/category), addHeatmap, setBasemap, removeLayer, setLayerVisibility, updateLayerStyle, listLayers | 完整 |
| 3D | load3dTiles, loadTerrain, loadImageryService | 完整 |
| 实体 | addLabels, addMarker | 完整 |
| 轨迹 | playTrajectory (匀速插值+尾迹) | 完整 |
| 交互 | screenshot, highlight | highlight 有 bug |

已知 Bug：
- `highlight` 函数中 `layer.dataSource` 永远 `undefined`，高亮无法工作
- `addMarker` 创建的 Entity 未注册到图层系统
- `loadTerrain` 异步无错误处理

### 2.3 Runtime 能力覆盖

| Bridge 命令 | Runtime MCP 工具 | 状态 |
|------------|-----------------|------|
| flyTo | flyTo | 已映射 |
| setView | setView | 已映射 |
| getView | getView | 已映射 |
| zoomToExtent | zoomToExtent | 已映射 |
| addGeoJsonLayer | addGeoJsonLayer | 已映射 |
| removeLayer | removeLayer | 已映射 |
| screenshot | screenshot | 已映射 |
| highlight | highlight | 已映射（但底层有bug） |
| setBasemap | — | **缺失** |
| addHeatmap | — | **缺失** |
| load3dTiles | — | **缺失** |
| loadTerrain | — | **缺失** |
| loadImageryService | — | **缺失** |
| addLabels | — | **缺失** |
| addMarker | — | **缺失** |
| playTrajectory | — | **缺失** |
| setLayerVisibility | — | **缺失** |
| updateLayerStyle | — | **缺失** |
| listLayers | — | **缺失** |

**工具覆盖率：8/19+ = 42%**，AI Agent 无法使用 Bridge 58% 的能力。

---

## 三、与主流 MCP Server 差距分析

### 3.1 协议原语覆盖度

MCP 规范定义三种核心原语：

| 原语 | 用途 | cesium-mcp-runtime | cesium-mcp-dev | 主流做法 |
|------|------|-------------------|----------------|---------|
| **Tools** | AI 可调用的操作 | 有（8个） | 有（3个） | GitHub: 30+, Playwright: 20+ |
| **Resources** | 暴露上下文数据 | **缺失** | 有 | Filesystem: 目录资源, Memory: 知识图谱 |
| **Prompts** | 操作模板 | **缺失** | **缺失** | Everything Server: 完整三原语 |

**Resource 缺失的影响**：Cesium 场景状态（相机位置、已加载图层、Entity 集合）天然适合作为 Resource 暴露。没有 Resource，LLM 是"盲操作"——不知道地图上当前有什么就去添加/删除图层。

**Prompt 缺失的影响**：常见 GIS 操作模板（如"创建点密度热力图"、"设置飞行漫游路线"）可显著降低 LLM 构造工具调用的难度。

### 3.2 工具设计质量

对比主流 MCP Server 的 zod schema 最佳实践：

```typescript
// 主流做法 (GitHub MCP)
const CreateIssueSchema = z.object({
  owner: z.string().describe("Repository owner (username or org)"),
  repo: z.string().describe("Repository name"),
  title: z.string().min(1).describe("Issue title"),
  body: z.string().optional().describe("Issue body in Markdown"),
  labels: z.array(z.string()).optional().describe("Labels to apply"),
});

// 当前做法 (cesium-mcp-runtime)
server.tool("flyTo", { params: z.record(z.unknown()) }, ...);
// 缺少字段级 describe，参数校验过于宽松
```

差距要点：
- 每个字段需要 `.describe()` 说明（LLM 依赖此理解参数含义）
- 使用 `.min()/.max()` 约束防止无效输入
- 枚举类型需用 `z.enum()` 限定合法值
- 可选字段明确标记 `.optional()`

### 3.3 npm 发布规范

| 规范项 | 主流做法 | 当前状态 |
|--------|---------|---------|
| `npx` 一键启动 | `npx @org/server-name` | runtime 缺 bin，无法执行 |
| `main/exports` | 指向编译后 JS | runtime 指向 TS 源码 |
| `files` 白名单 | 只发布必要文件 | runtime 未配置 |
| `engines` | 声明 Node 最低版本 | 未声明 |
| README | 安装/配置/工具列表/示例 | bridge 充实，runtime 尚可 |
| LICENSE | MIT/Apache-2.0 | bridge 缺失 |

### 3.4 架构对标

当前架构：
```
[LLM Client] --stdio--> [cesium-mcp-runtime] --WebSocket--> [Browser/Cesium]
```

与 Playwright MCP (Microsoft) 完全同构：
```
[LLM Client] --stdio--> [Playwright MCP Server] --CDP--> [Browser]
```

**架构方向正确，不是差距点。** stdio + WebSocket 桥接到浏览器是唯一合理的选择。

### 3.5 高级协议特性

| 特性 | MCP 规范状态 | 当前支持 | 优先级 |
|------|-------------|---------|--------|
| Capability Negotiation | 必需 | SDK 自动处理（合规） | — |
| Tool Error (isError: true) | 必需 | 需确认 | 中 |
| Resource Links | 推荐 | 未实现 | 高 |
| outputSchema / structuredContent | 可选 | 未实现 | 低 |
| Streamable HTTP Transport | 可选 | 未实现 | 低（远程部署时需要） |
| Tool Result Streaming | 可选 | 未实现 | 低 |

---

## 四、差距优先级排序

| 优先级 | 差距 | 严重度 | 修复工作量 | 影响面 |
|--------|------|--------|-----------|--------|
| **P0** | Runtime 只暴露 8/19+ 工具 | 致命 | 中（1-2天） | LLM 无法使用 58% 能力 |
| **P1** | 未实现 Resource 原语 | 严重 | 小（半天） | LLM 无场景上下文 |
| **P1** | 构建配置不完整 | 严重 | 小（2小时） | 无法 npx 启动，阻碍采用 |
| **P2** | Bridge highlight bug | 中等 | 小 | 功能不可用 |
| **P2** | zod schema 缺少 describe | 中等 | 小 | LLM 工具调用准确率 |
| **P3** | 未实现 Prompt 原语 | 低 | 小 | 用户体验优化 |
| **P3** | dev API 数据覆盖率低 | 低 | 持续 | 长尾价值 |
| **P4** | 错误处理双层模型 | 低 | 小 | 错误恢复能力 |
| **P4** | Streamable HTTP / outputSchema | 低 | 中 | 远期需要 |

---

## 五、发布策略

### 5.1 路线图

```
Phase 1: 卡位发布（最高优先级）
├── cesium-mcp-bridge 修 bug + 加 LICENSE → npm publish v0.1.0
├── cesium-mcp-runtime 补齐 19+ 工具 + Resource 原语 + 修构建 → npm publish v0.1.0
└── cesium-mcp-dev 修构建配置 → npm publish v0.1.0

Phase 2: 社区推广
├── Cesium 社区论坛发帖（回应官方 MCP 征集）
├── GitHub README 完善（英文，含 GIF 演示）
├── 技术文章: "Building the First Cesium MCP Server"
└── MCP 官方注册表提交

Phase 3: 深化
├── Prompt 原语（常见 GIS 操作模板）
├── dev 持续补充 API 文档数据
├── GeoAgent 作为 showcase 打磨
└── Streamable HTTP 支持
```

### 5.2 Phase 1 执行清单

**cesium-mcp-bridge**（工作量: 半天）：
- [ ] 修复 `highlight` -- 从 `layerManager._cesiumRefs` 获取 dataSource
- [ ] 修复 `addMarker` -- 注册到图层系统
- [ ] `loadTerrain` 添加错误处理
- [ ] 添加 LICENSE (MIT)
- [ ] 确认 package.json exports/files 配置
- [ ] npm publish

**cesium-mcp-runtime**（工作量: 2天）：
- [ ] 新增 11+ MCP 工具（setBasemap, addHeatmap, load3dTiles, loadTerrain, loadImageryService, addLabels, addMarker, playTrajectory, setLayerVisibility, updateLayerStyle, listLayers）
- [ ] 每个工具的 zod schema 添加完整 `.describe()`
- [ ] 添加 Resource 原语: `cesium://scene/camera`（当前相机状态）、`cesium://scene/layers`（已加载图层列表）
- [ ] 修复构建: 添加 `bin` 字段 + tsup 构建 + 测试 `npx` 启动
- [ ] 提取 demo-server.ts 与 index.ts 共享代码
- [ ] 添加 LICENSE
- [ ] npm publish

**cesium-mcp-dev**（工作量: 半天）：
- [ ] 修复构建: bin 指向编译后 JS
- [ ] 添加 LICENSE
- [ ] 确认 npx 启动可用
- [ ] npm publish

### 5.3 不应该做的事

- **不急着上 PostGIS/Redis/RAG** -- SQLite 够用，复杂化基础设施是当前阶段的陷阱
- **不急着补 cesium-mcp-dev 的 API 文档到 500+** -- 12 条够 MVP
- **不在 GeoAgent 上投入过多 UI 打磨** -- 先把 MCP 层做到可被其他项目集成
- **不追求 Streamable HTTP** -- stdio 足以覆盖 IDE MCP 客户端场景

---

## 六、核心论点

本项目的价值不在于"又一个 MCP Server"，而在于**填补了 WebGL 3D 地图渲染库的 MCP 空白**。

这个空白今天存在，但不会永远存在。Cesium 官方已在征集方案，一旦官方或其他团队出品 MCP 实现，后来者的生存空间会急剧缩小。

**先发 = 先定义标准。** 第一个发布到 npm + MCP 注册表的 Cesium MCP Server，会成为社区默认选择和参考实现。

---

## 七、接入教程

### 7.1 整体架构

```
                          ┌─────────────────────────┐
                          │   AI Agent / LLM Host    │
                          │  (Claude, GPT, etc.)     │
                          └──────────┬──────────────┘
                                     │ stdio (MCP Protocol)
                          ┌──────────▼──────────────┐
                          │  cesium-mcp-runtime      │
                          │  MCP Server + WS Hub     │
                          │  (Node.js, port 9100)    │
                          └──────────┬──────────────┘
                     HTTP POST       │       WebSocket (JSON-RPC 2.0)
                     /api/command    │       ws://localhost:9100?session=xxx
               ┌─────────┘          │          └──────────┐
               │                    │                     │
    ┌──────────▼─────┐              │          ┌──────────▼──────────┐
    │  后端 (FastAPI) │              │          │  前端 (Browser)      │
    │  也可通过 HTTP   │              │          │  cesium-mcp-bridge   │
    │  推送地图命令    │              │          │  + Cesium.Viewer     │
    └────────────────┘              │          └─────────────────────┘
                                    │
              ┌─────────────────────┘  (独立，IDE 专用)
              │
    ┌─────────▼──────────┐
    │  cesium-mcp-dev    │
    │  IDE MCP Server    │
    │  (stdio, 开发辅助)  │
    └────────────────────┘
```

### 7.2 cesium-mcp-bridge (前端 SDK)

**安装**：

```bash
npm install cesium-mcp-bridge
# cesium 为 peerDependency，需自行安装 cesium >= 1.100.0
```

**初始化**：

```typescript
import { CesiumBridge } from 'cesium-mcp-bridge'
import type { LayerInfo, BridgeCommand } from 'cesium-mcp-bridge'

// 1. 创建 Cesium Viewer
const viewer = new Cesium.Viewer('cesiumContainer')

// 2. 初始化 Bridge
const bridge = new CesiumBridge(viewer)

// 3. (可选) 绑定响应式图层列表
const layers = ref<LayerInfo[]>([])
bridge.layerManager.setLayersRef(layers.value)
```

**使用方式**：

```typescript
// 方式 1: 类型安全的直接调用
await bridge.flyTo({ longitude: 116.39, latitude: 39.91, height: 5000, duration: 2 })
await bridge.addGeoJsonLayer({ id: 'buildings', data: geojsonObject })
await bridge.screenshot()

// 方式 2: 命令分发（适用于接收 MCP/SSE 消息后动态执行）
await bridge.execute({
  action: 'addHeatmap',
  params: { id: 'heat1', data: geojson, radius: 30, gradient: { 0.4: 'blue', 0.8: 'yellow', 1.0: 'red' } }
})
```

**支持的全部命令**：

| 类别 | 命令 | 说明 |
|------|------|------|
| 视图 | `flyTo` | 飞行到指定经纬度/高度 |
| 视图 | `setView` | 瞬时设置相机位置 |
| 视图 | `getView` | 获取当前相机状态 |
| 视图 | `zoomToExtent` | 缩放到矩形范围 |
| 图层 | `addGeoJsonLayer` | 加载 GeoJSON（支持聚合/分级/分类渲染） |
| 图层 | `addHeatmap` | WebGL 热力图 |
| 图层 | `removeLayer` | 移除图层 |
| 图层 | `setLayerVisibility` | 切换图层显隐 |
| 图层 | `updateLayerStyle` | 动态更新样式 |
| 图层 | `listLayers` | 列出已加载图层 |
| 底图 | `setBasemap` | 切换底图（天地图/ArcGIS/OpenStreetMap 等） |
| 3D | `load3dTiles` | 加载 3D Tiles 模型 |
| 3D | `loadTerrain` | 加载地形服务 |
| 3D | `loadImageryService` | 加载影像服务 |
| 实体 | `addLabels` | 批量添加标注 |
| 实体 | `addMarker` | 添加标记点 |
| 轨迹 | `playTrajectory` | 播放带尾迹的运动轨迹 |
| 交互 | `screenshot` | 截取地图画面 |
| 交互 | `highlight` | 高亮指定要素 |

### 7.3 cesium-mcp-runtime (MCP Server + WebSocket Hub)

**启动**：

```bash
cd packages/cesium-mcp-runtime

# 完整模式: stdio MCP + HTTP + WebSocket（AI Agent 接入用）
npx tsx src/index.ts

# 开发测试模式: 仅 HTTP + WebSocket（无 MCP stdio，人工测试用）
npx tsx src/demo-server.ts
```

**环境变量**：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CESIUM_WS_PORT` | `9100` | HTTP + WebSocket 监听端口 |

**前端连接 WebSocket**：

```typescript
function connectRuntime(wsUrl: string, sessionId: string = 'default') {
  const ws = new WebSocket(`${wsUrl}?session=${sessionId}`)

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    if (msg.method) {
      // 收到来自 AI Agent 的地图命令，交给 Bridge 执行
      bridge.execute({ action: msg.method, params: msg.params ?? {} })
      // 回复确认
      if (msg.id) {
        ws.send(JSON.stringify({ id: msg.id, result: { success: true } }))
      }
    }
  }
}

// 连接
connectRuntime('ws://localhost:9100')
```

**后端推送命令（HTTP API）**：

```python
import httpx

# 通过 HTTP 推送地图命令（不经过 MCP，直接推到浏览器）
async def push_map_command(action: str, params: dict):
    async with httpx.AsyncClient() as client:
        await client.post("http://localhost:9100/api/command", json={
            "sessionId": "default",
            "command": { "action": action, "params": params }
        })

# 示例
await push_map_command("flyTo", {"longitude": 116.39, "latitude": 39.91, "height": 5000})
```

**AI Agent MCP 配置**（Claude Desktop / VS Code / Cursor 等）：

```json
{
  "mcpServers": {
    "cesium-runtime": {
      "command": "npx",
      "args": ["tsx", "/abs/path/to/cesium-mcp-runtime/src/index.ts"],
      "env": {
        "CESIUM_WS_PORT": "9100"
      }
    }
  }
}
```

配置后 AI Agent 可直接调用 MCP 工具操控浏览器中的 Cesium 地图。

### 7.4 cesium-mcp-dev (IDE 开发辅助)

**用途**：纯开发辅助，提供 Cesium API 文档查询、代码生成、Entity 构建模板。与 runtime 无关，不操作真实地图。

**IDE 配置**：

```json
{
  "mcpServers": {
    "cesium-dev": {
      "command": "npx",
      "args": ["tsx", "/abs/path/to/cesium-mcp-dev/src/index.ts"]
    }
  }
}
```

**可用工具**：

| 工具 | 参数 | 说明 |
|------|------|------|
| `cesium_api_lookup` | `query`, `category?` | 查询 Cesium API (Viewer, Camera, Entity 等 12 个核心类) |
| `cesium_code_gen` | `description`, `language?` | 自然语言描述 -> Cesium 代码片段 |
| `cesium_entity_builder` | `type`, `position`, `color?` 等 | 生成 Entity 创建代码 (point/billboard/label/polyline/polygon/model/ellipsoid/wall) |

**使用示例**：

在 IDE 中对 AI 说：
- "查一下 Cesium Camera 的 API" -> 调用 `cesium_api_lookup`
- "写一段加载 3D Tiles 的代码" -> 调用 `cesium_code_gen`
- "帮我创建一个红色的多边形 Entity" -> 调用 `cesium_entity_builder`

### 7.5 完整接入示例 (GeoAgent 项目)

以下是 GeoAgent 项目中三个包协同工作的完整配置链路：

**1. 启动 Runtime**：
```bash
cd packages/cesium-mcp-runtime
CESIUM_WS_PORT=9100 npx tsx src/index.ts
```

**2. 后端配置**（`backend/.env`）：
```env
CESIUM_RUNTIME_URL=http://localhost:9100
```

后端 FastAPI 启动后，在 `/api/config` 接口中将 URL 协议从 `http://` 转为 `ws://` 返回给前端：
```python
# main.py
cesium_runtime_ws_url = settings.CESIUM_RUNTIME_URL.replace("http://", "ws://")
```

**3. 前端自动连接**：
```
configStore.loadConfig()          // 获取 cesiumRuntimeWsUrl = "ws://localhost:9100"
      ↓
MapView.vue onMounted()           // 创建 Cesium.Viewer
      ↓
mapStore.setViewer(viewer)        // 初始化 CesiumBridge
      ↓
mapStore.connectRuntime(wsUrl)    // WebSocket 连接 Runtime
```

**4. AI Agent 操控地图**：

AI Agent 通过 MCP stdio 调用 Runtime 的工具 -> Runtime 通过 WebSocket 推送到浏览器 -> Bridge 执行命令 -> Cesium 地图变化。

当 WebSocket 不可用时，后端也可通过 SSE 推送 `map_command` 事件作为降级方案。

### 7.6 极简样例项目

项目提供了一个开箱即用的最小示例，位于 `examples/minimal/`：

```
examples/minimal/
├── index.html      # 单文件完整示例（~150 行，Cesium + Bridge + WebSocket）
└── README.md
```

**包含内容**：
- Cesium Viewer 初始化（CDN 引入，无需构建）
- cesium-mcp-bridge 初始化（CDN 引入，含降级模式）
- WebSocket 连接 Runtime（自动重连）
- 5 个手动测试按钮（飞到北京/上海、添加标注、截图、获取视角）
- 实时命令日志面板

**30 秒快速体验**：

```bash
# 终端 1: 启动 Runtime
cd packages/cesium-mcp-runtime && npx tsx src/index.ts

# 终端 2: 启动页面
npx serve examples/minimal -l 3000
# 浏览器打开 http://localhost:3000
```

页面连接 Runtime 后，在 Claude Desktop / VS Code 中配置 MCP Server 即可用自然语言操控地图：

```
你: "把地图飞到上海外滩"
AI: 调用 flyTo(longitude=121.49, latitude=31.24, height=3000)
浏览器: Cesium 相机自动飞行到上海外滩
```

数据流路径：
```
AI "飞到上海" → MCP flyTo → Runtime → WebSocket → Bridge.execute() → Cesium 飞行动画
```

---

## 八、热力图渲染完善分析

### 8.1 现状差异

| 维度 | Bridge 真实实现 | Demo 降级版 |
|------|----------------|------------|
| **渲染技术** | Canvas 2D 离屏渲染 512x512，`createRadialGradient` 径向渐变逐点叠加 | Cesium Ellipse Entity 逐点创建 |
| **贴图方式** | 整张 canvas 作为 `ImageMaterialProperty` 贴到 Rectangle Entity | 无贴图，每点独立椭圆几何体 |
| **视觉效果** | 连续色域、热力扩散感 | 离散圆圈散点，本质是"气泡图" |
| **颜色模型** | 硬编码 红->橙->黄 三段径向渐变 | 简单 R/G 线性插值 |
| **gradient 参数** | 类型定义了但代码未使用 | 调用侧传了但被忽略 |

**核心函数**：`generateHeatmapCanvas()`（layer.ts L656-L695）
- 512x512 固定分辨率
- 径向渐变 + alpha 叠加 = 基础热力效果
- 无 KDE（核密度估计）、无高斯模糊后处理
- gradient 参数完全被忽略（颜色硬编码）

### 8.2 完善路径

**路径 1：补全现有 Canvas 实现**（约 50 行改动）
- 读取 `gradient` 参数，用 `ImageData` 像素级重映射颜色
- 加一遍 box blur / StackBlur 让热力融合更自然
- 分辨率动态计算（根据数据范围和点密度自适应）
- 投入小，效果明显改善

**路径 2：引入 heatmap.js**（推荐，约 30 行 + 1 依赖）
- 专业热力图库（~10KB gzipped），内置核密度估计
- 原生支持 gradient / radius / blur / opacity / min / max
- 直接输出 Canvas，无缝替换 `generateHeatmapCanvas`
- Cesium 社区最常用方案
- `npm install heatmap.js` 即可，bridge 已有 Canvas -> Entity 通路

**路径 3：WebGL CustomPrimitive**（大数据量场景）
- Fragment Shader 实现 GPU 端 KDE
- 适合 10K+ 数据点
- 开发成本高，当前规模不需要

**优先级**：路径 2 > 路径 1 > 路径 3

### 8.3 不受 MCP 协议限制

Bridge 运行在浏览器端，完全可访问 Canvas API / WebGL / 任何第三方库。MCP 协议仅是命令传输通道，热力图渲染质量完全由 bridge 实现决定。Runtime 不需要任何改动。

---

## 第九章 WebSocket Session 隔离方案

### 9.1 问题背景

Runtime 的 WebSocket 架构使用 `Map<string, WebSocket>` 管理浏览器连接，key 为 sessionId。但 MCP 工具中的 `sendToBrowser()` 始终调用 `getDefaultBrowser()` 获取 Map 中的第一个连接，导致：

- 多个浏览器页面（如 GeoAgent + example）同时连接时，AI 的命令可能发送到错误的目标
- 实际案例：用户在 GeoAgent 中发送的指令，在 example 页面上执行

### 9.2 现有路由机制对比

| 函数 | 路由方式 | 调用方 | 是否 session 感知 |
|------|---------|--------|------------------|
| `sendToBrowser()` | `getDefaultBrowser()` 盲取第一个 | MCP 工具 | 否 |
| `pushToBrowser(sessionId, cmd)` | 按 sessionId 查找，fallback 到默认 | HTTP API | 部分 |

### 9.3 方案评估

**方案 A：MCP 工具参数加 sessionId**

在每个 MCP tool 的参数中增加可选的 `sessionId` 字段，`sendToBrowser()` 据此路由。

- 优点：灵活，支持多目标
- 缺点：AI 不知道该填什么值。AI Agent 没有"当前正在操作哪个浏览器"的概念，除非显式告知

**方案 B：环境变量绑定默认 session（推荐）**

启动时通过 `DEFAULT_SESSION_ID` 环境变量绑定目标 session，`getDefaultBrowser()` 优先返回该 session 的连接。

MCP 配置示例：
```json
{
  "mcpServers": {
    "cesium-runtime": {
      "command": "npx",
      "args": ["tsx", "src/index.ts"],
      "env": { "DEFAULT_SESSION_ID": "geoagent" }
    }
  }
}
```

前端连接时使用匹配的 sessionId：
```typescript
connectRuntime('ws://localhost:9100', 'geoagent')
```

- 优点：AI 无需感知 session 概念，运维层面一次配置即可；约 10 行改动
- 缺点：一个 runtime 实例绑定一个默认目标

**方案 C：多实例隔离**

不同环境启动不同 runtime 实例，监听不同端口。

```
GeoAgent  -> runtime :9100
Example   -> runtime :9101
```

- 优点：最简单，零代码改动
- 缺点：运维成本高，端口管理复杂

### 9.4 多层隔离分析

| 隔离层面 | 当前状态 | 方案 B 能否解决 |
|---------|---------|----------------|
| 多浏览器连同一 runtime | 后者覆盖前者 | 能 -- 不同 sessionId 共存于 Map |
| MCP 工具路由到正确浏览器 | 盲取第一个 | 能 -- 环境变量指定默认目标 |
| 多 AI Agent 共用一个 runtime | 不可能 -- MCP stdio 是 1:1 | 不相关 -- 每个 AI 各启一个 runtime 进程 |

### 9.5 推荐实施

采用 **方案 B**（环境变量），改动范围：

1. `getDefaultBrowser()`：读取 `process.env.DEFAULT_SESSION_ID`，优先返回匹配的连接
2. `sendToBrowser()`：支持可选的 `sessionId` 参数覆盖默认值
3. 前端 `connectRuntime()`：接受 sessionId 参数，连接时携带 `?session=<sessionId>`

**优先级**：P1（已出现实际问题）
