import { defineStore } from 'pinia'
import { ref, shallowRef, toRaw } from 'vue'
import * as Cesium from 'cesium'
import { CesiumBridge } from 'cesium-mcp-bridge'
import type { LayerInfo, BridgeCommand } from 'cesium-mcp-bridge'
import { useResultStore } from './resultStore'

export type { LayerInfo as MapLayer }
export type MapCommand = BridgeCommand

export const useMapStore = defineStore('map', () => {
  const layers = ref<LayerInfo[]>([])
  const currentBasemap = ref('dark')
  const viewer = shallowRef<Cesium.Viewer | null>(null)
  const bridge = shallowRef<CesiumBridge | null>(null)
  const wsConnected = ref(false)

  const _pendingCommands: MapCommand[] = []
  let _ws: WebSocket | null = null
  let _wsReconnectTimer: ReturnType<typeof setTimeout> | null = null

  /** MapView 初始化后调用 */
  function setViewer(v: Cesium.Viewer) {
    viewer.value = v
    const b = new CesiumBridge(v)
    // 让 bridge 的 layerManager 共享响应式 layers 数组
    b.layerManager.setLayersRef(layers.value)
    bridge.value = b

    while (_pendingCommands.length) {
      executeCommand(_pendingCommands.shift()!)
    }
  }

  function toggleLayer(id: string) {
    bridge.value?.toggleLayer(id)
  }

  function removeLayer(id: string) {
    bridge.value?.removeLayer(id)
  }

  function toggleTrajectory(trajectoryId: string): boolean {
    return bridge.value?.toggleTrajectory(trajectoryId) ?? false
  }

  function isTrajectoryPlaying(trajectoryId: string): boolean {
    return bridge.value?.isTrajectoryPlaying(trajectoryId) ?? false
  }

  function zoomToLayer(id: string) {
    bridge.value?.zoomToLayer(id)
  }

  // ==================== CommandExecutor ====================

  async function executeCommand(cmd: MapCommand) {
    if (!bridge.value) {
      _pendingCommands.push(cmd)
      return
    }

    // setBasemap 需要同步 currentBasemap 状态
    if (cmd.action === 'setBasemap') {
      currentBasemap.value = (cmd.params as any).basemap ?? 'dark'
    }

    const result = await bridge.value.execute(cmd)
    if (!result.success) {
      console.warn('[CesiumBridge]', cmd.action, result.error)
    }
  }

  // ==================== WebSocket (cesium-mcp-runtime) ====================

  function connectRuntime(wsUrl: string, sessionId?: string) {
    if (_ws && _ws.readyState <= WebSocket.OPEN) return

    const url = `${wsUrl}?session=${sessionId ?? 'default'}`
    console.log('[mapStore] connecting runtime WS:', url)
    const ws = new WebSocket(url)

    ws.onopen = () => {
      wsConnected.value = true
      console.log('[mapStore] runtime WS connected')
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.method) {
          const cmd: MapCommand = { action: msg.method, params: msg.params ?? {} }
          executeCommand(cmd)
          const rs = useResultStore()
          rs.addMapCommand({ action: cmd.action, params: cmd.params ?? {}, timestamp: Date.now() })
          if (msg.id) {
            ws.send(JSON.stringify({ id: msg.id, result: { success: true } }))
          }
        }
      } catch { /* ignore */ }
    }

    ws.onclose = () => {
      wsConnected.value = false
      _ws = null
      console.log('[mapStore] runtime WS closed, reconnecting in 3s...')
      _wsReconnectTimer = setTimeout(() => connectRuntime(wsUrl, sessionId), 3000)
    }

    ws.onerror = () => { /* onclose will fire after this */ }

    _ws = ws
  }

  function disconnectRuntime() {
    if (_wsReconnectTimer) clearTimeout(_wsReconnectTimer)
    _wsReconnectTimer = null
    if (_ws) {
      _ws.onclose = null
      _ws.close()
      _ws = null
    }
    wsConnected.value = false
  }

  async function restoreLayers() {
    const resultStore = useResultStore()
    const cmds = resultStore.mapCommands
    if (!cmds.length) return

    const layerActions = new Set(['addGeoJsonLayer', 'addLabel', 'addHeatmap', 'setBasemap'])
    const fetchedData = new Map<string, any>()

    for (const cmd of cmds) {
      if (!layerActions.has(cmd.action)) continue

      const params = { ...cmd.params } as Record<string, any>
      const refId = params.dataRefId || params.data_ref_id

      if ((cmd.action === 'addGeoJsonLayer' || cmd.action === 'addLabel') && refId && !params.data) {
        if (!fetchedData.has(refId)) {
          try {
            const res = await fetch(`/api/data/${refId}/export?format=geojson`)
            if (res.ok) {
              fetchedData.set(refId, await res.json())
            } else {
              console.warn(`[restoreLayers] fetch ${refId} failed:`, res.status)
              continue
            }
          } catch (e) {
            console.warn(`[restoreLayers] fetch ${refId} error:`, e)
            continue
          }
        }
        params.data = fetchedData.get(refId)
      }

      await executeCommand({ action: cmd.action, params } as MapCommand)
    }
  }

  return {
    layers,
    currentBasemap,
    viewer,
    bridge,
    wsConnected,
    setViewer,
    toggleLayer,
    removeLayer,
    toggleTrajectory,
    isTrajectoryPlaying,
    zoomToLayer,
    executeCommand,
    connectRuntime,
    disconnectRuntime,
    restoreLayers,
  }
})
