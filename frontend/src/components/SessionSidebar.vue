<template>
  <aside class="session-sidebar">
    <div class="sidebar-top">
      <button class="new-session-btn" @click="chatStore.createSession()">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        新对话
      </button>
    </div>
    <div class="session-list">
      <div class="session-group" v-for="group in groupedSessions" :key="group.label">
        <div class="group-label">{{ group.label }}</div>
        <div
          v-for="s in group.sessions" :key="s.id"
          class="session-item"
          :class="{ active: s.id === chatStore.currentSessionId }"
          @click="chatStore.switchSession(s.id)"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="session-icon">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
          <span class="session-title" :title="s.title">{{ s.title }}</span>
          <button class="export-btn" @click.stop="exportSession(s.id, s.title)" title="导出对话">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
            </svg>
          </button>
          <button class="delete-btn" @click.stop="chatStore.deleteSession(s.id)" title="删除">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
    <div class="sidebar-bottom">
      <div class="usage-info">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
        <span>{{ chatStore.sessions.length }} 个对话</span>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '../stores/chatStore'

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'
const chatStore = useChatStore()

function exportSession(id: string, title: string) {
  const url = `${API_BASE}/sessions/${id}/export?format=markdown`
  const a = document.createElement('a')
  a.href = url
  a.download = `${title || id}.md`
  a.click()
}

const groupedSessions = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)

  const groups: { label: string; sessions: typeof chatStore.sessions }[] = [
    { label: '今天', sessions: [] },
    { label: '昨天', sessions: [] },
    { label: '最近7天', sessions: [] },
    { label: '更早', sessions: [] },
  ]

  for (const s of chatStore.sessions) {
    const d = new Date(s.updatedAt)
    if (d >= today) groups[0]!.sessions.push(s)
    else if (d >= yesterday) groups[1]!.sessions.push(s)
    else if (d >= weekAgo) groups[2]!.sessions.push(s)
    else groups[3]!.sessions.push(s)
  }

  return groups.filter(g => g.sessions.length > 0)
})
</script>

<style scoped>
.session-sidebar {
  width: 240px;
  min-width: 240px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-top {
  padding: 12px;
}

.new-session-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.new-session-btn:hover {
  filter: brightness(1.1);
  transform: translateY(-1px);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.group-label {
  font-size: 11px;
  color: var(--text-muted);
  padding: 8px 8px 4px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 2px;
  border-left: 2px solid transparent;
}

.session-item:hover {
  background: var(--bg-tertiary);
}

.session-item.active {
  background: rgba(59, 130, 246, 0.15);
  border-left-color: var(--accent);
}

.session-item.active .session-icon {
  color: var(--accent);
}

.session-icon {
  flex-shrink: 0;
  color: var(--text-muted);
}

.session-title {
  flex: 1;
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-item.active .session-title {
  color: var(--text-primary);
}

.export-btn, .delete-btn {
  opacity: 0;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: all 0.15s;
}

.session-item:hover .export-btn,
.session-item:hover .delete-btn {
  opacity: 1;
}

.export-btn:hover {
  color: var(--accent);
  background: rgba(59, 130, 246, 0.1);
}

.delete-btn:hover {
  color: var(--error);
  background: rgba(239, 68, 68, 0.1);
}

.sidebar-bottom {
  padding: 12px;
  border-top: 1px solid var(--border);
}

.usage-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
}
</style>
