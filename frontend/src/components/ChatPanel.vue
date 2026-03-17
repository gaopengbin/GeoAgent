<template>
  <div class="chat-panel" @dragover.prevent="isDragging = true" @dragleave.self="isDragging = false" @drop.prevent="handleDrop">
    <transition name="fade">
      <div v-if="isDragging" class="drop-overlay">
        <div class="drop-hint">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
          <span>{{ $t('chat.dropToUpload') }}</span>
        </div>
      </div>
    </transition>
    <div class="messages" ref="messagesRef" @scroll="handleMessagesScroll">
      <div v-if="currentMessages.length === 0" class="welcome">
        <div class="welcome-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="var(--accent)" stroke-width="1.5"/>
            <path d="M12 2c2.5 3 4 6.5 4 10s-1.5 7-4 10c-2.5-3-4-6.5-4-10s1.5-7 4-10z" stroke="var(--accent)" stroke-width="1.5"/>
            <path d="M2 12h20" stroke="var(--accent)" stroke-width="1.5"/>
          </svg>
        </div>
        <h3>{{ $t('chat.welcome') }}</h3>
        <p>{{ $t('chat.welcomeDesc') }}</p>
        <div class="quick-actions">
          <button v-for="q in quickActions" :key="q" class="quick-btn" @click="handleQuickAction(q)">
            {{ q }}
          </button>
        </div>
      </div>

      <template v-for="(msg, i) in currentMessages" :key="i">
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="message user-message">
          <div class="user-msg-row">
            <button v-if="!isStreaming" class="resend-btn" @click="startResend(i, msg.content)" :title="$t('chat.editResend')">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <div class="message-content user-bubble">{{ msg.content }}</div>
          </div>
          <span v-if="msg.timestamp" class="msg-time">{{ formatTime(msg.timestamp) }}</span>
        </div>

        <!-- 系统通知消息 -->
        <div v-else-if="msg.role === 'system'" class="message system-message">
          <div class="system-bubble" v-html="renderMarkdown(msg.content)"></div>
        </div>

        <!-- AI 消息 -->
        <div v-else class="message ai-message">
          <div class="ai-avatar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="var(--accent)" stroke-width="1.5"/>
              <path d="M2 12h20" stroke="var(--accent)" stroke-width="1"/>
              <path d="M12 2c2 2.5 3 5.5 3 10s-1 7.5-3 10" stroke="var(--accent)" stroke-width="1"/>
              <path d="M12 2c-2 2.5-3 5.5-3 10s1 7.5 3 10" stroke="var(--accent)" stroke-width="1"/>
            </svg>
          </div>
          <div class="ai-content">
            <!-- 思考过程 -->
            <div v-if="msg.thinking" class="thinking-block" @click="msg._showThinking = !msg._showThinking">
              <div class="thinking-header">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
                </svg>
                <span>{{ $t('chat.thinking') }}</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                  :style="{ transform: msg._showThinking ? 'rotate(180deg)' : '' }">
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              </div>
              <transition name="expand">
                <div v-if="msg._showThinking" class="thinking-content">{{ msg.thinking }}</div>
              </transition>
            </div>

            <!-- 工具调用 -->
            <div v-if="msg.toolCalls?.length" class="tool-calls">
              <div v-for="(tc, j) in msg.toolCalls" :key="j" class="tool-call" :class="tc.status">
                <div class="tool-call-header" @click="tc._expanded = !tc._expanded">
                  <svg v-if="tc.status === 'done'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                  <svg v-else-if="tc.status === 'running'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
                  <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                  <span class="tool-name">{{ tc.name }}</span>
                  <svg v-if="tc.args && Object.keys(tc.args).length" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="expand-icon" :class="{ expanded: tc._expanded }">
                    <polyline points="6 9 12 15 18 9"/>
                  </svg>
                </div>
                <div class="tool-status-row">
                  <div class="tool-status-text">{{ tc.statusText }}</div>
                  <button v-if="tc.status !== 'running'" class="detail-btn" @click.stop="showToolDetail(tc)" :title="$t('chat.viewDetail')">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  </button>
                </div>
                <!-- generate_report 完成后显示预览/下载按钮 -->
                <div v-if="tc.name === 'generate_report' && tc.status === 'done'" class="report-inline-actions">
                  <button class="report-inline-btn primary" @click.stop="previewReport(tc.result)">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                    {{ $t('chat.previewReport') }}
                  </button>
                  <button class="report-inline-btn" @click.stop="downloadReport(tc.result?.content)">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    {{ $t('common.download') }}
                  </button>
                </div>
                <transition name="expand">
                  <div v-if="tc._expanded && tc.args" class="tool-args">
                    <div v-for="(val, key) in tc.args" :key="String(key)" class="tool-arg-item">
                      <span class="arg-key">{{ key }}</span>
                      <span class="arg-val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
                    </div>
                  </div>
                </transition>
              </div>
            </div>

            <!-- 回复内容（剥离 suggestions 标记） -->
            <div v-if="msg.content" class="ai-text" v-html="renderMarkdown(stripSuggestions(msg.content))"></div>

            <!-- 建议操作按钮 -->
            <div v-if="!isStreaming && parseSuggestions(msg.content).length" class="suggestion-buttons">
              <button
                v-for="s in parseSuggestions(msg.content)" :key="s"
                class="suggestion-btn"
                @click="handleQuickAction(s)"
              >{{ s }}</button>
            </div>

            <!-- 消息操作栏 -->
            <div v-if="msg.content && !isStreaming" class="msg-actions">
              <button class="msg-action-btn" :title="$t('common.copy')" @click="copyMessage(msg.content)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                </svg>
              </button>
            </div>

            <!-- 流式输入指示器（集成在最后一条AI消息内） -->
            <div v-if="isStreaming && i === currentMessages.length - 1 && msg.role === 'assistant'" class="typing-indicator">
              <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
            <span v-if="msg.timestamp && !isStreaming" class="msg-time ai-time">{{ formatTime(msg.timestamp) }}</span>
          </div>
        </div>
      </template>
    </div>

    <!-- 回到底部按钮 -->
    <transition name="fade">
      <button v-if="!isNearBottom && currentMessages.length > 0" class="scroll-bottom-btn" @click="scrollToBottom(true)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
    </transition>

    <!-- 输入区域 -->
    <div class="input-area">
      <div class="input-row">
        <button class="attach-btn" :class="{ uploading: uploadProgress > 0 }" :title="$t('chat.uploadFile')" @click="triggerFileInput">
          <svg v-if="!uploadProgress" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
          </svg>
          <span v-else class="upload-progress">{{ uploadProgress }}%</span>
        </button>
        <input
          ref="fileInputRef"
          type="file"
          class="hidden-file-input"
          accept=".geojson,.json,.csv,.xlsx,.xls,.kml,.kmz,.gpx,.zip"
          @change="handleFileSelect"
        />
        <textarea
          ref="inputRef"
          v-model="inputText"
          class="chat-input"
          :placeholder="$t('chat.inputPlaceholder')"
          rows="1"
          @keydown.enter.exact="handleSend"
          @input="autoResize"
        />
        <button
          v-if="isStreaming"
          class="send-btn cancel"
          title="停止生成"
          @click="chatStore.cancelStream()"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="6" y="6" width="12" height="12" rx="2"/>
          </svg>
        </button>
        <button
          v-else
          class="send-btn"
          :class="{ active: inputText.trim() }"
          :disabled="!inputText.trim()"
          @click="handleSend"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
      <div class="input-hint">{{ $t('chat.sendHint') }}</div>
    </div>

    <!-- 工具详情弹窗 -->
    <teleport to="body">
      <transition name="fade">
        <div v-if="toolDetailVisible" class="tool-detail-overlay" @click.self="toolDetailVisible = false">
          <div class="tool-detail-modal">
            <div class="tool-detail-header">
              <span class="tool-detail-title">{{ toolDetailData?.name }}</span>
              <span class="tool-detail-badge" :class="toolDetailData?.status">{{ toolDetailData?.status === 'done' ? $t('chat.done') : $t('common.failed') }}</span>
              <button class="tool-detail-close" @click="toolDetailVisible = false">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div class="tool-detail-body">
              <div class="tool-detail-section">
                <div class="tool-detail-section-title">{{ $t('chat.inputParams') }}</div>
                <pre class="tool-detail-json">{{ formatJson(toolDetailData?.args) }}</pre>
              </div>
              <div class="tool-detail-section">
                <div class="tool-detail-section-title">{{ $t('chat.outputResult') }}</div>
                <pre class="tool-detail-json">{{ formatJson(toolDetailData?.result) }}</pre>
              </div>
            </div>
          </div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useChatStore } from '../stores/chatStore'
