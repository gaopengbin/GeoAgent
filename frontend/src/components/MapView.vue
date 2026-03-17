<template>
  <div class="map-view" ref="mapContainer">
    <div id="cesiumContainer" ref="cesiumRef"></div>

    <!-- 地图工具栏 -->
    <div class="map-toolbar">
      <button
        v-for="tool in tools" :key="tool.id"
        class="toolbar-btn"
        :class="{ active: activeTool === tool.id }"
        :title="tool.label"
        @click="activeTool = activeTool === tool.id ? '' : tool.id"
      >
        <div v-html="tool.icon"></div>
      </button>
    </div>

    <!-- 图层面板 -->
    <transition name="slide-panel">
      <div v-if="showLayerPanel" class="layer-panel">
        <div class="panel-header">
          <span>图层管理</span>
          <button class="close-btn" @click="showLayerPanel = false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="layer-list">
          <div v-for="layer in mapStore.layers" :key="layer.id" class="layer-item">
            <label class="layer-toggle">
              <input type="checkbox" :checked="layer.visible" @change="mapStore.toggleLayer(layer.id)">
              <span class="layer-color" :style="{ background: layer.color }"></span>
              <span class="layer-name" :title="layer.name">{{ layer.name }}</span>
            </label>
            <div class="layer-actions">
              <span class="layer-type">{{ layer.type }}</span>
              <button class="layer-action-btn" title="缩放到" @click="mapStore.zoomToLayer(layer.id)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              </button>
              <button class="layer-action-btn delete" title="删除" @click="mapStore.removeLayer(layer.id)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>
          <div v-if="mapStore.layers.length === 0" class="empty-layers">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
            <span>暂无图层</span>
            <span class="hint">通过对话添加数据图层</span>
          </div>
        </div>
      </div>
    </transition>

    <!-- 测量面板 -->
    <transition name="slide-panel">
      <div v-if="showMeasurePanel" class="measure-panel">
        <div class="panel-header">
          <span>{{ measureMode === 'distance' ? '距离测量' : '面积测量' }}</span>
          <button class="close-btn" @click="stopMeasure">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="measure-body">
          <div class="measure-modes">
            <button :class="{ active: measureMode === 'distance' }" @click="startMeasure('distance')">距离</button>
            <button :class="{ active: measureMode === 'area' }" @click="startMeasure('area')">面积</button>
          </div>
          <div v-if="measureResult" class="measure-result">
            <span class="measure-value">{{ measureResult }}</span>
          </div>
          <div class="measure-hint">左键点击添加点，右键结束</div>
        </div>
      </div>
    </transition>

    <!-- 绘制面板 -->
    <transition name="slide-panel">
      <div v-if="showDrawPanel" class="draw-panel">
        <div class="panel-header">
          <span>绘制工具</span>
          <button class="close-btn" @click="stopDraw">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="measure-body">
          <div class="measure-modes">
            <button :class="{ active: drawMode === 'point' }" @click="startDraw('point')">点</button>
            <button :class="{ active: drawMode === 'line' }" @click="startDraw('line')">线</button>
            <button :class="{ active: drawMode === 'polygon' }" @click="startDraw('polygon')">面</button>
          </div>
          <div v-if="drawPointCount > 0" class="measure-result">
            <span class="measure-value">已绘制 {{ drawPointCount }} 个点</span>
          </div>
          <div class="draw-actions" v-if="drawPointCount > 0">
            <button class="draw-action-btn" @click="finishDraw">完成绘制</button>
            <button class="draw-action-btn secondary" @click="clearDraw">清除</button>
          </div>
          <div class="measure-hint">左键点击添加点，右键或点“完成绘制”结束</div>
        </div>
      </div>
    </transition>

    <!-- 底图切换 -->
    <div class="basemap-switcher">
      <div
        v-for="bm in basemaps" :key="bm.id"
        class="basemap-option"
        :class="{ active: currentBasemap === bm.id }"
        @click="switchBasemap(bm.id)"
      >
        <div class="basemap-preview" :style="{ background: bm.color }">
          <svg v-if="bm.id === 'dark'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
          <svg v-else-if="bm.id === 'satellite'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2c2.5 3 4 6.5 4 10s-1.5 7-4 10c-2.5-3-4-6.5-4-10s1.5-7 4-10z"/></svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="3" x2="9" y2="21"/></svg>
        </div>
        <span class="basemap-label">{{ bm.label }}</span>
      </div>
    </div>

    <!-- 坐标显示 -->
    <div class="coord-display">
      <span>{{ lng.toFixed(4) }}°E, {{ lat.toFixed(4) }}°N</span>
      <span class="separator">|</span>
      <span>缩放: {{ zoom }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useMapStore } from '../stores/mapStore'
