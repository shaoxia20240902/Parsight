<template>
  <aside class="chat-sidebar">
    <div class="mode-switcher">
      <button
        v-for="mode in chatModes"
        :key="mode.id"
        type="button"
        class="mode-btn"
        :class="{ 'mode-btn--active': activeMode === mode.id }"
        @click="$emit('switch-mode', mode.id)"
      >
        <span
          class="mode-btn__icon"
          :style="{ color: mode.accent, background: mode.accentSoft }"
        >
          <el-icon><component :is="mode.icon" /></el-icon>
        </span>
        <span class="mode-btn__text">
          <span class="mode-btn__label">{{ mode.label }}</span>
          <span class="mode-btn__desc">{{ mode.description }}</span>
        </span>
      </button>
    </div>

    <div class="sessions-section">
      <div class="sessions-head">
        <span class="sessions-title">聊天记录</span>
        <span class="sessions-count">{{ sessions.length }}</span>
      </div>

      <div v-if="sessions.length" class="session-list">
        <button
          v-for="item in sessions"
          :key="item.id"
          type="button"
          class="session-item"
          :class="{ 'session-item--active': activeSessionId === item.id }"
          @click="$emit('select-session', item)"
        >
          <span
            class="session-mode-icon"
            :style="{
              color: getChatMode(item.mode).accent,
              background: getChatMode(item.mode).accentSoft
            }"
            :title="getChatMode(item.mode).label"
          >
            <el-icon><component :is="getChatMode(item.mode).icon" /></el-icon>
          </span>
          <span class="session-body">
            <span class="session-title">{{ item.title }}</span>
            <span class="session-preview">{{ item.preview }}</span>
          </span>
          <span class="session-time">{{ formatSessionTime(item.updatedAt) }}</span>
        </button>
      </div>
      <div v-else class="sessions-empty">
        <p>暂无「{{ currentModeLabel }}」对话</p>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'
import { getChatMode, type ChatModeId } from '../../constants/chatModes'

type ChatSessionItem = {
  id: string
  mode: ChatModeId
  title: string
  preview: string
  updatedAt: string
  fileId?: string
  messages?: { role: string; content: string }[]
}

const props = defineProps<{
  chatModes: Array<{ id: ChatModeId; label: string; description: string; accent: string; accentSoft: string; icon: Component; avatar: string; switchTransition?: boolean }>
  activeMode: ChatModeId
  sessions: ChatSessionItem[]
  activeSessionId: string | null
}>()

defineEmits<{
  'switch-mode': [mode: ChatModeId]
  'select-session': [item: ChatSessionItem]
}>()

const currentModeLabel = computed(() => getChatMode(props.activeMode).label)

function formatSessionTime(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  if (sameDay) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  }
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}
</script>

<style scoped>
.chat-sidebar {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--chat-sidebar);
  border-right: 1px solid var(--chat-border);
  overflow: hidden;
}

.mode-switcher {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 12px;
  border-bottom: 1px solid var(--chat-border);
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  text-align: left;
  font-family: inherit;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.mode-btn:hover {
  background: rgba(255, 255, 255, 0.75);
}

.mode-btn--active {
  background: var(--chat-surface);
  border-color: var(--chat-border);
  box-shadow: 0 1px 3px rgba(28, 25, 23, 0.04);
}

.mode-btn__icon {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  font-size: 16px;
}

.mode-btn__text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mode-btn__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--chat-text);
}

.mode-btn__desc {
  font-size: 11px;
  color: var(--chat-faint);
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sessions-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.sessions-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 8px;
}

.sessions-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--chat-muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.sessions-count {
  font-size: 11px;
  color: var(--chat-faint);
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(28, 25, 23, 0.05);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 10px 12px;
}

.session-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  margin-bottom: 4px;
  text-align: left;
  font-family: inherit;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.session-item:hover {
  background: rgba(255, 255, 255, 0.7);
}

.session-item--active {
  background: var(--chat-surface);
  border-color: var(--chat-border);
}

.session-mode-icon {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 14px;
}

.session-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-preview {
  font-size: 12px;
  color: var(--chat-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-time {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--chat-faint);
}

.sessions-empty {
  padding: 28px 16px;
  text-align: center;
  font-size: 13px;
  color: var(--chat-muted);
}

.sessions-empty p {
  margin: 0;
}
</style>
