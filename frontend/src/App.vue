<template>
  <div class="app" :class="{ 'sidebar-collapsed': !showSidebar, 'mobile': isMobile, 'mobile-chat': isMobile && mobileView === 'chat' }">
    <AppHeader
      :show-sidebar="showSidebar"
      @toggle-sidebar="showSidebar = !showSidebar"
    />
    <div class="app-body">
      <transition name="slide-left">
        <SessionSidebar v-show="showSidebar && !isMobile" />
      </transition>
      <div class="center-area" v-show="!isMobile || mobileView === 'map'">
        <div class="map-region">
          <MapView />
        </div>
        <!-- 底部面板打开按钮 -->
        <button
          v-if="!showBottomPanel"
          class="bottom-panel-toggle"
          @click="showBottomPanel = true"
          title="打开分析面板"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>
          <span>分析结果</span>
        </button>
        <!-- 底部结果面板 -->
        <div
          v-show="showBottomPanel"
          class="bottom-panel"
          :style="{ height: bottomHeight + 'px' }"
        >
          <div class="resize-handle-row" @mousedown="startResizeBottom">
            <div class="handle-grip"></div>
          </div>
          <div class="bottom-header">
            <span class="bottom-title">分析结果</span>
            <button class="bottom-close" @click="showBottomPanel = false">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>
          </div>
          <ResultPanel />
        </div>
      </div>
      <div
        v-if="!isMobile"
        class="resize-handle-col"
        @mousedown="startResizeCol"
      ></div>
      <div class="right-panel" :class="{ 'mobile-panel': isMobile }" v-show="!isMobile || mobileView === 'chat'" :style="!isMobile ? { width: chatWidth + 'px' } : {}">
        <ChatPanel />
      </div>
    </div>
    <!-- 移动端底部导航 -->
    <div v-if="isMobile" class="mobile-nav">
      <button :class="{ active: mobileView === 'map' }" @click="mobileView = 'map'">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2c2.5 3 4 6.5 4 10s-1.5 7-4 10c-2.5-3-4-6.5-4-10s1.5-7 4-10z"/></svg>
        <span>地图</span>
      </button>
      <button :class="{ active: mobileView === 'chat' }" @click="mobileView = 'chat'">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
        <span>对话</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import AppHeader from './components/AppHeader.vue'
import SessionSidebar from './components/SessionSidebar.vue'
import MapView from './components/MapView.vue'
import ChatPanel from './components/ChatPanel.vue'
import ResultPanel from './components/ResultPanel.vue'
import { useResultStore } from './stores/resultStore'
import { useChatStore } from './stores/chatStore'

const chatStore = useChatStore()
const showSidebar = ref(true)
const chatWidth = ref(420)
const showBottomPanel = ref(false)
const bottomHeight = ref(200)
const isMobile = ref(false)
const mobileView = ref<'map' | 'chat'>('map')

function checkMobile() {
  isMobile.value = window.innerWidth < 768
  if (isMobile.value) showSidebar.value = false
}

function handleKeyboard(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    chatStore.createSession()
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
    e.preventDefault()
    showSidebar.value = !showSidebar.value
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  window.addEventListener('keydown', handleKeyboard)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  window.removeEventListener('keydown', handleKeyboard)
})

const resultStore = useResultStore()

// 新图表或新工具结果到达 → 自动展开底部面板
watch(() => resultStore.chartOptions.length, (n, o) => {
  if (n > o) showBottomPanel.value = true
})
watch(() => resultStore.toolResults.length, (n, o) => {
  if (n > o) showBottomPanel.value = true
})

// ==================== 列宽拖拽 ====================
let startX = 0
let startWidth = 0

function startResizeCol(e: MouseEvent) {
  startX = e.clientX
  startWidth = chatWidth.value
  document.addEventListener('mousemove', onResizeCol)
  document.addEventListener('mouseup', stopResizeCol)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onResizeCol(e: MouseEvent) {
  const delta = startX - e.clientX
  chatWidth.value = Math.min(700, Math.max(300, startWidth + delta))
}

function stopResizeCol() {
  document.removeEventListener('mousemove', onResizeCol)
  document.removeEventListener('mouseup', stopResizeCol)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// ==================== 底部高度拖拽 ====================
let startY = 0
let startHeight = 0

function startResizeBottom(e: MouseEvent) {
  startY = e.clientY
  startHeight = bottomHeight.value
  document.addEventListener('mousemove', onResizeBottom)
  document.addEventListener('mouseup', stopResizeBottom)
  document.body.style.cursor = 'row-resize'
  document.body.style.userSelect = 'none'
}

function onResizeBottom(e: MouseEvent) {
  const delta = startY - e.clientY
  bottomHeight.value = Math.min(600, Math.max(150, startHeight + delta))
}

function stopResizeBottom() {
  document.removeEventListener('mousemove', onResizeBottom)
  document.removeEventListener('mouseup', stopResizeBottom)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}
</script>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.app-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.center-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.map-region {
  flex: 1;
  min-height: 0;
  position: relative;
  overflow: hidden;
}

/* Bottom panel */
.bottom-panel {
  flex-shrink: 0;
  border-top: 1px solid var(--border);
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.resize-handle-row {
  height: 6px;
  cursor: row-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.resize-handle-row:hover .handle-grip {
  background: var(--accent);
}

.handle-grip {
  width: 40px;
  height: 3px;
  border-radius: 2px;
  background: var(--border);
  transition: background 0.2s;
}

.bottom-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px 6px;
  flex-shrink: 0;
}

.bottom-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.bottom-close {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  display: flex;
  transition: all 0.15s;
}

.bottom-close:hover {
  color: var(--text-primary);
  background: var(--bg-tertiary);
}

/* Bottom panel toggle button */
.bottom-panel-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  height: 28px;
  background: var(--bg-secondary);
  border: none;
  border-top: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}

.bottom-panel-toggle:hover {
  color: var(--accent);
  background: var(--bg-tertiary);
}

/* Right panel (chat only) */
.right-panel {
  flex-shrink: 0;
  overflow: hidden;
  border-left: 1px solid var(--border);
}

.resize-handle-col {
  width: 4px;
  cursor: col-resize;
  background: transparent;
  flex-shrink: 0;
  transition: background 0.2s;
}

.resize-handle-col:hover {
  background: var(--accent);
}

/* Transitions */
.slide-left-enter-active,
.slide-left-leave-active {
  transition: all 0.3s ease;
}
.slide-left-enter-from,
.slide-left-leave-to {
  transform: translateX(-100%);
  opacity: 0;
  width: 0 !important;
  min-width: 0 !important;
  padding: 0 !important;
}

/* Mobile */
.mobile-nav {
  display: flex;
  height: 52px;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.mobile-nav button {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  transition: color 0.2s;
}

.mobile-nav button.active {
  color: var(--accent);
}

.mobile-panel {
  width: 100% !important;
  border-left: none !important;
}
</style>
