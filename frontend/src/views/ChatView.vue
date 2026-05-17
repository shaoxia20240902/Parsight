<template>
  <div class="chat-view">
    <aside class="chat-sidebar">
      <div class="mode-switcher">
        <button
          v-for="mode in chatModes"
          :key="mode.id"
          type="button"
          class="mode-btn"
          :class="{ 'mode-btn--active': activeMode === mode.id }"
          @click="switchMode(mode.id)"
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
          <span class="sessions-count">{{ filteredSessions.length }}</span>
        </div>

        <div v-if="filteredSessions.length" class="session-list">
          <button
            v-for="item in filteredSessions"
            :key="item.id"
            type="button"
            class="session-item"
            :class="{ 'session-item--active': activeSessionId === item.id }"
            @click="selectSession(item)"
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
          <p>暂无「{{ currentModeConfig.label }}」对话</p>
        </div>
      </div>
    </aside>

    <main class="chat-main">
      <div class="chat-panel">
        <div
          class="chat-messages"
          :class="{ 'chat-messages--welcome': messages.length === 0 }"
          ref="chatRef"
        >
          <div v-if="messages.length === 0" class="chat-welcome">
            <div class="welcome-stage">
              <div class="welcome-hero-layer" aria-hidden="true">
                <img
                  v-for="mode in chatModes"
                  :key="mode.id"
                  :src="mode.avatar"
                  :alt="mode.label"
                  class="welcome-hero"
                  :class="{ 'welcome-hero--visible': contentMode === mode.id }"
                  decoding="async"
                />
              </div>

              <div class="welcome-content" :class="{ 'welcome-content--fading': contentFading }">
                  <h2 class="welcome-title">{{ displayModeConfig.welcomeTitle }}</h2>
                  <p class="welcome-desc">{{ displayModeConfig.description }}</p>

                <!-- 洞察：3 组 × 3 问题 -->
                <div
                  v-show="contentMode === 'insight'"
                  class="prompt-layout prompt-layout--grid"
                >
                  <div
                    v-for="group in insightGroups"
                    :key="group.title"
                    class="prompt-card"
                  >
                    <h3 class="prompt-card__title">{{ group.title }}</h3>
                    <div class="prompt-card__list">
                      <button
                        v-for="(q, qi) in group.questions"
                        :key="qi"
                        type="button"
                        class="prompt-chip"
                        @click="onPromptClick(q)"
                      >
                        {{ q }}
                      </button>
                    </div>
                  </div>
                </div>

                <!-- 深度洞察 -->
                <div v-show="contentMode === 'deep'" class="prompt-layout">
                  <div class="prompt-card prompt-card--single">
                    <h3 class="prompt-card__title">推荐深度分析问题</h3>
                    <div class="prompt-card__list">
                      <button
                        v-for="(q, i) in deepPrompts"
                        :key="i"
                        type="button"
                        class="prompt-chip prompt-chip--long"
                        @click="onPromptClick(q)"
                      >
                        {{ q }}
                      </button>
                    </div>
                  </div>
                </div>

                <!-- 构建者 -->
                <div v-show="contentMode === 'builder'" class="prompt-layout">
                  <div class="prompt-card prompt-card--single">
                    <h3 class="prompt-card__title">描述你想创建的图表</h3>
                    <div class="prompt-card__list">
                      <button
                        v-for="(q, i) in builderPrompts"
                        :key="i"
                        type="button"
                        class="prompt-chip prompt-chip--long"
                        @click="onPromptClick(q)"
                      >
                        {{ q }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <TransitionGroup v-else name="msg" tag="div" class="msg-list">
            <div
              v-for="(msg, i) in messages"
              :key="i"
              :class="['message', msg.role]"
            >
              <div class="message-avatar">{{ msg.role === 'user' ? '我' : '析' }}</div>
              <div class="message-bubble">
                <div class="message-content">{{ msg.content }}</div>
                <div v-if="msg.blocks?.length" class="builder-blocks">
                  <template v-for="(block, bi) in msg.blocks" :key="bi">
                    <div v-if="block.type === 'markdown'" class="builder-markdown" v-html="renderMarkdown(block.content)" />

                    <div v-else-if="block.type === 'data_table'" class="builder-card builder-card--preview">
                      <div class="builder-card__title">{{ block.title || '查询结果' }}</div>
                      <div v-if="block.rows?.length" class="preview-table-wrap">
                        <table class="preview-table">
                          <thead>
                            <tr>
                              <th v-for="col in block.columns" :key="col">{{ col }}</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="(row, ri) in block.rows.slice(0, 8)" :key="ri">
                              <td v-for="col in block.columns" :key="col">{{ row[col] }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <div v-else class="builder-card__meta">暂无可展示数据。</div>
                    </div>

                    <div v-else-if="block.type === 'chart_summary'" class="builder-card">
                      <div class="builder-card__title">{{ block.title }}</div>
                      <div class="builder-card__meta">
                        {{ block.category_name || block.category_id || '未分类' }} · {{ block.chart_type || 'chart' }}
                      </div>
                      <div v-if="block.reason" class="builder-card__reason">{{ block.reason }}</div>
                    </div>

                    <div v-else-if="block.type === 'chart_preview'" class="builder-card builder-card--preview">
                      <div class="builder-card__title">图表预览</div>
                      <div v-if="block.preview?.rows?.length" class="preview-table-wrap">
                        <table class="preview-table">
                          <thead>
                            <tr>
                              <th v-for="col in block.preview.columns" :key="col">{{ col }}</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="(row, ri) in block.preview.rows.slice(0, 5)" :key="ri">
                              <td v-for="col in block.preview.columns" :key="col">{{ row[col] }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <div v-else class="builder-card__meta">可点击“去查看”在 BI 页面查看完整图表。</div>
                    </div>

                    <div v-else-if="block.type === 'questionnaire'" class="builder-card">
                      <div class="builder-card__title">必填信息</div>
                      <label v-for="q in block.questions" :key="q.field" class="builder-field">
                        <span>{{ q.label }}</span>
                        <select v-model="formValues[q.field]">
                          <option value="">请选择</option>
                          <option v-for="opt in q.options" :key="optionValue(opt)" :value="optionValue(opt)">
                            {{ optionLabel(opt) }}
                          </option>
                        </select>
                      </label>
                      <button type="button" class="builder-action builder-action--primary" @click="submitQuestionnaire(block)">
                        {{ block.submit_label || '确认并继续' }}
                      </button>
                    </div>

                    <details v-else-if="block.type === 'advanced_panel'" class="builder-card builder-details">
                      <summary>高级设置</summary>
                      <div class="builder-card__meta">可选项，默认可跳过。</div>
                    </details>

                    <div v-else-if="block.type === 'analysis_directions'" class="builder-card">
                      <div class="builder-card__title">推荐分析方向</div>
                      <button
                        v-for="item in block.items"
                        :key="item.title"
                        type="button"
                        class="builder-action"
                        @click="sendBuilderMessage(item.prompt, { type: 'user_message', payload: { force_create: true } })"
                      >
                        {{ item.title }}
                      </button>
                    </div>

                    <div v-else-if="block.type === 'knowledge_cards'" class="builder-card">
                      <div v-for="card in block.items" :key="card.title" class="knowledge-card">
                        <div class="builder-card__title">{{ card.title }}</div>
                        <div class="builder-actions">
                          <button type="button" class="builder-action builder-action--primary" @click="handleAction({ type: card.card_type === 'user_preference' ? 'confirm_preference' : 'confirm_knowledge', payload: { accepted: true, card } })">
                            确认
                          </button>
                          <button type="button" class="builder-action" @click="handleAction({ type: card.card_type === 'user_preference' ? 'confirm_preference' : 'confirm_knowledge', payload: { accepted: false, card } })">
                            不保存
                          </button>
                        </div>
                      </div>
                    </div>

                    <div v-else-if="block.type === 'actions'" class="builder-actions">
                      <button
                        v-for="action in block.items"
                        :key="action.label"
                        type="button"
                        class="builder-action"
                        :class="{ 'builder-action--primary': action.type === 'confirm_generate' }"
                        @click="handleAction(action)"
                      >
                        {{ action.label }}
                      </button>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </TransitionGroup>
        </div>

        <footer class="chat-composer">
          <div class="composer-box">
            <textarea
              v-model="composerText"
              class="composer-input"
              rows="1"
              :disabled="sending"
              :placeholder="activeMode === 'builder' ? '描述你想创建、调整或探索的 BI 图表…' : '输入问题…'"
              @keydown.enter.prevent="sendComposer"
            />
            <button type="button" class="composer-send" :disabled="sending || !composerText.trim()" aria-label="发送" @click="sendComposer">
              <el-icon><Promotion /></el-icon>
            </button>
          </div>
        </footer>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Promotion } from '@element-plus/icons-vue'
import { CHAT_MODES, getChatMode, type ChatModeId } from '../constants/chatModes'
import { biBuilderChat, deepResearchUrl, quickQA } from '../api'
import { getChatHistory, listFiles } from '../api/space'
import {
  INSIGHT_PROMPT_GROUPS,
  DEEP_PROMPT_QUESTIONS,
  BUILDER_PROMPT_QUESTIONS
} from '../mocks/chatPromptsMock'

const chatModes = CHAT_MODES
const insightGroups = INSIGHT_PROMPT_GROUPS
const deepPrompts = DEEP_PROMPT_QUESTIONS
const builderPrompts = BUILDER_PROMPT_QUESTIONS
const router = useRouter()
const SPACE_KEY = 'xlsx-bi-active-space'

const activeMode = ref<ChatModeId>('insight')
const contentMode = ref<ChatModeId>('insight')
const contentFading = ref(false)
const activeSessionId = ref<string | null>(null)
type ChatMessage = { role: string; content: string; blocks?: any[] }
type ChatSessionItem = {
  id: string
  mode: ChatModeId
  title: string
  preview: string
  updatedAt: string
  fileId?: string
  messages?: ChatMessage[]
}
const messages = ref<ChatMessage[]>([])
const sessions = ref<ChatSessionItem[]>([])
const chatRef = ref<HTMLElement>()
const composerText = ref('')
const sending = ref(false)
const builderSessionId = ref<string | null>(null)
const formValues = ref<Record<string, any>>({})

let switchGen = 0

const currentModeConfig = computed(() => getChatMode(activeMode.value))
const displayModeConfig = computed(() => getChatMode(contentMode.value))

const filteredSessions = computed(() =>
  sessions.value
    .filter((s) => s.mode === activeMode.value)
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
)

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

async function onPromptClick(text: string) {
  if (activeMode.value !== contentMode.value) activeMode.value = contentMode.value
  await sendChatMessage(text)
}

async function sendComposer() {
  const text = composerText.value.trim()
  if (!text) return
  composerText.value = ''
  await sendChatMessage(text)
}

async function latestFileId() {
  const spaceId = localStorage.getItem(SPACE_KEY) || ''
  const res = await listFiles(spaceId)
  const files = res.data.data || []
  const latest = files.find((f: any) => f.status === 'analyzed' || f.status === 'understanding_ready') || files[0]
  return latest?.id || ''
}

async function sendBuilderMessage(text: string, event?: any) {
  const fileId = await latestFileId()
  if (!fileId) {
    ElMessage.warning('请先在数据页上传并分析文件')
    return
  }
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  await nextTick()
  scrollToBottom()
  try {
    const spaceId = localStorage.getItem(SPACE_KEY) || ''
    const res = await biBuilderChat({
      file_id: fileId,
      message: text,
      session_id: builderSessionId.value,
      space_id: spaceId,
      event: event || { type: 'user_message', payload: {} },
    })
    const data = res.data.data
    builderSessionId.value = data.session_id || builderSessionId.value
    if (data.session_id) activeSessionId.value = data.session_id
    const reply = data.reply || { content: '已处理', blocks: [] }
    messages.value.push({ role: 'assistant', content: reply.content || '', blocks: reply.blocks || [] })
    await loadHistory()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '构建者处理失败')
    messages.value.push({ role: 'assistant', content: e.response?.data?.detail || e.message || '构建者处理失败' })
  } finally {
    sending.value = false
    await nextTick()
    scrollToBottom()
  }
}

async function sendChatMessage(text: string, event?: any) {
  if (activeMode.value === 'builder' || contentMode.value === 'builder') {
    await sendBuilderMessage(text, event)
    return
  }
  if (activeMode.value === 'deep' || contentMode.value === 'deep') {
    await sendDeepMessage(text)
    return
  }
  await sendInsightMessage(text)
}

async function sendInsightMessage(text: string) {
  const fileId = await latestFileId()
  if (!fileId) {
    ElMessage.warning('请先在数据页上传并分析文件')
    return
  }
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  await nextTick()
  scrollToBottom()
  try {
    const spaceId = localStorage.getItem(SPACE_KEY) || ''
    const res = await quickQA(fileId, text, {
      space_id: spaceId,
      session_id: activeSessionId.value,
      conversation_history: messages.value.slice(-10).map((m) => ({ role: m.role, content: m.content })),
    })
    const data = res.data.data || {}
    if (data.session_id) activeSessionId.value = data.session_id
    const blocks: any[] = []
    if (Array.isArray(data.data) && data.data.length) {
      blocks.push({
        type: 'data_table',
        title: '查询结果',
        columns: Object.keys(data.data[0]),
        rows: data.data,
      })
    }
    if (Array.isArray(data.recommended_questions) && data.recommended_questions.length) {
      blocks.push({
        type: 'markdown',
        content: '推荐追问：\n' + data.recommended_questions.map((q: string) => `- ${q}`).join('\n'),
      })
    }
    messages.value.push({ role: 'assistant', content: data.answer || '已完成分析。', blocks })
    await loadHistory()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '洞察处理失败')
    messages.value.push({ role: 'assistant', content: e.response?.data?.detail || e.message || '洞察处理失败' })
  } finally {
    sending.value = false
    await nextTick()
    scrollToBottom()
  }
}

