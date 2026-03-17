/**
 * 后端 API 客户端 + SSE 事件流解析
 */

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

// ---------- 通用 fetch ----------

export async function apiPost<T = any>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export async function apiGet<T = any>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
}

// ---------- 文件上传 ----------

export interface UploadResult {
  file_id: string
  filename: string
  type: string
  size: number
  feature_count: number
  geometry_type: string | null
  crs: string
  properties: string[]
  data_ref_id: string | null
}

export async function apiUpload(
  file: File,
  sessionId?: string,
  crs: string = 'EPSG:4326',
  onProgress?: (pct: number) => void,
): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  if (sessionId) form.append('session_id', sessionId)
  form.append('crs', crs)

  const xhr = new XMLHttpRequest()
  return new Promise((resolve, reject) => {
    xhr.open('POST', `${API_BASE}/upload`)
    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText))
      } else {
        reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`))
      }
    }
    xhr.onerror = () => reject(new Error('Upload network error'))
    xhr.send(form)
  })
}

// ---------- SSE 事件流 ----------

export interface SSEEvent {
  event: string
  data: any
}

export type SSECallback = (evt: SSEEvent) => void

/**
 * 发送 chat 请求并以 SSE 流式接收事件
 * 返回 AbortController 供外部取消
 */
export function chatSSE(
  message: string,
  sessionId: string | null,
  options: { model?: string; temperature?: number; api_key?: string; base_url?: string } | null,
  onEvent: SSECallback,
  onError?: (err: Error) => void,
  onDone?: () => void,
): AbortController {
  const controller = new AbortController()

  const body: Record<string, any> = { message }
  if (sessionId) body.session_id = sessionId
  if (options) body.options = options

  fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok || !res.body) {
        throw new Error(`SSE failed: ${res.status} ${res.statusText}`)
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = ''
      let currentData = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            currentData = line.slice(6)
          } else if (line === '' && currentEvent) {
            try {
              const parsed = JSON.parse(currentData)
              onEvent({ event: currentEvent, data: parsed })
            } catch {
              onEvent({ event: currentEvent, data: currentData })
            }
            currentEvent = ''
            currentData = ''
          }
        }
      }
      onDone?.()
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError?.(err)
      }
    })

  return controller
}