import { useChatStore } from '../stores/chatStore'
import { useConfigStore } from '../stores/configStore'
import { useResultStore } from '../stores/resultStore'
import { apiPost } from '../api/client'
import * as Cesium from 'cesium'

const mapStore = useMapStore()
const chatStore = useChatStore()
const configStore = useConfigStore()
const resultStore = useResultStore()

const cesiumRef = ref<HTMLDivElement>()
const activeTool = ref('')
const showLayerPanel = ref(false)
const showMeasurePanel = ref(false)
const measureMode = ref<'distance' | 'area'>('distance')
const measureResult = ref('')
const showDrawPanel = ref(false)
const drawMode = ref<'point' | 'line' | 'polygon'>('point')
const drawPointCount = ref(0)
const lng = ref(116.3912)
const lat = ref(39.9073)
const zoom = ref(10)

// 测量状态
let _measureHandler: Cesium.ScreenSpaceEventHandler | null = null
let _measurePoints: Cesium.Cartesian3[] = []
let _measureEntities: Cesium.Entity[] = []

// SSE map_command 监听注销函数
let _unregMapCmd: (() => void) | null = null

// 图层恢复（仅执行一次）
let _layersRestored = false
function _tryRestoreOnce() {
  if (_layersRestored || !mapStore.bridge || resultStore.mapCommands.length === 0) return
  _layersRestored = true
  mapStore.restoreLayers().catch(e => console.warn('[MapView] restoreLayers failed:', e))
}
const _stopRestoreWatch = watch(
  () => resultStore.mapCommands.length,
  (len) => { if (len > 0) { _tryRestoreOnce(); _stopRestoreWatch() } },
)

// 绘制状态
let _drawHandler: Cesium.ScreenSpaceEventHandler | null = null
let _drawPoints: Cesium.Cartographic[] = []
let _drawEntities: Cesium.Entity[] = []

const currentBasemap = computed(() => mapStore.currentBasemap)

const tools = [
  {
    id: 'layers',
    label: '图层',
    icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>'
  },
  {
    id: 'measure',
    label: '测量',
    icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 2L22 22M5.5 5.5l2-2M9 9l2-2M12.5 12.5l2-2M16 16l2-2"/></svg>'
  },
  {
    id: 'draw',
    label: '绘制',
    icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/></svg>'
  },
  {
    id: 'screenshot',
    label: '截图',
    icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/><circle cx="12" cy="13" r="4"/></svg>'
  },
]

const defaultBasemaps = [
  { id: 'dark', label: '暗色', color: '#1a1a2e' },
  { id: 'satellite', label: '卫星', color: '#2d5a27' },
  { id: 'standard', label: '标准', color: '#e8e4d8' },
]

const basemaps = computed(() => {
  if (configStore.availableBasemaps.length) {
    return configStore.availableBasemaps.map(b => ({
      id: b.id,
      label: b.name,
      color: b.color ?? '#666',
    }))
  }
  return defaultBasemaps
})

function switchBasemap(id: string) {
  mapStore.executeCommand({ action: 'setBasemap', params: { basemap: id } })
}