async function sendDeepMessage(text: string) {
  const fileId = await latestFileId()
  if (!fileId) {
    ElMessage.warning('请先在数据页上传并分析文件')
    return
  }
  const spaceId = localStorage.getItem(SPACE_KEY) || ''
  const sessionId = activeSessionId.value || crypto.randomUUID()
  activeSessionId.value = sessionId
  messages.value.push({ role: 'user', content: text })
  const assistantMsg: ChatMessage = { role: 'assistant', content: '开始深度洞察…' }
  messages.value.push(assistantMsg)
  sending.value = true
  await nextTick()
  scrollToBottom()

  try {
    const token = localStorage.getItem('xlsx-bi-token')
    const response = await fetch(deepResearchUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        file_id: fileId,
        question: text,
        space_id: spaceId,
        session_id: sessionId,
      }),
    })
    if (!response.ok || !response.body) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || '深度洞察处理失败')
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalReport = ''
    const progress: string[] = []
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''
      for (const chunk of chunks) {
        const line = chunk.split('\n').find((l) => l.startsWith('data: '))
        if (!line) continue
        const event = JSON.parse(line.slice(6))
        if (event.message) progress.push(event.message)
        if (event.report) finalReport = event.report
        if (event.result?.report) finalReport = event.result.report
        assistantMsg.content = finalReport || progress.slice(-6).join('\n')
      }
      await nextTick()
      scrollToBottom()
    }
    assistantMsg.content = finalReport || assistantMsg.content || '深度洞察完成。'
    await loadHistory()
  } catch (e: any) {
    ElMessage.error(e.message || '深度洞察处理失败')
    assistantMsg.content = e.message || '深度洞察处理失败'
  } finally {
    sending.value = false
    await nextTick()
    scrollToBottom()
  }
}