import { useResultStore } from '../stores/resultStore'
import { apiUpload } from '../api/client'
import MarkdownIt from 'markdown-it'

const { t } = useI18n()
const chatStore = useChatStore()
const resultStore = useResultStore()
const md = new MarkdownIt({ html: false, linkify: true })

const defaultFence = md.renderer.rules.fence!
md.renderer.rules.fence = (tokens, idx, options, env, self) => {
  const raw = defaultFence(tokens, idx, options, env, self)
  return `<div class="code-block-wrapper"><button class="copy-code-btn" title="Copy">` +
    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">` +
    `<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>` +
    `</button>${raw}</div>`
}

const inputText = ref('')
const inputRef = ref<HTMLTextAreaElement>()
const messagesRef = ref<HTMLDivElement>()
const fileInputRef = ref<HTMLInputElement>()
const uploadProgress = ref(0)
const isDragging = ref(false)

// 工具详情弹窗
const toolDetailVisible = ref(false)
const toolDetailData = ref<{ name: string; status: string; args?: any; result?: any } | null>(null)

function showToolDetail(tc: any) {
  toolDetailData.value = { name: tc.name, status: tc.status, args: tc.args, result: tc.result }
  toolDetailVisible.value = true
}

function formatJson(data: any): string {
  if (!data) return t('common.noData')
  try { return JSON.stringify(data, null, 2) } catch { return String(data) }
}