onMounted(() => {
  if (!cesiumRef.value) return
  try {
    const v = new Cesium.Viewer(cesiumRef.value, {
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      shadows: false,
      shouldAnimate: false,
    })

    // 设置暗色底图
    v.scene.backgroundColor = Cesium.Color.fromCssColorString('#0B1120')
    v.scene.globe.baseColor = Cesium.Color.fromCssColorString('#0B1120')

    // 初始视角：中国
    v.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(104.0, 35.0, 6000000),
      duration: 0,
    })

    // 坐标跟踪
    const handler = new Cesium.ScreenSpaceEventHandler(v.scene.canvas)
    handler.setInputAction((movement: Cesium.ScreenSpaceEventHandler.MotionEvent) => {
      const cartesian = v.camera.pickEllipsoid(movement.endPosition)
      if (cartesian) {
        const carto = Cesium.Cartographic.fromCartesian(cartesian)
        lng.value = Cesium.Math.toDegrees(carto.longitude)
        lat.value = Cesium.Math.toDegrees(carto.latitude)
      }
    }, Cesium.ScreenSpaceEventType.MOUSE_MOVE)

    // 注册到 mapStore（触发排队指令执行）
    mapStore.setViewer(v)

    // 图层恢复通过 watcher 触发（等待 loadFromStorage 完成）
    _tryRestoreOnce()

    // SSE fallback：当 cesium-mcp-runtime 不可用时，后端会通过 SSE 推送 map_command
    _unregMapCmd = chatStore.onMapCommand((cmd) => {
      console.log('[MapView] SSE map_command received:', cmd)
      mapStore.executeCommand(cmd)
    })

    // 连接 cesium-mcp-runtime WebSocket（优先通道）
    if (configStore.cesiumRuntimeWsUrl) {
      mapStore.connectRuntime(configStore.cesiumRuntimeWsUrl, 'geoagent')
    }
  } catch (e) {
    console.warn('Cesium init failed:', e)
  }
})

onUnmounted(() => {
  _unregMapCmd?.()
  _unregMapCmd = null
  mapStore.disconnectRuntime()
  clearMeasure()
  clearDraw()
})

watch(activeTool, (val) => {
  if (val === 'layers') {
    showLayerPanel.value = true
    activeTool.value = ''
  } else if (val === 'screenshot') {
    doScreenshot()
    activeTool.value = ''
  } else if (val === 'measure') {
    stopDraw()
    showMeasurePanel.value = true
    startMeasure('distance')
  } else if (val === 'draw') {
    stopMeasure()
    showDrawPanel.value = true
    startDraw('point')
  } else {
    stopMeasure()
    stopDraw()
  }
})

// ==================== 截图 ====================

async function doScreenshot() {
  const bridge = mapStore.bridge
  if (!bridge) return
  const result = await bridge.screenshot()
  const link = document.createElement('a')
  link.href = result.dataUrl
  link.download = `geoagent_screenshot_${Date.now()}.png`
  link.click()
}

// ==================== 测量 ====================

