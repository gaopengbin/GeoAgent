# API接口设计

## 1. 接口总览

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | /api/chat | 对话（SSE流式） | 可选 |
| POST | /api/upload | 上传空间数据文件 | 可选 |
| GET | /api/sessions | 获取会话列表 | 可选 |
| GET | /api/sessions/{id} | 获取会话详情 | 可选 |
| DELETE | /api/sessions/{id} | 删除会话 | 可选 |
| GET | /api/layers/{session_id} | 获取会话图层列表 | 可选 |
| POST | /api/analysis/export | 导出分析报告 | 可选 |
| GET | /api/config | 获取前端配置 | 无 |
| GET | /api/health | 健康检查 | 无 |

---

## 2. 对话接口

### POST /api/chat

**核心接口，SSE流式返回。**

#### 请求

```json
{
  "session_id": "uuid-string",    // 可选。不传则创建新会话
  "message": "分析北京地铁站分布密度",
  "attachments": [                // 可选。引用已上传的文件
    {
      "file_id": "uploaded-uuid",
      "filename": "stations.geojson"
    }
  ],
  "options": {                    // 可选。控制参数
    "model": "deepseek-chat",    // LLM模型
    "temperature": 0.3,
    "max_tools": 10,             // 最多调用几个工具
    "enable_report": true        // 是否生成报告
  }
}
```

#### SSE响应事件

事件类型：`session` | `text` | `thinking` | `tool_call` | `tool_result` | `map_command` | `chart` | `report` | `done` | `error`

```
event: session
data: {"session_id": "new-uuid"}

event: text
data: {"content": "好的，我来帮你分析北京地铁站分布密度。", "done": false}

event: thinking
data: {"content": "正在规划分析步骤..."}

event: tool_call
data: {"step": 1, "tool_name": "fetch_osm_data", "tool_args": {"data_type": "poi", "query": "地铁站", "area": "北京"}, "description": "正在从OSM获取北京地铁站数据..."}

event: tool_result
data: {"step": 1, "tool_name": "fetch_osm_data", "success": true, "summary": "获取到326个地铁站", "data_ref_id": "ref_001", "preview": {"feature_count": 326, "geometry_type": "Point", "bbox": [116.12, 39.68, 116.78, 40.18]}, "duration_ms": 1200}

event: tool_call
data: {"step": 2, "tool_name": "kernel_density", "tool_args": {"data_ref_id": "ref_001"}, "description": "正在计算核密度估计..."}

event: tool_result
data: {"step": 2, "tool_name": "kernel_density", "success": true, "summary": "生成密度热力图数据", "data_ref_id": "ref_002", "duration_ms": 800}

event: map_command
data: {"action": "flyTo", "params": {"longitude": 116.4, "latitude": 39.9, "height": 80000}}

event: map_command
data: {"action": "addHeatmap", "params": {"id": "subway_density", "name": "地铁站密度热力图", "points": [...]}}

event: text
data: {"content": "分析完成。北京共有**326个地铁站**...", "done": false}

event: chart
data: {"chartType": "bar", "title": "各区地铁站数量", "labels": ["朝阳","海淀",...], "values": [58,45,...]}

event: report
data: {"content": "## 北京地铁站空间分布分析报告\n\n### 1. 数据概况\n...", "format": "markdown"}

event: done
data: {"session_id": "uuid", "tool_calls": 4, "tokens_used": 1523}
```

#### 错误响应

```json
{
  "error": {
    "code": "RATE_LIMIT",
    "message": "请求过于频繁，请稍后再试",
    "retry_after": 30
  }
}
```

---

## 3. 文件上传接口

### POST /api/upload

支持格式：`.geojson`, `.json`, `.csv`, `.xlsx`/`.xls`, `.kml`, `.kmz`, `.gpx`, `.shp`(zip打包)

**智能识别能力：**
- CSV/Excel 自动匹配坐标列（支持 lon/lng/longitude/经度/x 等别名）
- CSV/Excel 含地址列但无坐标时，自动批量 geocoding 转换为空间数据
- 文件编码自动检测（UTF-8/GBK/Latin-1）
- 坐标系自动推断（坐标范围检测，识别 WGS84/GCJ-02/BD-09/CGCS2000）
- GeoJSON 嵌套在普通 JSON 中时，递归扫描提取 FeatureCollection 节点

#### 请求

```
Content-Type: multipart/form-data

file: <binary>
session_id: "uuid-xxx"     (可选)
crs: "EPSG:4326"           (可选，默认WGS84)
```

#### 响应

```json
{
  "file_id": "file-uuid-xxx",
  "filename": "stations.geojson",
  "type": "geojson",
  "size": 125430,
  "feature_count": 326,
  "geometry_type": "Point",
  "bbox": [116.12, 39.68, 116.78, 40.18],
  "crs": "EPSG:4326",
  "properties": [
    {"name": "name", "type": "string", "sample": "西直门站"},
    {"name": "line", "type": "string", "sample": "2号线"},
    {"name": "passengers", "type": "number", "sample": 85432}
  ],
  "preview": {
    "type": "FeatureCollection",
    "features": [/* 前5条 */]
  }
}
```