function previewReport(result: any) {
  if (result?.content) {
    resultStore.setReport({ content: result.content, format: result.format ?? 'markdown' })
  }
  resultStore.showReportModal = true
}

function downloadReport(content?: string) {
  const text = content ?? resultStore.report?.content ?? ''
  if (!text) return
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const ts = new Date().toISOString().slice(0, 16).replace(/[T:]/g, '-')
  a.download = `GeoAgent-report-${ts}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function handleCopyClick(e: MouseEvent) {
  const btn = (e.target as HTMLElement).closest('.copy-code-btn') as HTMLElement | null
  if (!btn) return
  const wrapper = btn.closest('.code-block-wrapper')
  const code = wrapper?.querySelector('code')?.textContent ?? ''
  navigator.clipboard.writeText(code).then(() => {
    btn.classList.add('copied')
    setTimeout(() => btn.classList.remove('copied'), 1500)
  })
}

onMounted(() => document.addEventListener('click', handleCopyClick))
onUnmounted(() => document.removeEventListener('click', handleCopyClick))

function copyMessage(content: string) {
  const plain = content.replace(/<<suggestions:.+?>>/g, '').trim()
  navigator.clipboard.writeText(plain)
}

const currentMessages = computed(() => chatStore.currentMessages)
const isStreaming = computed(() => chatStore.isStreaming)

const quickActions = computed(() => [
  t('chat.quickFlyTo'),
  t('chat.quickPOI'),
  t('chat.quickRoute'),
  t('chat.quickWeather'),
])

function renderMarkdown(text: string) {
  return md.render(text)
}

const SUGGESTIONS_RE = /<<suggestions:(.+?)>>/g

function parseSuggestions(text: string): string[] {
  if (!text) return []
  const match = SUGGESTIONS_RE.exec(text)
  SUGGESTIONS_RE.lastIndex = 0
  if (!match?.[1]) return []
  return match[1].split('|').map(s => s.trim()).filter(Boolean)
}

function stripSuggestions(text: string): string {
  return text.replace(SUGGESTIONS_RE, '').trimEnd()
}

function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function handleSend(e?: Event) {
  if (e instanceof KeyboardEvent && e.shiftKey) return
  e?.preventDefault()
  const text = inputText.value.trim()
  if (!text || isStreaming.value) return
  inputText.value = ''
  if (inputRef.value) inputRef.value.style.height = 'auto'
  chatStore.sendMessage(text)
  scrollToBottom(true)
}

function handleQuickAction(text: string) {
  if (isStreaming.value) return
  chatStore.sendMessage(text)
  scrollToBottom(true)
}

function startResend(_msgIndex: number, content: string) {
  inputText.value = content
  nextTick(() => {
    if (inputRef.value) {
      inputRef.value.focus()
      inputRef.value.style.height = 'auto'
      inputRef.value.style.height = Math.min(inputRef.value.scrollHeight, 120) + 'px'
    }
  })
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

async function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''
  await uploadFile(file)
}

function handleDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file) uploadFile(file)
}

async function uploadFile(file: File) {
  uploadProgress.value = 1
  try {
    const result = await apiUpload(
      file,
      chatStore.currentSessionId ?? undefined,
      'EPSG:4326',
      (pct) => { uploadProgress.value = pct },
    )
    uploadProgress.value = 0
    const lines = [`📎 ${t('chat.fileUploaded')}：**${result.filename}**`]
    if (result.data_ref_id) {
      lines.push(`- ${t('chat.dataRef')}: \`${result.data_ref_id}\``)
      lines.push(`- 要素数: ${result.feature_count}　类型: ${result.geometry_type ?? '未知'}　坐标系: ${result.crs}`)
      lines.push('')
      lines.push(t('chat.dataAutoRegistered'))
    } else {
      lines.push(`- file_id: \`${result.file_id}\``)
      lines.push('')
      lines.push(t('chat.dataManualLoad'))
    }
    chatStore.addSystemMessage(lines.join('\n'))
    scrollToBottom()
  } catch (err: any) {
    uploadProgress.value = 0
    console.error('Upload failed:', err)
    chatStore.addSystemMessage(`${t('chat.uploadFailed')}: ${err.message}`)
  }
}