function startMeasure(mode: 'distance' | 'area') {
  clearMeasure()
  measureMode.value = mode
  measureResult.value = ''
  showMeasurePanel.value = true

  const viewer = mapStore.viewer
  if (!viewer) return

  _measureHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
  _measurePoints = []

  // 左键添加点
  _measureHandler.setInputAction((click: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
    const cartesian = viewer.camera.pickEllipsoid(click.position)
    if (!cartesian) return
    _measurePoints.push(cartesian)

    // 添加点标记
    const entity = viewer.entities.add({
      position: cartesian,
      point: {
        pixelSize: 8,
        color: Cesium.Color.fromCssColorString('#3B82F6'),
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 1,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    })
    _measureEntities.push(entity)

    // 添加线段
    if (_measurePoints.length > 1) {
      const lineEntity = viewer.entities.add({
        polyline: {
          positions: [..._measurePoints],
          width: 2,
          material: Cesium.Color.fromCssColorString('#3B82F6').withAlpha(0.8),
          clampToGround: true,
        },
      })
      _measureEntities.push(lineEntity)
    }

    updateMeasureResult()
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

  // 右键结束
  _measureHandler.setInputAction(() => {
    if (measureMode.value === 'area' && _measurePoints.length >= 3) {
      // 闭合多边形
      const viewer = mapStore.viewer
      if (viewer) {
        const polygonEntity = viewer.entities.add({
          polygon: {
            hierarchy: new Cesium.PolygonHierarchy(_measurePoints),
            material: Cesium.Color.fromCssColorString('#3B82F6').withAlpha(0.2),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString('#3B82F6'),
          },
        })
        _measureEntities.push(polygonEntity)
      }
    }
    updateMeasureResult()
    // 停止交互但保留结果
    _measureHandler?.destroy()
    _measureHandler = null
  }, Cesium.ScreenSpaceEventType.RIGHT_CLICK)
}

function updateMeasureResult() {
  if (_measurePoints.length < 2) {
    measureResult.value = ''
    return
  }

  if (measureMode.value === 'distance') {
    let totalDist = 0
    for (let i = 1; i < _measurePoints.length; i++) {
      const c1 = Cesium.Cartographic.fromCartesian(_measurePoints[i - 1]!)
      const c2 = Cesium.Cartographic.fromCartesian(_measurePoints[i]!)
      const geodesic = new Cesium.EllipsoidGeodesic(c1, c2)
      totalDist += geodesic.surfaceDistance
    }
    measureResult.value = totalDist > 1000
      ? `${(totalDist / 1000).toFixed(2)} km`
      : `${totalDist.toFixed(1)} m`
  } else if (measureMode.value === 'area' && _measurePoints.length >= 3) {
    // 球面多边形面积近似计算
    const positions = _measurePoints.map(p => Cesium.Cartographic.fromCartesian(p))
    let area = 0
    for (let i = 0; i < positions.length; i++) {
      const j = (i + 1) % positions.length
      const p1 = positions[i]!
      const p2 = positions[j]!
      area += (p2.longitude - p1.longitude) * (2 + Math.sin(p1.latitude) + Math.sin(p2.latitude))
    }
    area = Math.abs(area * 6378137 * 6378137 / 2)
    measureResult.value = area > 1e6
      ? `${(area / 1e6).toFixed(2)} km²`
      : `${area.toFixed(0)} m²`
  }
}

function clearMeasure() {
  _measureHandler?.destroy()
  _measureHandler = null
  _measurePoints = []
  const viewer = mapStore.viewer
  if (viewer) {
    _measureEntities.forEach(e => viewer.entities.remove(e))
  }
  _measureEntities = []
  measureResult.value = ''
}

function stopMeasure() {
  clearMeasure()
  showMeasurePanel.value = false
  activeTool.value = ''
}

// ==================== 绘制 ====================

function startDraw(mode: 'point' | 'line' | 'polygon') {
  clearDraw()
  drawMode.value = mode
  drawPointCount.value = 0
  showDrawPanel.value = true

  const viewer = mapStore.viewer
  if (!viewer) return

  _drawHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
  _drawPoints = []

  _drawHandler.setInputAction((click: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
    const cartesian = viewer.camera.pickEllipsoid(click.position)
    if (!cartesian) return
    const carto = Cesium.Cartographic.fromCartesian(cartesian)
    _drawPoints.push(carto)
    drawPointCount.value = _drawPoints.length

    const entity = viewer.entities.add({
      position: cartesian,
      point: {
        pixelSize: 8,
        color: Cesium.Color.fromCssColorString('#F59E0B'),
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 1,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    })
    _drawEntities.push(entity)

    if (mode === 'point') {
      // 点模式：每点击即为一个独立点，不连线
    } else if (_drawPoints.length > 1) {
      const positions = _drawPoints.map(c =>
        Cesium.Cartesian3.fromRadians(c.longitude, c.latitude),
      )
      // 更新线条（删除旧线重绘）
      const oldLine = _drawEntities.find(e => (e as any).__drawLine)
      if (oldLine) {
        viewer.entities.remove(oldLine)
        _drawEntities = _drawEntities.filter(e => e !== oldLine)
      }
      const lineEntity = viewer.entities.add({
        polyline: {
          positions,
          width: 2,
          material: Cesium.Color.fromCssColorString('#F59E0B').withAlpha(0.8),
          clampToGround: true,
        },
      })
      ;(lineEntity as any).__drawLine = true
      _drawEntities.push(lineEntity)
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

  _drawHandler.setInputAction(() => {
    finishDraw()
  }, Cesium.ScreenSpaceEventType.RIGHT_CLICK)
}

async function finishDraw() {
  _drawHandler?.destroy()
  _drawHandler = null

  if (_drawPoints.length === 0) return

  const viewer = mapStore.viewer
  const mode = drawMode.value

  // 绘制多边形填充
  if (mode === 'polygon' && _drawPoints.length >= 3 && viewer) {
    const positions = _drawPoints.map(c =>
      Cesium.Cartesian3.fromRadians(c.longitude, c.latitude),
    )
    const polygonEntity = viewer.entities.add({
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(positions),
        material: Cesium.Color.fromCssColorString('#F59E0B').withAlpha(0.2),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString('#F59E0B'),
      },
    })
    _drawEntities.push(polygonEntity)
  }

  // 转 GeoJSON
  const geojson = drawToGeoJSON(mode, _drawPoints)
  if (!geojson) return

  const typeLabel = mode === 'point' ? '点' : mode === 'line' ? '线' : '面'
  const sessionId = chatStore.currentSessionId

  if (sessionId) {
    try {
      const res = await apiPost<{ data_ref_id: string; feature_count: number; geometry_type: string }>(
        '/register_geojson',
        { session_id: sessionId, geojson, source: `draw:${mode}` },
      )
      chatStore.sendMessage(
        `我在地图上绘制了${_drawPoints.length}个${typeLabel}，已注册为 data_ref_id="${res.data_ref_id}"（${res.feature_count}个${res.geometry_type}要素）。请在地图上展示并分析。`,
      )
    } catch {
      chatStore.sendMessage(
        `我在地图上绘制了${_drawPoints.length}个${typeLabel}，请分析。\n\n\`\`\`json\n${JSON.stringify(geojson)}\n\`\`\``,
      )
    }
  } else {
    chatStore.sendMessage(
      `我在地图上绘制了${_drawPoints.length}个${typeLabel}，请分析。\n\n\`\`\`json\n${JSON.stringify(geojson)}\n\`\`\``,
    )
  }
}

function drawToGeoJSON(mode: string, points: Cesium.Cartographic[]): Record<string, unknown> | null {
  if (points.length === 0) return null

  const toCoord = (c: Cesium.Cartographic) => [
    +Cesium.Math.toDegrees(c.longitude).toFixed(6),
    +Cesium.Math.toDegrees(c.latitude).toFixed(6),
  ]

  if (mode === 'point') {
    return {
      type: 'FeatureCollection',
      features: points.map((p, i) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: toCoord(p) },
        properties: { id: i + 1 },
      })),
    }
  }

  if (mode === 'line' && points.length >= 2) {
    return {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: points.map(toCoord) },
        properties: { id: 1 },
      }],
    }
  }

  if (mode === 'polygon' && points.length >= 3) {
    const coords = points.map(toCoord)
    coords.push(coords[0]!) // 闭合
    return {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [coords] },
        properties: { id: 1 },
      }],
    }
  }

  return null
}

