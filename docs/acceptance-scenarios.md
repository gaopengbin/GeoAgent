# GeoAgent 验收场景

## 场景设计原则
- 每个场景覆盖一条核心链路（工具组合）
- 验证点包括：工具选择正确性、数据重用、地图展示、结果准确性
- 场景之间有递进关系，从简单到复杂

---

## 场景1：地理编码 + 地图定位
**用户输入**: "飞到北京天安门"
**期望链路**:
1. `amap_geocoding("天安门")` → 返回坐标 (116.39xx, 39.90xx)
2. `generate_map_command("flyTo", longitude=116.39xx, latitude=39.90xx)`

**验证点**:
- [x] 使用 amap_geocoding 而非 geocoding/nominatim
- [ ] 地图相机飞到天安门位置
- [ ] 返回坐标为 WGS84

**追加测试**: "在地图上标注天安门"
**期望**: `generate_map_command("addLabel", ...)` — 复用上一步坐标，不重新地理编码

---

## 场景2：POI 搜索 + 图层展示
**用户输入**: "搜索北京三里屯周边2公里的咖啡店"
**期望链路**:
1. `amap_geocoding("北京三里屯")` → 坐标
2. `amap_around_search(query="咖啡店", location="lon,lat", radius=2000)`
3. `generate_map_command("addGeoJsonLayer", data_ref_id="ref_xxx")`
4. `generate_map_command("flyTo", data_ref_id="ref_xxx")`

**验证点**:
- [ ] 使用 amap_around_search 而非 fetch_osm_data
- [ ] 地图上显示 POI 点位图层
- [ ] 图层颜色和样式可见

---

## 场景3：路径规划 + 轨迹播放
**用户输入**: "规划从天安门到故宫的步行路线"
**期望链路**:
1. `amap_geocoding("天安门")` → 起点坐标（如上下文已有则复用）
2. `amap_geocoding("故宫")` → 终点坐标
3. `amap_route_planning(origin="lon1,lat1", destination="lon2,lat2", mode="walking")`
4. `generate_map_command("addGeoJsonLayer", data_ref_id="ref_route")`
5. `generate_map_command("playTrajectory", data_ref_id="ref_route")`

**验证点**:
- [ ] 路线在地图上可见（LineString 彩色粗线）
- [ ] 轨迹播放不闪烁，固定俯视视角
- [ ] 路线坐标已转 WGS84（非 GCJ-02 偏移）

---

## 场景4：坐标转换
**用户输入**: "天安门的坐标是多少"
**期望链路**:
1. `amap_geocoding("天安门")` → (116.3912, 39.9078)

**追加**: "转为CGCS2000坐标系"
**期望**:
1. `convert_point(longitude=116.3912, latitude=39.9078, target_crs="EPSG:4490")` — 复用已有坐标

**验证点**:
- [ ] 不重新调用 amap_geocoding
- [ ] 使用 convert_point 而非 transform_crs
- [ ] 正确说明 CGCS2000 与 WGS84 差异极小

---

## 场景5：数据上传 + 统计分析 + 图表
**前置**: 上传一份包含多边形的 GeoJSON/Shapefile
**用户输入**: "加载我上传的数据"
**期望链路**:
1. `load_uploaded_file(file_id="xxx")` → ref_001
2. `generate_map_command("addGeoJsonLayer", data_ref_id="ref_001")`
3. `generate_map_command("flyTo", data_ref_id="ref_001")`

**追加**: "统计面积分布并生成图表"
**期望**:
1. `enrich_geometry_fields(data_ref_id="ref_001")` → ref_002（补充面积字段）
2. `field_statistics(data_ref_id="ref_002", field="area_m2")` → 统计结果
3. `generate_chart(...)` → 柱状图/直方图

**验证点**:
- [ ] 图层在地图上可见
- [ ] 图表在底部面板正确渲染（柱/线在图表区域内）
- [ ] 上传数据后不主动分析，等用户指令

---

## 场景6：空间分析（缓冲+查询）
**用户输入**: "北京朝阳区地铁站500米范围内有多少便利店"
**期望链路**:
1. `amap_poi_search(query="地铁站", city="北京", citylimit=true)` → ref_subway
2. `buffer_analysis(data_ref_id="ref_subway", distance=500)` → ref_buffer
3. `amap_poi_search(query="便利店", city="北京", citylimit=true)` → ref_store
4. `spatial_query("intersects", target_ref="ref_store", mask_ref="ref_buffer")` → ref_result
5. `generate_map_command("addGeoJsonLayer", data_ref_id="ref_result")`

**验证点**:
- [ ] POI 搜索使用高德而非 OSM
- [ ] 缓冲区分析正确执行
- [ ] 空间查询返回正确交集
- [ ] 结果数量合理

---

## 场景7：天气查询（纯文本）
**用户输入**: "今天北京天气怎么样"
**期望链路**:
1. `amap_weather(city="北京")`

**验证点**:
- [ ] 直接调用 amap_weather，不走 geocoding
- [ ] 返回清晰的天气摘要

---

## 场景8：多轮对话上下文重用
**第1轮**: "搜索上海陆家嘴周边1公里的餐厅" → ref_restaurant
**第2轮**: "这些餐厅中哪些在500米范围内有地铁站"
**期望**:
1. 复用 ref_restaurant（不重新搜索餐厅）
2. `amap_around_search(query="地铁站", ...)` 或 `amap_poi_search` → ref_subway
3. `buffer_analysis(data_ref_id="ref_subway", distance=500)` → ref_buffer
4. `spatial_query("intersects", target_ref="ref_restaurant", mask_ref="ref_buffer")`

**验证点**:
- [ ] 第2轮不重复搜索餐厅
- [ ] 正确引用第1轮的 data_ref_id

---

## 执行状态追踪

| 场景 | 状态 | 发现的问题 |
|------|------|-----------|
| 1. 地理编码+定位 | ✅ 通过 | 飞到+标注均已验证 |
| 2. POI搜索+图层 | ⬜ 待测 | |
| 3. 路径规划+播放 | ✅ 通过 | 已修复：动画匀速、播放/暂停控制、起终点用geocoding |
| 4. 坐标转换 | ⬜ 待测 | |
| 5. 上传+统计+图表 | ⬜ 待测 | |
| 6. 空间分析 | ⬜ 待测 | |
| 7. 天气查询 | ⬜ 待测 | |
| 8. 多轮上下文重用 | ⬜ 待测 | |