#### 文件大小限制

| 格式 | 最大大小 |
|------|---------|
| GeoJSON/JSON | 50MB |
| CSV | 30MB |
| Excel (.xlsx/.xls) | 30MB |
| KML/KMZ | 20MB |
| GPX | 20MB |
| SHP(zip) | 100MB |

---

## 4. 会话管理接口

### GET /api/sessions

获取所有会话列表。

#### 响应

```json
{
  "sessions": [
    {
      "id": "uuid-1",
      "title": "北京地铁站分析",
      "created_at": "2026-03-11T10:30:00Z",
      "updated_at": "2026-03-11T11:15:00Z",
      "message_count": 8,
      "layer_count": 3
    },
    {
      "id": "uuid-2",
      "title": "上海绿地覆盖分析",
      "created_at": "2026-03-10T14:00:00Z",
      "updated_at": "2026-03-10T15:20:00Z",
      "message_count": 5,
      "layer_count": 2
    }
  ]
}
```

### GET /api/sessions/{id}

获取会话详情（含历史消息）。

#### 响应

```json
{
  "id": "uuid-1",
  "title": "北京地铁站分析",
  "created_at": "2026-03-11T10:30:00Z",
  "messages": [
    {
      "role": "user",
      "content": "分析北京地铁站分布密度",
      "timestamp": "2026-03-11T10:30:00Z"
    },
    {
      "role": "assistant",
      "content": "分析完成。北京共有326个地铁站...",
      "timestamp": "2026-03-11T10:30:25Z",
      "map_commands": [/* 该回复产生的地图指令 */],
      "charts": [/* 图表数据 */]
    }
  ],
  "layers": [
    {
      "id": "subway_density",
      "name": "地铁站密度热力图",
      "type": "heatmap",
      "visible": true,
      "created_at": "2026-03-11T10:30:25Z"
    }
  ],
  "files": [
    {
      "file_id": "file-uuid",
      "filename": "stations.geojson",
      "feature_count": 326
    }
  ]
}
```

### DELETE /api/sessions/{id}

删除会话及关联数据（图层、上传文件）。

#### 响应

```json
{
  "success": true,
  "deleted": {
    "messages": 8,
    "layers": 3,
    "files": 1
  }
}
```

---

## 5. 图层管理接口

### GET /api/layers/{session_id}

获取会话中的图层列表。

#### 响应

```json
{
  "layers": [
    {
      "id": "subway_stations",
      "name": "北京地铁站",
      "type": "geojson",
      "geometry_type": "Point",
      "feature_count": 326,
      "visible": true,
      "style": {
        "color": "#ff6b35",
        "size": 8,
        "opacity": 0.8
      },
      "bbox": [116.12, 39.68, 116.78, 40.18]
    },
    {
      "id": "subway_density",
      "name": "地铁站密度热力图",
      "type": "heatmap",
      "visible": true,
      "style": {
        "radius": 30,
        "gradient": {"0.4": "blue", "0.6": "green", "0.8": "yellow", "1.0": "red"}
      }
    }
  ]
}
```

---

## 6. 报告导出接口

### POST /api/analysis/export

将分析报告导出为文件。

#### 请求

```json
{
  "session_id": "uuid-xxx",
  "format": "markdown",        // markdown | html | pdf
  "include_charts": true,
  "include_map_screenshot": false
}
```

#### 响应

```
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="分析报告-北京地铁站.md"

<文件二进制内容>
```

---

## 7. 配置接口

### GET /api/config

前端启动时获取配置。

#### 响应

```json
{
  "cesium_token": "eyJ...",           // Cesium Ion Token
  "tianditu_token": "xxx",           // 天地图Token
  "max_upload_size": 52428800,       // 50MB
  "supported_formats": [".geojson", ".json", ".csv", ".xlsx", ".xls", ".kml", ".kmz", ".gpx", ".zip"],
  "available_models": [
    {"id": "deepseek-chat", "name": "DeepSeek Chat", "default": true},
    {"id": "qwen-plus", "name": "通义千问Plus"}
  ],
  "available_basemaps": [
    {"id": "tianditu_vec", "name": "天地图矢量"},
    {"id": "tianditu_img", "name": "天地图影像"},
    {"id": "osm", "name": "OpenStreetMap"},
    {"id": "dark", "name": "暗色底图"}
  ]
}
```

---

## 8. 健康检查

### GET /api/health

```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": {
    "llm": "ok",
    "postgis": "ok",
    "redis": "ok"
  }
}
```

---

## 9. 错误码

| 错误码 | HTTP状态 | 说明 |
|--------|---------|------|
| INVALID_INPUT | 400 | 输入参数不合法 |
| FILE_TOO_LARGE | 413 | 文件超出大小限制 |
| UNSUPPORTED_FORMAT | 415 | 不支持的文件格式 |
| SESSION_NOT_FOUND | 404 | 会话不存在 |
| RATE_LIMIT | 429 | 请求频率超限 |
| LLM_ERROR | 502 | LLM服务调用失败 |
| TOOL_ERROR | 500 | 工具执行失败 |
| INTERNAL_ERROR | 500 | 内部错误 |
