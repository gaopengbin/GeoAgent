import { defineStore } from 'pinia'
import { ref, computed, shallowRef } from 'vue'
import { chatSSE, apiGet, apiDelete, type SSEEvent } from '../api/client'
import { useResultStore } from './resultStore'
import { useConfigStore } from './configStore'

export interface ToolCall {
  name: string
  args?: Record<string, any>
  result?: Record<string, any> | null
  status: 'running' | 'done' | 'error'
  statusText: string
  dataRefId?: string | null
  _expanded?: boolean
}

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  thinking?: string
  toolCalls?: ToolCall[]
  _showThinking?: boolean
  timestamp?: number
}

export interface Session {
  id: string
  title: string
  messages: Message[]
  createdAt: string
  updatedAt: string
}

// 地图指令事件（由 mapStore 监听）
export type MapCommandListener = (command: any) => void

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string>('')
  const isStreaming = ref(false)
  const abortController = shallowRef<AbortController | null>(null)

  // 地图指令监听器
  const _mapCommandListeners: MapCommandListener[] = []

  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value)
  )

  const currentMessages = computed(() =>
    currentSession.value?.messages ?? []
  )

  function createSession() {
    const resultStore = useResultStore()
    if (currentSessionId.value) {
      resultStore.saveToStorage(currentSessionId.value)
    }
    _cleanEmptySession(currentSessionId.value)
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
    const session: Session = {
      id,
      title: '新对话',
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    sessions.value.unshift(session)
    currentSessionId.value = id
    resultStore.loadFromStorage(id)
    return session
  }

  function switchSession(id: string) {
    const resultStore = useResultStore()
    if (currentSessionId.value) {
      resultStore.saveToStorage(currentSessionId.value)
    }
    _cleanEmptySession(currentSessionId.value)
    currentSessionId.value = id
    loadSessionMessages(id)
    resultStore.loadFromStorage(id)
  }

  function _cleanEmptySession(oldId: string | null) {
    if (!oldId) return
    const s = sessions.value.find(x => x.id === oldId)
    if (s && s.messages.length === 0 && s.title === '新对话') {
      sessions.value = sessions.value.filter(x => x.id !== oldId)
    }
  }

  function deleteSession(id: string) {
    const idx = sessions.value.findIndex(s => s.id === id)
    if (idx !== -1) {
      sessions.value.splice(idx, 1)
      if (currentSessionId.value === id) {
        currentSessionId.value = sessions.value[0]?.id ?? ''
      }
    }
    apiDelete(`/sessions/${id}`).catch(() => {})
    const resultStore = useResultStore()
    resultStore.removeStorage(id)
  }

  function addMessage(msg: Message): Message {
    if (!currentSession.value) {
      createSession()
    }
    const session = currentSession.value!
    if (!msg.timestamp) msg.timestamp = Date.now()
    session.messages.push(msg)
    session.updatedAt = new Date().toISOString()

    // 自动更新标题
    if (msg.role === 'user' && session.title === '新对话') {
      session.title = msg.content.slice(0, 20) + (msg.content.length > 20 ? '...' : '')
    }

    return session.messages[session.messages.length - 1]!
  }

  /** 添加系统提示消息（本地展示，不发送给 AI） */
  function addSystemMessage(text: string) {
    addMessage({ role: 'system', content: text })
  }

  /** 注册地图指令监听 */
  function onMapCommand(listener: MapCommandListener) {
    _mapCommandListeners.push(listener)
    return () => {
      const idx = _mapCommandListeners.indexOf(listener)
      if (idx !== -1) _mapCommandListeners.splice(idx, 1)
    }
  }

  /** 取消当前正在进行的流式请求 */
  function cancelStream() {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    isStreaming.value = false
  }

  /** 发送消息到后端 Agent，通过 SSE 流式接收结果 */
  function sendMessage(text: string) {
    if (isStreaming.value) return

    // 添加用户消息
    addMessage({ role: 'user', content: text })

    // 准备 AI 消息占位
    const aiMsg = addMessage({
      role: 'assistant',
      content: '',
      toolCalls: [],
      _showThinking: false,
    })

    isStreaming.value = true

    const sessionId = currentSessionId.value || null

    const configStore = useConfigStore()
    const ctrl = chatSSE(
      text,
      sessionId,
      {
        model: configStore.selectedModel || undefined,
        temperature: parseFloat(localStorage.getItem('geoagent_temperature') ?? '0.3'),
      },
      // SSE 事件处理
      (evt: SSEEvent) => {
        switch (evt.event) {
          case 'session': {
            // 后端返回的 session_id，同步到本地
            const backendId = evt.data.session_id
            if (backendId && currentSession.value) {
              const session = currentSession.value
              const oldId = session.id
              if (oldId !== backendId) {
                const rs = useResultStore()
                rs.saveToStorage(oldId)
                session.id = backendId
                currentSessionId.value = backendId
                rs.loadFromStorage(backendId)
                rs.removeStorage(oldId)
              }
            }
            break
          }

          case 'title': {
            const sid = evt.data.session_id
            const s = sessions.value.find(x => x.id === sid)
            if (s) s.title = evt.data.title
            break
          }

          case 'text': {
            aiMsg.content += evt.data.content ?? ''
            break
          }

          case 'thinking': {
            if (!aiMsg.thinking) aiMsg.thinking = ''
            aiMsg.thinking += evt.data.content ?? ''
            break
          }

          case 'tool_call': {
            const tc: ToolCall = {
              name: evt.data.tool_name,
              args: evt.data.tool_args,
              status: 'running',
              statusText: evt.data.description ?? `正在执行 ${evt.data.tool_name}...`,
            }
            if (!aiMsg.toolCalls) aiMsg.toolCalls = []
            aiMsg.toolCalls.push(tc)
            break
          }

          case 'tool_result': {
            if (aiMsg.toolCalls?.length) {
              const tc = [...aiMsg.toolCalls].reverse().find(
                t => t.name === evt.data.tool_name && t.status === 'running'
              )
              if (tc) {
                tc.status = evt.data.success ? 'done' : 'error'
                tc.statusText = evt.data.summary ?? (evt.data.success ? '完成' : '失败')
                tc.dataRefId = evt.data.data_ref_id ?? null
                tc.result = evt.data.result ?? null
              }
            }
            // 同步到 resultStore（snake_case → camelCase）
            const resultStore = useResultStore()
            const rawPreview = evt.data.preview
            const preview = rawPreview ? {
              featureCount: rawPreview.feature_count ?? rawPreview.featureCount,
              geometryType: rawPreview.geometry_type ?? rawPreview.geometryType,
              bbox: rawPreview.bbox,
              sampleProperties: rawPreview.sample_properties ?? rawPreview.sampleProperties,
            } : null
            resultStore.addToolResult({
              step: evt.data.step ?? 0,
              toolName: evt.data.tool_name,
              success: evt.data.success ?? false,
              summary: evt.data.summary ?? '',
              dataRefId: evt.data.data_ref_id ?? null,
              preview,
              timestamp: Date.now(),
            })
            break
          }

          case 'map_command': {
            const cmd = evt.data.command ?? evt.data
            console.log('[chatStore] map_command SSE received, listeners:', _mapCommandListeners.length, cmd)
            _mapCommandListeners.forEach(fn => fn(cmd))
            const resultStore2 = useResultStore()
            resultStore2.addMapCommand({ action: cmd.action, params: cmd.params ?? {}, timestamp: Date.now() })
            break
          }

          case 'chart_option': {
            const chart = evt.data.chart ?? evt.data
            const resultStore = useResultStore()
            resultStore.addChartOption({
              option: chart.option,
              chartType: chart.chart_type ?? 'bar',
              title: chart.title ?? '图表',
              timestamp: Date.now(),
            })
            break
          }

          case 'report': {
            const resultStore = useResultStore()
            resultStore.setReport({
              content: evt.data.content ?? '',
              format: evt.data.format ?? 'markdown',
            })
            break
          }

          case 'error': {
            aiMsg.content += `\n\n⚠️ 错误：${evt.data.message ?? '未知错误'}`
            break
          }

          case 'done': {
            isStreaming.value = false
            abortController.value = null
            const rsDone = useResultStore()
            if (currentSessionId.value) rsDone.saveToStorage(currentSessionId.value)
            break
          }
        }
      },
      // 网络错误
      (err: Error) => {
        aiMsg.content += `\n\n⚠️ 网络错误：${err.message}`
        isStreaming.value = false
        abortController.value = null
      },
      // 流结束
      () => {
        isStreaming.value = false
        abortController.value = null
      },
    )

    abortController.value = ctrl
  }

  async function loadSessions() {
    try {
      const list = await apiGet<Array<{ id: string; title: string; created_at: string; updated_at: string }>>('/sessions')
      sessions.value = list.map(s => ({
        id: s.id,
        title: s.title,
        messages: [],
        createdAt: s.created_at,
        updatedAt: s.updated_at,
      }))
      const first = sessions.value[0]
      if (first && !currentSessionId.value) {
        currentSessionId.value = first.id
        await loadSessionMessages(first.id)
        const resultStore = useResultStore()
        resultStore.loadFromStorage(first.id)
      }
    } catch (e) {
      console.warn('加载会话列表失败:', e)
    }
  }

  async function loadSessionMessages(sessionId: string) {
    const session = sessions.value.find(s => s.id === sessionId)
    if (!session || session.messages.length > 0) return
    try {
      const detail = await apiGet<{ messages: Array<{ role: string; content: string; tool_calls?: any[] }> }>(`/sessions/${sessionId}`)
      session.messages = detail.messages.map(m => {
        const msg: Message = {
          role: m.role as 'user' | 'assistant' | 'system',
          content: m.content,
        }
        if (m.tool_calls?.length) {
          msg.toolCalls = m.tool_calls.map((tc: any) => ({
            name: tc.name ?? '',
            args: tc.args ?? undefined,
            result: tc.result ?? null,
            status: tc.status === 'error' ? 'error' : 'done',
            statusText: tc.statusText ?? '',
            dataRefId: tc.dataRefId ?? null,
          } as ToolCall))
        }
        return msg
      })
    } catch (e) {
      console.warn('加载会话消息失败:', e)
    }
  }

  return {
    sessions,
    currentSessionId,
    currentSession,
    currentMessages,
    isStreaming,
    createSession,
    switchSession,
    deleteSession,
    addMessage,
    addSystemMessage,
    sendMessage,
    cancelStream,
    onMapCommand,
    loadSessions,
    loadSessionMessages,
  }
})