async function handleAction(action: any) {
  if (action.type === 'navigate') {
    await router.push({ path: action.target || '/bi', query: action.params || {} })
    return
  }
  const eventPayload = action.payload || {}
  await sendBuilderMessage(eventPayload.message || action.label || '', {
    type: action.type,
    payload: eventPayload,
  })
}

async function loadHistory() {
  const spaceId = localStorage.getItem(SPACE_KEY) || ''
  const res = await getChatHistory(spaceId)
  const rows = res.data.data || []
  const groups = new Map<string, any[]>()
  for (const row of rows) {
    const mode = (row.mode || 'insight') as ChatModeId
    const sid = row.session_id || `${mode}-${row.file_id || 'none'}-${row.id}`
    const key = `${mode}:${sid}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(row)
  }
  sessions.value = Array.from(groups.entries()).map(([key, group]) => {
    const firstUser = group.find((m) => m.role === 'user') || group[0]
    const last = group[group.length - 1]
    const mode = (group[0]?.mode || 'insight') as ChatModeId
    const id = key.slice(key.indexOf(':') + 1)
    return {
      id,
      mode,
      title: firstUser?.content?.slice(0, 24) || '未命名对话',
      preview: last?.content?.slice(0, 36) || '',
      updatedAt: last?.created_at || firstUser?.created_at || '',
      fileId: firstUser?.file_id,
      messages: group.map((m) => ({ role: m.role, content: m.content })),
    }
  })
}

async function submitQuestionnaire(block: any) {
  const values: Record<string, any> = {}
  for (const q of block.questions || []) {
    if (formValues.value[q.field]) values[q.field] = formValues.value[q.field]
  }
  await sendBuilderMessage('已补充必要信息', {
    type: 'submit_questionnaire',
    payload: { form_values: values },
  })
}

function optionLabel(opt: any) {
  return typeof opt === 'string' ? opt : opt.label
}

function optionValue(opt: any) {
  return typeof opt === 'string' ? opt : opt.value
}

function renderMarkdown(content: string) {
  if (!content) return ''
  const lines = content.trim().split('\n')
  if (lines.length >= 2 && lines[0].includes('|') && lines[1].includes('---')) {
    const headers = lines[0].split('|').map((s) => s.trim()).filter(Boolean)
    const rows = lines.slice(2).map((line) => line.split('|').map((s) => s.trim()).filter(Boolean))
    return `<table class="builder-md-table"><thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${escapeHtml(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`
  }
  return escapeHtml(content).replace(/\n/g, '<br>')
}

function escapeHtml(s: string) {
  return String(s).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch] || ch))
}

function switchMode(mode: ChatModeId) {
  if (mode === activeMode.value && !contentFading.value) return

  const gen = ++switchGen
  activeMode.value = mode
  activeSessionId.value = null
  messages.value = []
  if (mode !== 'builder') builderSessionId.value = null
  formValues.value = {}

  const config = getChatMode(mode)
  if (!config.switchTransition) {
    contentMode.value = mode
    contentFading.value = false
    return
  }

  contentFading.value = true
  window.setTimeout(() => {
    if (gen !== switchGen) return
    contentMode.value = mode
    window.setTimeout(() => {
      if (gen !== switchGen) return
      contentFading.value = false
    }, 120)
  }, 100)
}

async function selectSession(item: ChatSessionItem) {
  if (item.mode !== activeMode.value) {
    await switchMode(item.mode)
  }
  activeSessionId.value = item.id
  if (item.mode === 'builder') builderSessionId.value = item.id
  messages.value = item.messages || []
  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight
}

onMounted(() => {
  for (const mode of chatModes) {
    const img = new Image()
    img.src = mode.avatar
  }
  loadHistory()
})
</script>

<style scoped>
.chat-view {
  --chat-bg: #FAF9F7;
  --chat-surface: #FFFFFF;
  --chat-sidebar: #F7F5F2;
  --chat-border: #E8E4DF;
  --chat-text: #2B2825;
  --chat-muted: #6B6560;
  --chat-faint: #9C9690;
  --chat-accent: #C6613F;
  --chat-orange: #C6613F;
  --chat-orange-soft: #DA7756;
  --chat-chip-bg: #FFFCFA;
  --chat-chip-hover: #FFF6F1;
  --chat-chip-border: rgba(198, 97, 63, 0.32);
  --chat-chip-border-hover: rgba(198, 97, 63, 0.52);
  --chat-card-bg: #FFFFFF;
  --chat-card-border: rgba(198, 97, 63, 0.22);

  display: flex;
  height: calc(100vh - var(--header-height, 52px) - 20px);
  min-height: 0;
  margin: 0;
  background: var(--chat-bg);
  color: var(--chat-text);
  font-family: var(--font-family);
}

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

.builder-blocks {
  display: grid;
  gap: 10px;
  margin-top: 10px;
}

.builder-card {
  padding: 12px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: rgba(255, 252, 250, 0.78);
}

.builder-card__title {
  font-size: 13px;
  font-weight: 650;
  color: var(--chat-text);
  margin-bottom: 4px;
}

.builder-card__meta,
.builder-card__reason {
  font-size: 12px;
  color: var(--chat-muted);
  line-height: 1.45;
}

.builder-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.builder-action {
  min-height: 30px;
  padding: 0 11px;
  border: 1px solid var(--chat-chip-border);
  border-radius: 8px;
  background: var(--chat-chip-bg);
  color: var(--chat-accent);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.builder-action--primary {
  background: var(--chat-accent);
  color: #fff;
  border-color: var(--chat-accent);
}

.builder-field {
  display: grid;
  gap: 5px;
  margin: 8px 0;
  font-size: 12px;
  color: var(--chat-muted);
}

.builder-field select {
  height: 32px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: #fff;
  color: var(--chat-text);
  padding: 0 8px;
  font: inherit;
}

.preview-table-wrap,
.builder-markdown {
  overflow-x: auto;
}

:deep(.builder-md-table),
.preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

:deep(.builder-md-table th),
:deep(.builder-md-table td),
.preview-table th,
.preview-table td {
  border: 1px solid var(--chat-border);
  padding: 6px 8px;
  text-align: left;
  white-space: nowrap;
}

:deep(.builder-md-table th),
.preview-table th {
  background: rgba(198, 97, 63, 0.08);
  color: var(--chat-text);
}

.builder-details summary {
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}

.knowledge-card + .knowledge-card {
  margin-top: 10px;
}

/* ========== Main ========== */
.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--chat-bg);
}

.chat-panel {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px 16px;
}

.chat-messages--welcome {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 8px 24px 12px;
}

.chat-welcome {
  flex: 1;
  min-height: 0;
  width: 100%;
  max-width: 920px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.welcome-stage {
  position: relative;
  flex: 1;
  min-height: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  isolation: isolate;
  overflow: hidden;
}

.welcome-hero-layer {
  position: absolute;
  left: 50%;
  top: 26%;
  z-index: 0;
  width: min(460px, 88vw);
  height: min(400px, 46vh);
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.welcome-hero {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center bottom;
  opacity: 0;
  transition: opacity 0.32s ease;
  will-change: opacity;
}

.welcome-hero--visible {
  opacity: 1;
}

.welcome-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding-top: 148px;
  transition: opacity 0.22s ease;
}

.welcome-content--fading {
  opacity: 0.35;
  pointer-events: none;
}

.welcome-title {
  margin: 0 0 10px;
  font-size: 26px;
  font-weight: 500;
  letter-spacing: -0.03em;
  color: var(--chat-text);
  line-height: 1.25;
}

.welcome-desc {
  margin: 0 0 20px;
  font-size: 15px;
  color: var(--chat-muted);
  line-height: 1.55;
  max-width: 520px;
  font-weight: 400;
}

.prompt-layout {
  width: 100%;
  max-width: 720px;
}

.prompt-layout--grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.prompt-card {
  text-align: left;
  background: var(--chat-card-bg);
  border: 1.5px solid var(--chat-card-border);
  border-radius: 14px;
  padding: 14px 12px 12px;
  box-shadow: 0 1px 4px rgba(198, 97, 63, 0.05);
}

.prompt-card--single {
  max-width: 680px;
  margin: 0 auto;
  width: 100%;
  padding: 16px 14px 14px;
}

.prompt-card__title {
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--chat-orange-soft);
  letter-spacing: 0;
}

.prompt-card__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prompt-chip {
  width: 100%;
  padding: 14px 16px;
  font-size: 14px;
  line-height: 1.5;
  font-family: inherit;
  text-align: left;
  color: var(--chat-orange);
  background: var(--chat-chip-bg);
  border: 1.5px solid var(--chat-chip-border);
  border-radius: 12px;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(198, 97, 63, 0.06);
  transition:
    background 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    color 0.18s ease;
}

.prompt-chip:hover {
  color: #A8522F;
  background: var(--chat-chip-hover);
  border-color: var(--chat-chip-border-hover);
  box-shadow: 0 2px 10px rgba(198, 97, 63, 0.1);
}

.prompt-chip--long {
  line-height: 1.6;
  padding: 16px 18px;
}

.msg-list {
  display: flex;
  flex-direction: column;
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 85%;
}

.message.user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
  background: rgba(217, 119, 87, 0.1);
  color: var(--chat-accent);
}

.message.assistant .message-avatar {
  background: rgba(28, 25, 23, 0.06);
  color: var(--chat-muted);
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.65;
}

.message.user .message-bubble {
  background: var(--chat-accent);
  color: #fff;
}

.message.assistant .message-bubble {
  background: var(--chat-surface);
  border: 1px solid var(--chat-border);
}

.chat-composer {
  flex-shrink: 0;
  padding: 12px 24px 16px;
  border-top: 1px solid var(--chat-border);
  background: rgba(250, 248, 245, 0.92);
}

.composer-box {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  max-width: 720px;
  margin: 0 auto;
  padding: 10px 12px 10px 16px;
  background: var(--chat-surface);
  border: 1px solid var(--chat-border);
  border-radius: 16px;
  opacity: 0.75;
}

.composer-input {
  flex: 1;
  min-height: 24px;
  padding: 4px 0;
  font-size: 14px;
  font-family: inherit;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--chat-text);
}

.composer-input:disabled {
  cursor: not-allowed;
}

.composer-input::placeholder {
  color: var(--chat-faint);
}

.composer-send {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 10px;
  background: var(--chat-border);
  color: var(--chat-faint);
  cursor: not-allowed;
}

@media (max-width: 960px) {
  .prompt-layout--grid {
    grid-template-columns: 1fr;
  }
}
</style>
