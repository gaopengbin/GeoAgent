<template>
  <header class="app-header">
    <div class="header-left">
      <button class="icon-btn" @click="$emit('toggleSidebar')" :title="$t('header.toggleSidebar')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <line x1="9" y1="3" x2="9" y2="21" />
        </svg>
      </button>
      <div class="logo">
        <svg class="logo-icon" width="24" height="24" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="var(--accent)" stroke-width="2"/>
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
          <path d="M2 12h20M12 2c2.5 3 4 6.5 4 10s-1.5 7-4 10c-2.5-3-4-6.5-4-10s1.5-7 4-10z" stroke="var(--accent)" stroke-width="1.5"/>
          <circle cx="12" cy="12" r="3" fill="var(--accent)" opacity="0.3"/>
        </svg>
        <span class="logo-text">GeoAgent</span>
        <span class="logo-badge">AI</span>
      </div>
    </div>
    <div class="header-center">
      <div ref="selectorRef" class="model-selector" @click="showModelMenu = !showModelMenu">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
        <span>{{ currentModel }}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
        <transition name="fade">
          <div v-if="showModelMenu" class="model-menu">
            <div
              v-for="m in models" :key="m.id"
              class="model-item"
              :class="{ active: m.id === currentModel }"
              @click.stop="currentModel = m.id; showModelMenu = false"
            >
              <span class="model-name">{{ m.desc }}</span>
              <span class="model-desc">{{ m.id }}</span>
            </div>
          </div>
        </transition>
      </div>
    </div>
    <div class="header-right">
      <div ref="settingsRef" class="settings-wrap">
        <button class="icon-btn" @click="showSettings = !showSettings" :title="$t('header.settings')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        </button>
        <transition name="fade">
          <div v-if="showSettings" class="settings-panel">
            <div class="settings-title">{{ $t('header.settings') }}</div>
            <div class="settings-item">
              <label class="settings-label">{{ $t('header.language') }}</label>
              <div class="lang-switch">
                <button class="lang-btn" :class="{ active: locale === 'zh-CN' }" @click="switchLocale('zh-CN')">中文</button>
                <button class="lang-btn" :class="{ active: locale === 'en' }" @click="switchLocale('en')">EN</button>
              </div>
            </div>
            <div class="settings-item">
              <label class="settings-label">{{ $t('header.temperature') }}</label>
              <div class="slider-row">
                <input type="range" min="0" max="100" :value="Math.round(temperature * 100)" @input="onTempChange" class="slider">
                <span class="slider-val">{{ temperature.toFixed(2) }}</span>
              </div>
              <span class="settings-hint">{{ $t('header.temperatureHint') }}</span>
            </div>
            <div class="settings-item">
              <label class="settings-label">{{ $t('header.amap') }}</label>
              <span class="status-dot" :class="configStore.amapAvailable ? 'on' : 'off'"></span>
              <span class="settings-hint">{{ configStore.amapAvailable ? $t('header.amapConfigured') : $t('header.amapNotConfigured') }}</span>
            </div>
            <div class="settings-divider"></div>
            <div class="settings-item">
              <label class="settings-label">{{ $t('header.llmConfig') }}</label>
            </div>
            <div class="settings-item">
              <label class="settings-label-sm">{{ $t('header.apiKey') }}</label>
              <input v-model="llmApiKey" type="password" class="settings-input" :placeholder="$t('header.apiKeyPlaceholder')">
            </div>
            <div class="settings-item">
              <label class="settings-label-sm">{{ $t('header.baseUrl') }}</label>
              <input v-model="llmBaseUrl" type="text" class="settings-input" :placeholder="$t('header.baseUrlPlaceholder')">
            </div>
            <div class="settings-item">
              <label class="settings-label-sm">{{ $t('header.modelName') }}</label>
              <input v-model="llmModelName" type="text" class="settings-input" :placeholder="$t('header.modelNamePlaceholder')">
            </div>
            <button class="apply-btn" @click="applyLLMConfig">{{ $t('header.applyConfig') }}</button>
            <span v-if="configAppliedMsg" class="config-applied-msg">{{ configAppliedMsg }}</span>
          </div>
        </transition>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfigStore } from '../stores/configStore'

const { t, locale } = useI18n()

defineEmits(['toggleSidebar'])

const configStore = useConfigStore()
const showModelMenu = ref(false)
const showSettings = ref(false)
const temperature = ref(parseFloat(localStorage.getItem('geoagent_temperature') ?? '0.3'))
const configAppliedMsg = ref('')

const llmApiKey = ref(sessionStorage.getItem('geoagent_llm_api_key') ?? '')
const llmBaseUrl = ref(localStorage.getItem('geoagent_llm_base_url') ?? '')
const llmModelName = ref(localStorage.getItem('geoagent_llm_model') ?? '')