const isNearBottom = ref(true)

function scrollToBottom(force = false) {
  nextTick(() => {
    const el = messagesRef.value
    if (!el) return
    if (force || isNearBottom.value) {
      el.scrollTop = el.scrollHeight
    }
  })
}

function handleMessagesScroll() {
  const el = messagesRef.value
  if (!el) return
  isNearBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 80
}

watch(currentMessages, () => {
  // 流式输出期间始终强制滚动到底部
  scrollToBottom(isStreaming.value)
}, { deep: true })

watch(isStreaming, (streaming, wasStreaming) => {
  // 流式结束后强制滚到底部一次
  if (!streaming && wasStreaming) scrollToBottom(true)
})

watch(() => chatStore.currentSessionId, () => {
  nextTick(() => inputRef.value?.focus())
})
</script>

<style scoped>
.chat-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  position: relative;
}

.drop-overlay {
  position: absolute;
  inset: 0;
  z-index: 100;
  background: rgba(59, 130, 246, 0.08);
  border: 2px dashed var(--accent);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.drop-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--accent);
  font-size: 14px;
  font-weight: 500;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

/* Welcome */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  gap: 12px;
  animation: fadeIn 0.5s ease;
}

.welcome-icon {
  opacity: 0.6;
}

.welcome h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.welcome p {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
  max-width: 320px;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 8px;
  max-width: 480px;
}

