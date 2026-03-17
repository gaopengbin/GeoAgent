import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiGet } from '../api/client'

export interface ModelOption {
  id: string
  name: string
  default?: boolean
}

export interface BasemapOption {
  id: string
  name: string
  color?: string
}

export const useConfigStore = defineStore('config', () => {
  const cesiumToken = ref('')
  const tiandituToken = ref('')
  const maxUploadSize = ref(100 * 1024 * 1024)
  const supportedFormats = ref<string[]>([])
  const availableModels = ref<ModelOption[]>([])
  const availableBasemaps = ref<BasemapOption[]>([])
  const selectedModel = ref('')
  const amapAvailable = ref(false)
  const cesiumRuntimeWsUrl = ref('')
  const loaded = ref(false)

  async function loadConfig() {
    if (loaded.value) return
    try {
      const cfg = await apiGet<{
        cesium_token: string
        tianditu_token: string
        max_upload_size: number
        supported_formats: string[]
        available_models: ModelOption[]
        available_basemaps: BasemapOption[]
        amap_available: boolean
        cesium_runtime_ws_url: string
      }>('/config')
      cesiumToken.value = cfg.cesium_token
      tiandituToken.value = cfg.tianditu_token
      maxUploadSize.value = cfg.max_upload_size
      supportedFormats.value = cfg.supported_formats
      availableModels.value = cfg.available_models
      availableBasemaps.value = cfg.available_basemaps
      const defaultModel = cfg.available_models.find(m => m.default)
      selectedModel.value = defaultModel?.id ?? cfg.available_models[0]?.id ?? ''
      amapAvailable.value = cfg.amap_available ?? false
      cesiumRuntimeWsUrl.value = cfg.cesium_runtime_ws_url ?? ''
      loaded.value = true
    } catch (e) {
      console.warn('加载配置失败:', e)
      loaded.value = true
    }
  }

  return {
    cesiumToken,
    tiandituToken,
    maxUploadSize,
    supportedFormats,
    availableModels,
    availableBasemaps,
    selectedModel,
    amapAvailable,
    cesiumRuntimeWsUrl,
    loaded,
    loadConfig,
  }
})