function clearDraw() {
  _drawHandler?.destroy()
  _drawHandler = null
  _drawPoints = []
  drawPointCount.value = 0
  const viewer = mapStore.viewer
  if (viewer) {
    _drawEntities.forEach(e => viewer.entities.remove(e))
  }
  _drawEntities = []
}

function stopDraw() {
  clearDraw()
  showDrawPanel.value = false
  activeTool.value = ''
}
</script>

<style scoped>
.map-view {
  width: 100%;
  height: 100%;
  position: relative;
  background: var(--bg-primary);
}

#cesiumContainer {
  width: 100%;
  height: 100%;
}

/* 隐藏 Cesium 自带的 UI */
:deep(.cesium-viewer-bottom),
:deep(.cesium-viewer-toolbar),
:deep(.cesium-credit-logoContainer),
:deep(.cesium-credit-textContainer) {
  display: none !important;
}

.map-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 4px;
}

.toolbar-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--text-secondary);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.toolbar-btn.active {
  background: rgba(59, 130, 246, 0.2);
  color: var(--accent);
}

.layer-panel {
  position: absolute;
  top: 12px;
  right: 56px;
  width: 360px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border);
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  padding: 2px;
  border-radius: 4px;
}

.close-btn:hover {
  color: var(--text-primary);
  background: var(--bg-tertiary);
}