.quick-btn {
  padding: 6px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 16px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-btn:hover {
  background: rgba(59, 130, 246, 0.1);
  border-color: var(--accent);
  color: var(--accent);
}

/* Messages */
.message {
  margin-bottom: 16px;
  animation: fadeIn 0.3s ease;
}

/* System message */
.system-message {
  display: flex;
  justify-content: center;
}

.system-bubble {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 16px;
  max-width: 85%;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.system-bubble :deep(p) {
  margin: 0 0 4px;
}

.system-bubble :deep(ul) {
  padding-left: 16px;
  margin: 2px 0;
}

.system-bubble :deep(code) {
  background: var(--bg-tertiary);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
}

/* Suggestion buttons */
.suggestion-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.suggestion-btn {
  padding: 5px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 14px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion-btn:hover {
  background: rgba(59, 130, 246, 0.1);
  border-color: var(--accent);
  color: var(--accent);
}

.user-message {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.user-msg-row {
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: flex-end;
}

.resend-btn {
  opacity: 0;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: all 0.15s;
  flex-shrink: 0;
}

.user-message:hover .resend-btn {
  opacity: 1;
}

.resend-btn:hover {
  color: var(--accent);
  background: rgba(59, 130, 246, 0.1);
}

.user-bubble {
  background: var(--accent);
  color: white;
  padding: 8px 14px;
  border-radius: 16px 16px 4px 16px;
  max-width: 70%;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.msg-time {
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0;
  transition: opacity 0.2s;
}

.user-message:hover .msg-time,
.ai-message:hover .msg-time {
  opacity: 1;
}

.user-message .msg-time {
  text-align: right;
  display: block;
  margin-top: 2px;
}

.ai-time {
  margin-top: 2px;
}

.ai-message {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.ai-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--border);
}

.ai-content {
  flex: 1;
  min-width: 0;
}

/* 思考过程 */
.thinking-block {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.thinking-block:hover {
  background: var(--bg-tertiary);
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.thinking-header svg:last-child {
  margin-left: auto;
  transition: transform 0.2s;
}

.thinking-content {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--border);
  line-height: 1.5;
}

/* 工具调用 */
.tool-calls {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}

.tool-call {
  border-radius: 8px;
  padding: 6px 10px;
  background: var(--bg-secondary);
  border-left: 3px solid var(--text-muted);
  transition: all 0.2s;
}

.tool-call.done {
  border-left-color: var(--success);
}

.tool-call.running {
  border-left-color: var(--accent);
}

.tool-call.error {
  border-left-color: var(--error);
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
}

.tool-call.done .tool-call-header { color: var(--success); }
.tool-call.running .tool-call-header { color: var(--accent); }
.tool-call.error .tool-call-header { color: var(--error); }

.tool-name {
  font-size: 12px;
  font-weight: 600;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
}

.tool-status-row {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  margin-top: 2px;
  padding-left: 18px;
}

.tool-status-text {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  flex: 1;
}

.detail-btn {
  flex-shrink: 0;
  background: none;
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 2px 4px;
  cursor: pointer;
  color: var(--text-muted);
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}

.tool-call:hover .detail-btn {
  opacity: 1;
}

.detail-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}

.expand-icon {
  margin-left: auto;
  transition: transform 0.2s;
  opacity: 0.5;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.tool-call-header {
  cursor: pointer;
}

.tool-args {
  margin-top: 4px;
  padding: 6px 8px 6px 18px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 4px;
  font-size: 11px;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
}

.tool-arg-item {
  display: flex;
  gap: 6px;
  line-height: 1.6;
}

.arg-key {
  color: var(--accent);
  flex-shrink: 0;
}

.arg-key::after {
  content: ':';
}

.arg-val {
  color: var(--text-secondary);
  word-break: break-all;
}

.msg-actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}

.ai-message:hover .msg-actions {
  opacity: 1;
}

.msg-action-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 3px 6px;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  transition: all 0.15s;
}

.msg-action-btn:hover {
  color: var(--text-primary);
  background: var(--bg-tertiary);
}

/* AI 文本 */
.ai-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
}

.ai-text :deep(p) {
  margin: 0 0 8px;
}

.ai-text :deep(strong) {
  color: var(--text-primary);
  font-weight: 600;
}

.ai-text :deep(blockquote) {
  border-left: 3px solid var(--accent);
  padding-left: 12px;
  margin: 8px 0;
  color: var(--text-secondary);
}

.ai-text :deep(code) {
  background: var(--bg-secondary);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
}

.ai-text :deep(ul), .ai-text :deep(ol) {
  padding-left: 20px;
  margin: 4px 0;
}

.ai-text :deep(pre) {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  margin: 8px 0;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
}

.ai-text :deep(pre code) {
  background: none;
  padding: 0;
}

.ai-text :deep(.code-block-wrapper) {
  position: relative;
}

.ai-text :deep(.copy-code-btn) {
  position: absolute;
  top: 6px;
  right: 6px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 4px;
  cursor: pointer;
  color: var(--text-muted);
  opacity: 0;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  z-index: 2;
}

.ai-text :deep(.code-block-wrapper:hover .copy-code-btn) {
  opacity: 1;
}

.ai-text :deep(.copy-code-btn:hover) {
  color: var(--text-primary);
  background: var(--bg-secondary);
}

.ai-text :deep(.copy-code-btn.copied) {
  opacity: 1;
  color: var(--success, #22c55e);
}

.ai-text :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12px;
  display: block;
  overflow-x: auto;
  border-radius: 6px;
  border: 1px solid var(--border);
}

.ai-text :deep(th), .ai-text :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
  white-space: nowrap;
}

.ai-text :deep(th) {
  background: var(--bg-tertiary);
  font-weight: 600;
  position: sticky;
  top: 0;
}

.ai-text :deep(tr:nth-child(even)) {
  background: rgba(255, 255, 255, 0.02);
}

.ai-text :deep(tr:hover td) {
  background: rgba(59, 130, 246, 0.05);
}

.ai-text :deep(h1), .ai-text :deep(h2), .ai-text :deep(h3), .ai-text :deep(h4) {
  color: var(--text-primary);
  margin: 12px 0 6px;
  line-height: 1.3;
}

.ai-text :deep(h1) { font-size: 16px; }
.ai-text :deep(h2) { font-size: 14px; }
.ai-text :deep(h3) { font-size: 13px; }

.ai-text :deep(a) {
  color: var(--accent);
  text-decoration: none;
}

.ai-text :deep(a:hover) {
  text-decoration: underline;
}

.ai-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 10px 0;
}