function switchLocale(lang: string) {
  locale.value = lang
  localStorage.setItem('locale', lang)
}

function applyLLMConfig() {
  if (llmApiKey.value) sessionStorage.setItem('geoagent_llm_api_key', llmApiKey.value)
  else sessionStorage.removeItem('geoagent_llm_api_key')
  if (llmBaseUrl.value) localStorage.setItem('geoagent_llm_base_url', llmBaseUrl.value)
  else localStorage.removeItem('geoagent_llm_base_url')
  if (llmModelName.value) localStorage.setItem('geoagent_llm_model', llmModelName.value)
  else localStorage.removeItem('geoagent_llm_model')
  configStore.llmOverride = {
    apiKey: llmApiKey.value || undefined,
    baseUrl: llmBaseUrl.value || undefined,
    model: llmModelName.value || undefined,
  }
  configAppliedMsg.value = t('header.configApplied')
  setTimeout(() => { configAppliedMsg.value = '' }, 2000)
}

function onTempChange(e: Event) {
  const val = parseInt((e.target as HTMLInputElement).value) / 100
  temperature.value = val
  localStorage.setItem('geoagent_temperature', val.toString())
}

const currentModel = computed({
  get: () => configStore.selectedModel,
  set: (v: string) => { configStore.selectedModel = v },
})

const models = computed(() =>
  configStore.availableModels.map(m => ({ id: m.id, desc: m.name }))
)

const selectorRef = ref<HTMLElement>()

const settingsRef = ref<HTMLElement>()

function onClickOutside(e: MouseEvent) {
  if (showModelMenu.value && selectorRef.value && !selectorRef.value.contains(e.target as Node)) {
    showModelMenu.value = false
  }
  if (showSettings.value && settingsRef.value && !settingsRef.value.contains(e.target as Node)) {
    showSettings.value = false
  }
}

onMounted(() => document.addEventListener('click', onClickOutside, true))
onUnmounted(() => document.removeEventListener('click', onClickOutside, true))
</script>

<style scoped>
.app-header {
  height: 48px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  flex-shrink: 0;
  z-index: 100;
}

.header-left, .header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 8px;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent), #818CF8);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 0.5px;
}

.logo-badge {
  font-size: 10px;
  font-weight: 600;
  background: linear-gradient(135deg, var(--accent), #818CF8);
  color: white;
  padding: 1px 6px;
  border-radius: 4px;
  letter-spacing: 1px;
}

.icon-btn {
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

.icon-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.model-selector {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: var(--bg-tertiary);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
  position: relative;
  transition: all 0.2s;
}

.model-selector:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

.model-menu {
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-top: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 4px;
  min-width: 220px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  z-index: 200;
}

.model-item {
  display: flex;
  flex-direction: column;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.model-item:hover {
  background: var(--bg-tertiary);
}

.model-item.active {
  background: rgba(59, 130, 246, 0.15);
}

.model-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.model-desc {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.settings-wrap {
  position: relative;
}

.settings-panel {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 16px;
  min-width: 260px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  z-index: 200;
}

.settings-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.settings-item {
  margin-bottom: 12px;
}

.settings-item:last-child {
  margin-bottom: 0;
}

.settings-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  display: inline-block;
  margin-right: 6px;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.slider {
  flex: 1;
  -webkit-appearance: none;
  height: 4px;
  border-radius: 2px;
  background: var(--bg-tertiary);
  outline: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--accent);
  cursor: pointer;
}

.slider-val {
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  min-width: 32px;
  text-align: right;
}

.settings-hint {
  font-size: 11px;
  color: var(--text-muted);
  display: block;
  margin-top: 2px;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  vertical-align: middle;
}

.status-dot.on {
  background: var(--success, #22c55e);
}

.status-dot.off {
  background: var(--text-muted);
}

.settings-divider {
  height: 1px;
  background: var(--border);
  margin: 8px 0;
}

.lang-switch {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}

.lang-btn {
  padding: 3px 10px;
  font-size: 12px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: none;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.lang-btn.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.settings-label-sm {
  font-size: 11px;
  color: var(--text-muted);
  display: block;
  margin-bottom: 2px;
}

.settings-input {
  width: 100%;
  padding: 5px 8px;
  font-size: 12px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-primary);
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.15s;
}

.settings-input:focus {
  border-color: var(--accent);
}

.apply-btn {
  width: 100%;
  padding: 5px 0;
  margin-top: 4px;
  font-size: 12px;
  font-weight: 500;
  border: none;
  border-radius: 4px;
  background: var(--accent);
  color: white;
  cursor: pointer;
  transition: opacity 0.15s;
}

.apply-btn:hover {
  opacity: 0.85;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.15s;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
