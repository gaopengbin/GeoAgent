<template>
  <aside class="result-panel">
    <div class="panel-tabs">
      <button
        v-for="tab in tabs" :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        <div v-html="tab.icon"></div>
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <div class="panel-content">
      <!-- 结果视图 -->
      <div v-if="activeTab === 'chart'" class="chart-view">
        <!-- 统计概览 -->
        <div v-if="hasResults" class="stats-row">
          <div class="stat-card">
            <span class="stat-value">{{ stats.total }}</span>
            <span class="stat-label">{{ $t('result.toolCalls') }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-value success">{{ stats.success }}</span>
            <span class="stat-label">{{ $t('common.success') }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">{{ stats.totalFeatures }}</span>
            <span class="stat-label">{{ $t('result.dataFeatures') }}</span>
          </div>
        </div>

        <!-- 数据量条形图 -->
        <div v-if="resultBars.length" style="margin-top: 16px;">
          <div class="chart-header">
            <span class="chart-title">{{ $t('result.dataDistribution') }}</span>
          </div>
          <div class="mock-chart">
            <div v-for="(bar, i) in resultBars" :key="i" class="bar-item">
              <span class="bar-label">{{ bar.name }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: bar.pct + '%', background: bar.color }"></div>
              </div>
              <span class="bar-value">{{ bar.value }}</span>
            </div>
          </div>
        </div>

        <!-- ECharts 图表 -->
        <div v-if="resultStore.chartOptions.length" class="echarts-section">
          <div class="chart-header">
            <span class="chart-title">{{ $t('result.chart') }}</span>
            <span class="chart-count">{{ resultStore.chartOptions.length }}</span>
          </div>
          <div class="echarts-row">
            <div
              v-for="(chart, idx) in resultStore.chartOptions"
              :key="chart.timestamp"
              class="echarts-card"
            >
              <div class="echarts-card-title">{{ chart.title }}</div>
              <div :ref="(el) => setChartRef(el as HTMLElement | null, idx)" class="echarts-container"></div>
            </div>
          </div>
        </div>

        <!-- 执行记录 -->
        <div v-if="hasResults" style="margin-top: 16px;">
          <div class="chart-header">
            <span class="chart-title">{{ $t('result.executionLog') }}</span>
          </div>
          <div class="result-list">
            <div v-for="r in resultStore.latestResults" :key="r.timestamp" class="result-item" :class="{ error: !r.success }">
              <div class="result-icon" :class="r.success ? 'done' : 'error'">
                <svg v-if="r.success" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
              </div>
              <div class="result-info">
                <span class="result-name">{{ r.toolName }}</span>
                <span class="result-summary">{{ r.summary }}</span>
              </div>
              <span v-if="r.dataRefId" class="result-ref">{{ r.dataRefId }}</span>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="!hasResults" class="empty-results">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
            <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
          <span>{{ $t('result.noResults') }}</span>
          <span class="hint">{{ $t('result.noResultsHint') }}</span>
        </div>
      </div>

      <!-- 图层列表 -->
      <div v-if="activeTab === 'table'" class="table-view">
        <div v-if="layerList.length" class="layer-list-panel">
          <div v-for="layer in layerList" :key="layer.id" class="layer-row">
            <label class="layer-toggle">
              <input type="checkbox" :checked="layer.visible" @change="mapStore.toggleLayer(layer.id)">
              <span class="layer-color" :style="{ background: layer.color }"></span>
              <span class="layer-name">{{ layer.name }}</span>
            </label>
            <div class="layer-meta">
              <span class="layer-type-badge">{{ layer.type }}</span>
              <button v-if="layer.type === $t('result.trajectory')" class="sm-btn" :class="{ active: trajectoryPlaying[layer.id] }" @click="toggleTrajectoryPlay(layer)" :title="trajectoryPlaying[layer.id] ? $t('result.pause') : $t('result.play')">
                <svg v-if="trajectoryPlaying[layer.id]" width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                <svg v-else width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
              </button>
              <button class="sm-btn" @click="mapStore.zoomToLayer(layer.id)" :title="$t('map.zoomTo')">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              </button>
              <button v-if="layer.dataRefId" class="sm-btn" @click="exportLayerData(layer.dataRefId!, 'geojson')" :title="$t('result.exportGeoJSON')">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
              </button>
              <button class="sm-btn danger" @click="mapStore.removeLayer(layer.id)" :title="$t('common.delete')">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>
        </div>
        <div v-else class="empty-results">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          <span>{{ $t('result.noLayers') }}</span>
          <span class="hint">{{ $t('result.noLayersHint') }}</span>
        </div>
      </div>

      <!-- 报告视图 -->
      <div v-if="activeTab === 'report'" class="report-view">
        <div v-if="reportHtml" class="report-content" v-html="reportHtml"></div>
        <div v-else class="empty-results">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>
          </svg>
          <span>{{ $t('result.noReport') }}</span>
          <span class="hint">{{ $t('result.noReportHint') }}</span>
        </div>
        <div v-if="reportHtml" class="report-actions">
          <button class="action-btn primary" @click="resultStore.showReportModal = true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
            </svg>
            {{ $t('result.previewFull') }}
          </button>
          <button class="action-btn" @click="copyReport">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
            </svg>
            {{ $t('common.copy') }}
          </button>
          <button class="action-btn" @click="downloadReport">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            {{ $t('common.download') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 报告预览弹框 -->
    <Teleport to="body">
      <div v-if="resultStore.showReportModal" class="report-modal-overlay" @click.self="resultStore.showReportModal = false">
        <div class="report-modal">
          <div class="report-modal-header">
            <span class="report-modal-title">{{ $t('result.analysisReport') }}</span>
            <div class="report-modal-actions">
              <button class="action-btn" @click="copyReport" :title="$t('common.copy')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                </svg>
                {{ $t('common.copy') }}
              </button>
              <button class="action-btn" @click="downloadReport" :title="$t('common.download')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                {{ $t('result.downloadMarkdown') }}
              </button>
              <button class="report-modal-close" @click="resultStore.showReportModal = false">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          </div>
          <div class="report-modal-body" v-html="reportHtml"></div>
        </div>
      </div>
    </Teleport>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts'
import MarkdownIt from 'markdown-it'
import { useResultStore } from '../stores/resultStore'
import { useMapStore } from '../stores/mapStore'

const { t } = useI18n()
const md = new MarkdownIt()
const resultStore = useResultStore()
const mapStore = useMapStore()

const activeTab = ref('chart')
const searchQuery = ref('')

// ==================== ECharts 管理 ====================
const chartRefs: (HTMLElement | null)[] = []
const chartInstances: echarts.ECharts[] = []

function setChartRef(el: HTMLElement | null, idx: number) {
  chartRefs[idx] = el
}

function renderChart(idx: number, retries = 3) {
  const el = chartRefs[idx]
  const entry = resultStore.chartOptions[idx]
  if (!el || !entry) {
    console.warn('[ResultPanel] renderChart: el or entry missing', { el: !!el, entry: !!entry, idx })
    if (retries > 0) setTimeout(() => renderChart(idx, retries - 1), 300)
    return
  }

  // 容器尺寸为零时重试（面板可能还在展开动画中）
  if (el.offsetWidth === 0 || el.offsetHeight === 0) {
    console.warn('[ResultPanel] renderChart: container has zero size, retrying...', idx)
    if (retries > 0) setTimeout(() => renderChart(idx, retries - 1), 300)
    return
  }

  // 如果已有实例先销毁
  if (chartInstances[idx]) {
    chartInstances[idx]!.dispose()
  }

  console.log('[ResultPanel] renderChart:', idx, el.offsetWidth, 'x', el.offsetHeight, entry.option)

  const instance = echarts.init(el, 'dark', { width: el.offsetWidth, height: el.offsetHeight })
  const option = {
    ...entry.option as Record<string, unknown>,
    backgroundColor: 'transparent',
    grid: { left: '10%', right: '5%', top: 40, bottom: 40, containLabel: true },
    tooltip: { trigger: 'axis' as const },
  }
  instance.setOption(option)
  chartInstances[idx] = instance
}

// 监听 chartOptions 变化，新增时渲染
watch(
  () => resultStore.chartOptions.length,
  async (newLen) => {
    if (newLen === 0) return
    await nextTick()
    // 等待面板展开动画完成后再渲染，确保容器有正确尺寸
    setTimeout(() => {
      renderChart(newLen - 1)
      // 再次 resize 兜底（面板可能仍在过渡）
      setTimeout(() => chartInstances[newLen - 1]?.resize(), 300)
    }, 150)
  },
)

function handleResize() {
  chartInstances.forEach(inst => inst?.resize())
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstances.forEach(inst => inst?.dispose())
  chartInstances.length = 0
  chartRefs.length = 0
})

const tabs = computed(() => [
  {
    id: 'chart',
    label: t('result.results'),
    icon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'
  },
  {
    id: 'table',
    label: t('result.layers'),
    icon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/></svg>'
  },
  {
    id: 'report',
    label: t('result.report'),
    icon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>'
  },
])

// 工具结果条形图数据
const resultBars = computed(() => {
  const results = resultStore.latestResults
  if (!results.length) return []
  return results
    .filter(r => r.preview?.featureCount)
    .slice(0, 8)
    .map((r, i) => {
      const colors = ['#3B82F6', '#8B5CF6', '#06B6D4', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#F97316']
      const maxCount = Math.max(...results.map(x => x.preview?.featureCount ?? 0), 1)
      return {
        name: r.summary?.slice(0, 12) || r.toolName,
        value: r.preview?.featureCount ?? 0,
        pct: ((r.preview?.featureCount ?? 0) / maxCount) * 100,
        color: colors[i % colors.length],
      }
    })
})

// 统计概览
const stats = computed(() => resultStore.statistics)

// 图层列表
const layerList = computed(() => mapStore.layers)

// 轨迹播放状态
const trajectoryPlaying = ref<Record<string, boolean>>({})

function toggleTrajectoryPlay(layer: any) {
  const trajId = layer.id.replace('trajectory_', '')
  const playing = mapStore.toggleTrajectory(trajId)
  trajectoryPlaying.value[layer.id] = playing
}

// 轨迹图层添加时默认标记为播放中
watch(layerList, (layers) => {
  for (const l of layers) {
    if (l.type === t('result.trajectory') && !(l.id in trajectoryPlaying.value)) {
      trajectoryPlaying.value[l.id] = true
    }
  }
}, { deep: true, immediate: true })

// 报告内容
const reportHtml = computed(() => {
  if (resultStore.report) {
    return md.render(resultStore.report.content)
  }
  // 无报告时自动生成简要汇总
  if (!resultStore.toolResults.length) return ''
  const lines = [`## ${t('result.analysisSummary')}\n`]
  lines.push(`- **${t('result.toolCalls')}**: ${stats.value.total} (${t('common.success')} ${stats.value.success}, ${t('common.failed')} ${stats.value.failed})`)
  lines.push(`- **${t('result.dataFeatures')}**: ${stats.value.totalFeatures}`)
  lines.push(`\n### ${t('result.executionLog')}\n`)
  resultStore.latestResults.forEach((r, i) => {
    const icon = r.success ? '✅' : '❌'
    lines.push(`${i + 1}. ${icon} **${r.toolName}** — ${r.summary}`)
  })
  return md.render(lines.join('\n'))
})

const hasResults = computed(() => resultStore.toolResults.length > 0)

function copyReport() {
  const text = resultStore.report?.content ??
    resultStore.latestResults.map(r => `${r.toolName}: ${r.summary}`).join('\n')
  navigator.clipboard.writeText(text)
}

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

async function exportLayerData(refId: string, format: 'geojson' | 'csv') {
  try {
    const url = `${API_BASE}/data/${refId}/export?format=${format}`
    const resp = await fetch(url)
    if (!resp.ok) throw new Error(`${t('result.exportFailed')}: ${resp.status}`)
    const blob = await resp.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = `${refId}.${format === 'geojson' ? 'geojson' : 'csv'}`
    a.click()
    URL.revokeObjectURL(blobUrl)
  } catch (e) {
    console.error('[exportLayerData]', e)
    alert(`${t('result.exportFailed')}: ${e}`)
  }
}

function downloadReport() {
  const text = resultStore.report?.content ??
    resultStore.latestResults.map(r => `${r.toolName}: ${r.summary}`).join('\n')
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const ts = new Date().toISOString().slice(0, 16).replace(/[T:]/g, '-')
  a.download = `GeoAgent-report-${ts}.md`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.result-panel {
  flex: 1;
  min-height: 0;
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  padding: 0 8px;
  flex-shrink: 0;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--text-secondary);
}

.tab-btn.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
}

/* Chart view */
.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.chart-actions {
  display: flex;
  gap: 4px;
}

.sm-btn {
  padding: 4px 8px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s;
}

.sm-btn:hover {
  color: var(--text-primary);
  border-color: var(--text-muted);
}

.sm-btn.danger:hover {
  color: var(--error, #ef4444);
  border-color: var(--error, #ef4444);
  background: rgba(239, 68, 68, 0.1);
}

.sm-btn.active {
  color: var(--accent, #3B82F6);
  border-color: var(--accent, #3B82F6);
  background: rgba(59, 130, 246, 0.15);
}

.mock-chart {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bar-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.bar-label {
  font-size: 11px;
  color: var(--text-secondary);
  width: 60px;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bar-track {
  flex: 1;
  height: 14px;
  background: var(--bg-primary);
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 1s ease;
  animation: barGrow 1s ease forwards;
}

@keyframes barGrow {
  from { width: 0 !important; }
}

.bar-value {
  font-size: 12px;
  color: var(--text-muted);
  width: 24px;
}

/* Stats row */
.stats-row {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}

.stat-card {
  flex: 1;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.stat-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-value.success {
  color: var(--success, #10B981);
}

.stat-label {
  font-size: 10px;
  color: var(--text-muted);
}

/* Result list */
.result-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: var(--bg-primary);
  border-radius: 6px;
  border: 1px solid var(--border);
}

.result-item.error {
  border-color: rgba(239, 68, 68, 0.3);
}

.result-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.result-icon.done { color: var(--success, #10B981); }
.result-icon.error { color: var(--error, #EF4444); }

.result-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.result-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  font-family: monospace;
}

.result-summary {
  font-size: 11px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-ref {
  font-size: 10px;
  color: var(--accent);
  background: rgba(59, 130, 246, 0.1);
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
  font-family: monospace;
}

/* Empty state */
.empty-results {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 16px;
  color: var(--text-muted);
  font-size: 13px;
  text-align: center;
}

.empty-results .hint {
  font-size: 11px;
  opacity: 0.7;
}

/* Layer list panel */
.layer-list-panel {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.layer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
}

.layer-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
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
  max-width: 140px;
}

.layer-meta {
  display: flex;
  align-items: center;
  gap: 4px;
}

.layer-type-badge {
  font-size: 10px;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 1px 6px;
  border-radius: 4px;
}

/* Table view (kept for future) */
.table-search:focus {
  border-color: var(--accent);
}

.table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th {
  padding: 8px 10px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-weight: 500;
  text-align: left;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

td {
  padding: 6px 10px;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

tr:hover td {
  background: rgba(59, 130, 246, 0.05);
}

.table-footer {
  padding: 8px 0;
  font-size: 11px;
  color: var(--text-muted);
}

/* Report view */
.report-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
}

.report-content :deep(h2) {
  font-size: 16px;
  margin: 0 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.report-content :deep(h3) {
  font-size: 14px;
  margin: 16px 0 8px;
  color: var(--accent);
}

.report-content :deep(ul), .report-content :deep(ol) {
  padding-left: 18px;
}

.report-content :deep(li) {
  margin-bottom: 4px;
}

.report-content :deep(strong) {
  color: var(--text-primary);
}

.report-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12px;
}

.report-content :deep(table th),
.report-content :deep(table td) {
  padding: 6px 10px;
  border: 1px solid var(--border);
  text-align: left;
}

.report-content :deep(table th) {
  background: var(--bg-tertiary);
  font-weight: 500;
}

/* ECharts section */
.echarts-section {
  margin-top: 16px;
}

.chart-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 1px 7px;
  border-radius: 10px;
}

.echarts-row {
  display: flex;
  gap: 10px;
  overflow-x: auto;
}

.echarts-card {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  flex: 1 1 0;
  min-width: 320px;
}

.echarts-card-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  padding: 8px 12px 0;
}

.echarts-container {
  width: 100%;
  height: 280px;
  min-height: 280px;
}

.report-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  color: var(--text-primary);
  border-color: var(--accent);
}

.action-btn.primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

.action-btn.primary:hover {
  filter: brightness(1.15);
}

/* 报告预览弹框 */
.report-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.report-modal {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  width: 90vw;
  max-width: 800px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.report-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.report-modal-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.report-modal-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.report-modal-close {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  transition: all 0.15s;
}

.report-modal-close:hover {
  color: var(--text-primary);
  background: var(--bg-tertiary);
}

.report-modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
}

.report-modal-body :deep(h1),
.report-modal-body :deep(h2),
.report-modal-body :deep(h3) {
  margin-top: 1.2em;
  margin-bottom: 0.5em;
  color: var(--text-primary);
}

.report-modal-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}

.report-modal-body :deep(th),
.report-modal-body :deep(td) {
  padding: 8px 12px;
  border: 1px solid var(--border);
  text-align: left;
}

.report-modal-body :deep(th) {
  background: var(--bg-tertiary);
  font-weight: 600;
}

.report-modal-body :deep(code) {
  background: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.report-modal-body :deep(ul),
.report-modal-body :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}
</style>

