import './assets/main.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import * as Cesium from 'cesium'
import App from './App.vue'
import i18n from './i18n'
import { useChatStore } from './stores/chatStore'
import { useConfigStore } from './stores/configStore'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(i18n)
app.mount('#app')

// 从后端加载运行时配置 + Cesium Token
const configStore = useConfigStore()
configStore.loadConfig().then(() => {
  const token = configStore.cesiumToken || import.meta.env.VITE_CESIUM_TOKEN
  if (token) Cesium.Ion.defaultAccessToken = token
  if (configStore.tiandituToken) {
    ;(window as any).__TIANDITU_TOKEN__ = configStore.tiandituToken
  }
}).catch(() => {
  const token = import.meta.env.VITE_CESIUM_TOKEN
  if (token) Cesium.Ion.defaultAccessToken = token
})

// 从后端加载历史会话
const chatStore = useChatStore()
chatStore.loadSessions()