/* Typing indicator */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 0;
  width: fit-content;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  opacity: 0.4;
  animation: typing-dot 1.4s ease-in-out infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-dot {
  0%, 60%, 100% { opacity: 0.4; transform: scale(1); }
  30% { opacity: 1; transform: scale(1.3); }
}

.scroll-bottom-btn {
  position: absolute;
  bottom: 90px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: 50%;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-muted);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  transition: all 0.2s;
  z-index: 10;
}

.scroll-bottom-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}

/* Input */
.input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-secondary);
}

.input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 8px 12px;
  transition: border-color 0.2s;
}

.input-row:focus-within {
  border-color: var(--accent);
}

.chat-input {
  flex: 1;
  border: none;
  background: none;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  outline: none;
  font-family: inherit;
  max-height: 120px;
  min-height: 20px;
  padding: 2px 0;
  margin: 0;
}

.chat-input::placeholder {
  color: var(--text-muted);
}

.attach-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  transition: all 0.2s;
}

.attach-btn:hover {
  color: var(--accent);
  background: rgba(59, 130, 246, 0.1);
}

.attach-btn.uploading {
  color: var(--accent);
}

.upload-progress {
  font-size: 10px;
  font-weight: 600;
  min-width: 28px;
  text-align: center;
}

.hidden-file-input {
  display: none;
}

.send-btn {
  background: var(--bg-tertiary);
  border: none;
  color: var(--text-muted);
  width: 32px;
  height: 32px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.send-btn.active {
  background: var(--accent);
  color: white;
}

.send-btn.cancel {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.send-btn.cancel:hover {
  background: rgba(239, 68, 68, 0.25);
}

.send-btn:disabled {
  cursor: default;
}

.input-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
  opacity: 0.7;
}

/* Animations */
@keyframes spin {
  100% { transform: rotate(360deg); }
}

.spin {
  animation: spin 1s linear infinite;
}

.expand-enter-active, .expand-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.expand-enter-from, .expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.expand-enter-to, .expand-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>

<style>
/* 工具详情弹窗（teleport 到 body，不能 scoped） */
.tool-detail-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(2px);
}

.tool-detail-modal {
  background: var(--bg-primary, #1a1a2e);
  border: 1px solid var(--border, #333);
  border-radius: 12px;
  width: min(600px, 90vw);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.tool-detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border, #333);
}

.tool-detail-title {
  font-size: 14px;
  font-weight: 600;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  color: var(--text-primary, #e0e0e0);
}

.tool-detail-badge {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.tool-detail-badge.done {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.tool-detail-badge.error {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.tool-detail-close {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--text-muted, #888);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.tool-detail-close:hover {
  color: var(--text-primary, #e0e0e0);
  background: var(--bg-tertiary, #2a2a3e);
}

.tool-detail-body {
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tool-detail-section-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted, #888);
  margin-bottom: 6px;
}

.tool-detail-json {
  font-size: 12px;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  background: var(--bg-secondary, #141422);
  border: 1px solid var(--border, #333);
  border-radius: 6px;
  padding: 10px 12px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-secondary, #bbb);
  max-height: 300px;
  overflow-y: auto;
  line-height: 1.5;
}

/* 报告内联操作按钮 */
.report-inline-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--border, #333);
}

.report-inline-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--bg-tertiary, #1a1a2e);
  border: 1px solid var(--border, #333);
  border-radius: 5px;
  color: var(--text-secondary, #bbb);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}

.report-inline-btn:hover {
  color: var(--text-primary, #fff);
  border-color: var(--accent, #60a5fa);
}

.report-inline-btn.primary {
  background: var(--accent, #60a5fa);
  color: #fff;
  border-color: var(--accent, #60a5fa);
}

.report-inline-btn.primary:hover {
  filter: brightness(1.15);
}
</style>