.layer-list {
  padding: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.layer-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 6px;
  transition: background 0.15s;
  gap: 8px;
}

.layer-item:hover {
  background: var(--bg-tertiary);
}

.layer-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.layer-toggle input[type="checkbox"] {
  accent-color: var(--accent);
}

.layer-color {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.layer-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.layer-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.layer-type {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.layer-action-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--text-muted);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.layer-action-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.layer-action-btn.delete:hover {
  color: var(--error, #EF4444);
}

.empty-layers {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px;
  color: var(--text-muted);
  font-size: 13px;
}

.empty-layers .hint {
  font-size: 11px;
  opacity: 0.7;
}

/* Measure panel */
.measure-panel {
  position: absolute;
  top: 12px;
  right: 56px;
  width: 220px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  overflow: hidden;
}

.measure-body {
  padding: 10px 14px;
}

.measure-modes {
  display: flex;
  gap: 4px;
  margin-bottom: 10px;
}

.measure-modes button {
  flex: 1;
  padding: 5px 0;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.measure-modes button.active {
  background: rgba(59, 130, 246, 0.15);
  border-color: var(--accent);
  color: var(--accent);
}

.measure-result {
  text-align: center;
  padding: 8px 0;
}

.measure-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
}

.measure-hint {
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}

.draw-panel {
  position: absolute;
  top: 12px;
  right: 56px;
  width: 220px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  overflow: hidden;
}

.draw-actions {
  display: flex;
  gap: 6px;
  padding: 4px 0;
}

.draw-action-btn {
  flex: 1;
  padding: 6px 0;
  background: var(--accent);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}

.draw-action-btn:hover {
  opacity: 0.85;
}

.draw-action-btn.secondary {
  background: var(--bg-tertiary);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.draw-action-btn.secondary:hover {
  color: var(--text-primary);
}

.basemap-switcher {
  position: absolute;
  bottom: 36px;
  right: 12px;
  display: flex;
  gap: 6px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px;
}

.basemap-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.basemap-preview {
  width: 40px;
  height: 28px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid transparent;
  transition: border-color 0.2s;
  color: white;
}

.basemap-option.active .basemap-preview {
  border-color: var(--accent);
}

.basemap-label {
  font-size: 10px;
  color: var(--text-muted);
}

.coord-display {
  position: absolute;
  bottom: 8px;
  left: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 10px;
}

.separator {
  opacity: 0.3;
}

.slide-panel-enter-active, .slide-panel-leave-active {
  transition: all 0.2s ease;
}
.slide-panel-enter-from, .slide-panel-leave-to {
  opacity: 0;
  transform: translateX(10px);
}
</style>
