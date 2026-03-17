/**
 * 分析结果 Store：收集 Agent 工具返回的数据，供 ResultPanel 展示
 *
 * 数据来源：chatStore 的 tool_result 事件中的 preview / summary / dataRefId
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface ToolResultEntry {
  step: number
  toolName: string
  success: boolean
  summary: string
  dataRefId: string | null
  preview: {
    featureCount?: number
    geometryType?: string
    bbox?: number[]
    sampleProperties?: string[]
  } | null
  timestamp: number
}

export interface ChartOptionEntry {
  option: Record<string, unknown>
  chartType: string
  title: string
  timestamp: number
}

export interface ReportContent {
  content: string
  format: 'markdown' | 'html'
}

export interface MapCommandEntry {
  action: string
  params: Record<string, unknown>
  timestamp: number
}

const STORAGE_PREFIX = 'geoagent_result_'

export const useResultStore = defineStore('result', () => {
  const toolResults = ref<ToolResultEntry[]>([])
  const chartOptions = ref<ChartOptionEntry[]>([])
  const report = ref<ReportContent | null>(null)
  const showReportModal = ref(false)
  const mapCommands = ref<MapCommandEntry[]>([])
  let _currentSessionId = ''

  const latestResults = computed(() =>
    [...toolResults.value].sort((a, b) => b.timestamp - a.timestamp)
  )

  const dataLayers = computed(() =>
    toolResults.value.filter(r => r.dataRefId && r.success)
  )

  const statistics = computed(() => {
    const total = toolResults.value.length
    const success = toolResults.value.filter(r => r.success).length
    const failed = total - success
    const totalFeatures = toolResults.value.reduce(
      (sum, r) => sum + (r.preview?.featureCount ?? 0), 0
    )
    return { total, success, failed, totalFeatures }
  })

  function _autoSave() {
    if (_currentSessionId) saveToStorage(_currentSessionId)
  }

  /** 由 chatStore SSE 事件调用 */
  function addToolResult(result: ToolResultEntry) {
    toolResults.value.push(result)
    _autoSave()
  }

  function addChartOption(entry: ChartOptionEntry) {
    chartOptions.value.push(entry)
    _autoSave()
  }

  function setReport(r: ReportContent) {
    report.value = r
    _autoSave()
  }

  function addMapCommand(cmd: MapCommandEntry) {
    const slim = { ...cmd, params: { ...cmd.params } }
    delete (slim.params as any).data
    mapCommands.value.push(slim)
    _autoSave()
  }

  function clear() {
    toolResults.value = []
    chartOptions.value = []
    report.value = null
    mapCommands.value = []
  }

  function saveToStorage(sessionId: string) {
    const data = {
      toolResults: toolResults.value,
      chartOptions: chartOptions.value,
      report: report.value,
      mapCommands: mapCommands.value,
    }
    try {
      localStorage.setItem(STORAGE_PREFIX + sessionId, JSON.stringify(data))
    } catch { /* quota exceeded — ignore */ }
  }

  function loadFromStorage(sessionId: string) {
    _currentSessionId = sessionId
    const raw = localStorage.getItem(STORAGE_PREFIX + sessionId)
    if (!raw) {
      clear()
      return
    }
    try {
      const data = JSON.parse(raw)
      toolResults.value = data.toolResults ?? []
      chartOptions.value = data.chartOptions ?? []
      report.value = data.report ?? null
      mapCommands.value = data.mapCommands ?? []
    } catch {
      clear()
    }
  }

  function removeStorage(sessionId: string) {
    localStorage.removeItem(STORAGE_PREFIX + sessionId)
  }

  return {
    toolResults,
    chartOptions,
    report,
    showReportModal,
    mapCommands,
    latestResults,
    dataLayers,
    statistics,
    addToolResult,
    addChartOption,
    setReport,
    addMapCommand,
    clear,
    saveToStorage,
    loadFromStorage,
    removeStorage,
  }
})
