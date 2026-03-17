# 测试数据

用于 GeoAgent 核心场景验收的测试数据集。

## 数据列表

| 文件 | 格式 | 要素数 | 几何类型 | 用途 |
|------|------|--------|---------|------|
| `beijing_metro_stations.geojson` | GeoJSON | 40 | Point | 地铁站分布分析：聚类、热力图、缓冲区、空间查询 |
| `beijing_pois.geojson` | GeoJSON | 30 | Point | POI 分类分析：category 分色、统计图表、空间查询 |
| `gps_trajectory.geojson` | GeoJSON | 1 (71点) | LineString | 轨迹动画播放：清华→朝阳公园骑行路线 |
| `beijing_districts.geojson` | GeoJSON | 6 | Polygon | 行政区划：填色图、面积统计、叠加分析 |
| `shops_with_sales.csv` | CSV | 26 | 经纬度列 | 商铺销售数据：CSV 上传解析、统计分析、热力图 |

## 验收场景

### 场景1：地铁站密度分析
1. 上传 `beijing_metro_stations.geojson`
2. "帮我分析这些地铁站的空间分布特征"
3. 期望：聚类分析 → 分色渲染 → 热力图 → 统计图表 → 报告

### 场景2：POI 空间查询
1. 先上传 `beijing_metro_stations.geojson`，再上传 `beijing_pois.geojson`
2. "找出地铁站500米范围内的医院"
3. 期望：缓冲区分析 → 空间查询 → 结果渲染

### 场景3：轨迹动画
1. 上传 `gps_trajectory.geojson`
2. "播放这条轨迹的动画"
3. 期望：轨迹动画播放（移动实体 + 尾迹线）

### 场景4：区域统计 + 填色图
1. 上传 `beijing_districts.geojson`
2. "按 GDP 生成填色图，并统计各区人口"
3. 期望：填色图渲染 + 统计图表

### 场景5：CSV 数据分析
1. 上传 `shops_with_sales.csv`
2. "分析各类商铺的销售分布"
3. 期望：自动识别经纬度 → 分类统计 → 热力图/分色渲染
