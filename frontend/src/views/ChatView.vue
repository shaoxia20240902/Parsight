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
                    <h3 class="prompt-card__title">描述你想看的销售报表</h3>
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
                <div class="message-content" :class="{ 'message-content--pending': msg.pending }">
                  <span v-if="msg.pending" class="thinking-dot" aria-hidden="true"></span>
                  {{ msg.content }}
                </div>
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
                        <div class="builder-card__meta">这类业务知识会通过弹窗确认后保存到对应 Sheet 的表理解中。</div>
                        <div class="builder-actions">
                          <button type="button" class="builder-action builder-action--primary" @click="openKnowledgeDialog(card)">
                            打开确认弹窗
                          </button>
                          <button type="button" class="builder-action" @click="handleAction({ type: card.card_type === 'user_preference' ? 'confirm_preference' : 'confirm_knowledge', payload: { accepted: false, card } })">
                            不保存
                          </button>
                        </div>
                      </div>
                    </div>

                    <div v-else-if="block.type === 'sales_chart_plan'" class="builder-card">
                      <div class="builder-card__title">将创建这些销售报表</div>
                      <div class="sales-plan-list">
                        <div v-for="item in block.items" :key="item.client_chart_id" class="sales-plan-item">
                          <strong>{{ item.title }}</strong>
                          <span>{{ item.business_type }} · {{ item.metric }} · 按 {{ item.dimension }} 看</span>
                          <small>{{ item.chart_type_label }} · {{ item.category_name }}</small>
                        </div>
                      </div>
                      <button type="button" class="builder-action" @click="openChartEditor(block)">
                        调整报表方案
                      </button>
                    </div>

                    <div v-else-if="block.type === 'companion_suggestions'" class="builder-card">
                      <div class="builder-card__title">建议顺手补充</div>
                      <div class="builder-card__meta">这些报表已经按当前语境准备好，点击即可创建。</div>
                      <div class="builder-actions builder-actions--stack">
                        <button
                          v-for="item in block.items"
                          :key="item.title"
                          type="button"
                          class="builder-action"
                          @click="handleAction({ type: 'create_companion_chart', label: item.title, payload: { chart: item.chart } })"
                        >
                          {{ item.title }}
                        </button>
                      </div>
                    </div>

                    <div v-else-if="block.type === 'completion_summary'" class="builder-card">
                      <div class="builder-card__title">本轮上下文已保存</div>
                      <div class="builder-card__meta">{{ block.summary?.business_context }}</div>
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
            <!-- 统一思考状态（非 builder 模式专属） -->
            <div v-if="sending && !messages.some(m => m.pending)" key="thinking" class="message assistant">
              <div class="message-avatar">析</div>
              <div class="message-bubble">
                <div class="message-content message-content--thinking">
                  <span class="thinking-pulse" aria-hidden="true" />
                  <span class="thinking-text">{{ thinkingTexts[thinkingIndex] }}</span>
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
              :placeholder="activeMode === 'builder' ? '例如：我想看客户销售额 Top10，顺便看尾部客户…' : '输入问题…'"
              @keydown.enter.prevent="sendComposer"
            />
            <button type="button" class="composer-send" :disabled="sending || !composerText.trim()" aria-label="发送" @click="sendComposer">
              <el-icon><Promotion /></el-icon>
            </button>
          </div>
        </footer>

        <div v-if="knowledgeDialog.open" class="modal-backdrop" @click.self="closeKnowledgeDialog">
          <section class="builder-modal">
            <header class="builder-modal__header">
              <h3>确认业务知识</h3>
              <button type="button" class="modal-close" @click="closeKnowledgeDialog">×</button>
            </header>
            <div class="builder-modal__body">
              <label class="builder-field">
                <span>业务表达</span>
                <input v-model="knowledgeDialog.term" />
              </label>
              <label class="builder-field">
                <span>实际含义</span>
                <input v-model="knowledgeDialog.canonical" />
              </label>
              <label class="builder-field">
                <span>保存到哪个 Sheet</span>
                <select v-model="knowledgeDialog.tableName">
                  <option v-for="opt in knowledgeDialog.sheetOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
              </label>
            </div>
            <footer class="builder-modal__footer">
              <button type="button" class="builder-action" @click="closeKnowledgeDialog">取消</button>
              <button type="button" class="builder-action builder-action--primary" @click="confirmKnowledgeDialog">
                确认添加
              </button>
            </footer>
          </section>
        </div>

        <div v-if="chartEditor.open" class="modal-backdrop" @click.self="closeChartEditor">
          <section class="builder-modal builder-modal--wide">
            <header class="builder-modal__header">
              <h3>调整报表方案</h3>
              <button type="button" class="modal-close" @click="closeChartEditor">×</button>
            </header>
            <div class="builder-modal__body chart-editor">
              <div v-for="chart in chartEditor.items" :key="chart.client_chart_id" class="chart-edit-row">
                <label class="builder-field">
                  <span>报表名称</span>
                  <input v-model="chart.title" />
                </label>
                <label class="builder-field">
                  <span>看什么指标</span>
                  <select v-model="chart.metric.field">
                    <option v-for="opt in chartEditor.fields.metrics" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                  </select>
                </label>
                <label class="builder-field">
                  <span>按什么看</span>
                  <select v-model="chart.dimension">
                    <option v-for="opt in chartEditor.fields.dimensions" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                  </select>
                </label>
                <label class="builder-field">
                  <span>报表样式</span>
                  <select v-model="chart.chart_type">
                    <option value="kpi_group">核心指标卡</option>
                    <option value="ranking">排名榜</option>
                    <option value="bar">对比图</option>
                    <option value="line">趋势图</option>
                    <option value="pie">占比图</option>
                    <option value="combo">目标达成图</option>
                    <option value="table">汇总表</option>
                    <option value="detail_table">明细清单</option>
                  </select>
                </label>
                <label class="builder-field">
                  <span>放到哪里</span>
                  <select v-model="chart.target_category_id">
                    <option v-for="opt in chartEditor.categories" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                  </select>
                </label>
              </div>
            </div>
            <footer class="builder-modal__footer">
              <button type="button" class="builder-action" @click="closeChartEditor">取消</button>
              <button type="button" class="builder-action builder-action--primary" @click="submitChartEditor">
                保存方案
              </button>
            </footer>
          </section>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Promotion } from '@element-plus/icons-vue'
import { CHAT_MODES, getChatMode, type ChatModeId } from '../constants/chatModes'
import { biBuilderChat, deepResearchUrl, quickQA, getChatRecommendations } from '../api'
import { getChatHistory, listFiles } from '../api/space'
import {
  INSIGHT_PROMPT_GROUPS,
  DEEP_PROMPT_QUESTIONS,
  BUILDER_PROMPT_QUESTIONS
} from '../mocks/chatPromptsMock'

const chatModes = CHAT_MODES
const insightGroups = ref<typeof INSIGHT_PROMPT_GROUPS>(INSIGHT_PROMPT_GROUPS)
const deepPrompts = ref<string[]>(DEEP_PROMPT_QUESTIONS)
const builderPrompts = ref<string[]>(BUILDER_PROMPT_QUESTIONS)
const recommendationsLoaded = ref(false)
const router = useRouter()
const SPACE_KEY = 'xlsx-bi-active-space'

const activeMode = ref<ChatModeId>('insight')
const contentMode = ref<ChatModeId>('insight')
const contentFading = ref(false)
const activeSessionId = ref<string | null>(null)
type ChatMessage = { role: string; content: string; blocks?: any[]; pending?: boolean }
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
const thinkingIndex = ref(0)
let thinkingTimer: ReturnType<typeof setInterval> | null = null

const thinkingTexts = [
  '正在分析数据结构…',
  '正在读取表字段信息…',
  '正在查找相关记录…',
  '正在聚合计算…',
  '正在整理分析结果…',
  '正在生成可视化建议…',
]

const builderSessionId = ref<string | null>(null)
const formValues = ref<Record<string, any>>({})
const lastBuilderChartList = ref<any[]>([])
const lastBuilderEditorPayload = ref<any>({})
const knowledgeDialog = ref({
  open: false,
  card: null as any,
  term: '',
  canonical: '',
  tableName: '',
  sheetOptions: [] as Array<{ label: string; value: string }>,
})
const chartEditor = ref({
  open: false,
  items: [] as any[],
  categories: [] as Array<{ label: string; value: string }>,
  fields: { metrics: [] as any[], dimensions: [] as any[], times: [] as any[] },
})

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

async function loadRecommendations() {
  if (recommendationsLoaded.value) return
  const fileId = await latestFileId()
  if (!fileId) return
  try {
    const res = await getChatRecommendations(fileId)
    const data = res.data.data
    if (data?.status === 'completed' && data.questions) {
      const q = data.questions
      if (q.insight_groups?.length) {
        insightGroups.value = q.insight_groups.map((g: any) => ({
          title: g.title,
          questions: g.questions.slice(0, 3) as [string, string, string],
        }))
      }
      if (q.deep_questions?.length) {
        deepPrompts.value = q.deep_questions.slice(0, 3)
      }
      if (q.builder_questions?.length) {
        builderPrompts.value = q.builder_questions.slice(0, 3)
      }
      recommendationsLoaded.value = true
    }
  } catch (e) {
    console.error('加载推荐问题失败', e)
  }
}

async function sendBuilderMessage(text: string, event?: any) {
  const fileId = await latestFileId()
  if (!fileId) {
    ElMessage.warning('请先在数据页上传并分析文件')
    return
  }
  const eventType = event?.type || 'user_message'
  if (eventType === 'user_message' && text) {
    messages.value.push({ role: 'user', content: text })
  }
  const assistantMsg: ChatMessage = { role: 'assistant', content: builderLoadingText(eventType), blocks: [], pending: true }
  messages.value.push(assistantMsg)
  sending.value = true
  startThinkingCycle()
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
    assistantMsg.content = reply.content || ''
    assistantMsg.blocks = reply.blocks || []
    assistantMsg.pending = false
    lastBuilderChartList.value = data.chart_list || data.scope_plan?.chart_list || lastBuilderChartList.value
    rememberBuilderEditorPayload(reply.blocks || [])
    await loadHistory()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '构建者处理失败')
    assistantMsg.content = e.response?.data?.detail || e.message || '构建者处理失败'
    assistantMsg.pending = false
  } finally {
    sending.value = false
    stopThinkingCycle()
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
  startThinkingCycle()
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
    stopThinkingCycle()
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
  startThinkingCycle()
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
    stopThinkingCycle()
    await nextTick()
    scrollToBottom()
  }
}

async function handleAction(action: any) {
  if (action.type === 'navigate') {
    await router.push({ path: action.target || '/bi', query: action.params || {} })
    return
  }
  if (action.type === 'open_chart_editor') {
    openChartEditor(lastBuilderEditorPayload.value)
    return
  }
  const eventPayload = action.payload || {}
  await sendBuilderMessage(eventPayload.message || '', {
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

function builderLoadingText(eventType: string) {
  if (eventType === 'confirm_generate' || eventType === 'create_companion_chart') return '正在创建分析图表…'
  if (eventType === 'confirm_knowledge') return '正在保存数据知识并继续…'
  if (eventType === 'update_chart_list') return '正在更新分析方案…'
  if (eventType === 'confirm_complete') return '正在整理本轮上下文…'
  return '正在处理你的分析需求…'
}

function startThinkingCycle() {
  stopThinkingCycle()
  thinkingIndex.value = 0
  thinkingTimer = setInterval(() => {
    thinkingIndex.value = (thinkingIndex.value + 1) % thinkingTexts.length
  }, 3500)
}

function stopThinkingCycle() {
  if (thinkingTimer) {
    clearInterval(thinkingTimer)
    thinkingTimer = null
  }
}

function rememberBuilderEditorPayload(blocks: any[]) {
  const plan = blocks.find((b) => b.type === 'sales_chart_plan')
  if (plan) {
    lastBuilderEditorPayload.value = plan
  }
  const knowledge = blocks.find((b) => b.type === 'knowledge_cards')
  if (knowledge?.items?.length) {
    openKnowledgeDialog(knowledge.items[0])
  }
}

function openKnowledgeDialog(card: any) {
  const payload = card.payload || {}
  if (card.card_type === 'user_preference') {
    handleAction({ type: 'confirm_preference', payload: { accepted: true, card } })
    return
  }
  knowledgeDialog.value = {
    open: true,
    card,
    term: payload.term || '',
    canonical: payload.canonical || payload.mapped_to || '',
    tableName: payload.table_name || card.recommended_table_name || card.sheet_options?.[0]?.value || '',
    sheetOptions: card.sheet_options || [],
  }
}

function closeKnowledgeDialog() {
  knowledgeDialog.value.open = false
}

async function confirmKnowledgeDialog() {
  const dialog = knowledgeDialog.value
  const card = {
    ...(dialog.card || {}),
    payload: {
      ...((dialog.card || {}).payload || {}),
      term: dialog.term,
      canonical: dialog.canonical,
      table_name: dialog.tableName,
    },
  }
  dialog.open = false
  await handleAction({ type: 'confirm_knowledge', payload: { accepted: true, card } })
}

function openChartEditor(block: any) {
  const items = (lastBuilderChartList.value || []).map((chart) => ({
    ...structuredClone(chart),
    metric: { ...(chart.metric || { field: '' }) },
    dimension: (chart.dimensions || [])[0] || '',
  }))
  chartEditor.value = {
    open: true,
    items,
    categories: block?.categories || [],
    fields: block?.fields || { metrics: [], dimensions: [], times: [] },
  }
}

function closeChartEditor() {
  chartEditor.value.open = false
}

async function submitChartEditor() {
  const chartList = chartEditor.value.items.map((chart) => ({
    ...chart,
    dimensions: chart.dimension ? [chart.dimension] : [],
    metric: { ...(chart.metric || {}), label: chart.metric?.field || chart.metric?.label || '' },
  }))
  chartEditor.value.open = false
  await sendBuilderMessage('', {
    type: 'update_chart_list',
    payload: { chart_list: chartList },
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

  // 尝试加载动态推荐问题
  loadRecommendations()

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
  loadRecommendations()
})

onUnmounted(() => {
  stopThinkingCycle()
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

.builder-actions--stack {
  flex-direction: column;
  align-items: flex-start;
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

.builder-field input {
  height: 34px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: #fff;
  color: var(--chat-text);
  padding: 0 9px;
  font: inherit;
}

.message-content--pending {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--chat-muted);
}

.thinking-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--chat-accent);
  box-shadow: 12px 0 0 rgba(198, 97, 63, 0.35), 24px 0 0 rgba(198, 97, 63, 0.2);
  animation: thinkingPulse 1s ease-in-out infinite;
}

@keyframes thinkingPulse {
  0%, 100% { opacity: 0.35; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-1px); }
}

.message-content--thinking {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--chat-muted);
  min-height: 22px;
}

.thinking-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--chat-accent);
  box-shadow: 0 0 0 0 rgba(198, 97, 63, 0.45);
  animation: pulse-ring 1.8s ease-out infinite;
  flex-shrink: 0;
}

@keyframes pulse-ring {
  0% { box-shadow: 0 0 0 0 rgba(198, 97, 63, 0.45); }
  70% { box-shadow: 0 0 0 10px rgba(198, 97, 63, 0); }
  100% { box-shadow: 0 0 0 0 rgba(198, 97, 63, 0); }
}

.thinking-text {
  font-size: 13px;
  color: #8B7355;
  font-weight: 400;
  letter-spacing: 0.01em;
}

.sales-plan-list {
  display: grid;
  gap: 8px;
  margin: 8px 0 10px;
}

.sales-plan-item {
  display: grid;
  gap: 2px;
  padding: 9px 10px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: #fff;
}

.sales-plan-item strong {
  font-size: 13px;
  color: var(--chat-text);
}

.sales-plan-item span,
.sales-plan-item small {
  font-size: 12px;
  color: var(--chat-muted);
}

.modal-backdrop {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 22px;
  background: rgba(43, 40, 37, 0.24);
}

.builder-modal {
  width: min(460px, 100%);
  max-height: min(680px, 92%);
  display: flex;
  flex-direction: column;
  background: var(--chat-surface);
  border: 1px solid var(--chat-border);
  border-radius: 10px;
  box-shadow: 0 18px 44px rgba(43, 40, 37, 0.16);
  overflow: hidden;
}

.builder-modal--wide {
  width: min(860px, 100%);
}

.builder-modal__header,
.builder-modal__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--chat-border);
}

.builder-modal__footer {
  justify-content: flex-end;
  border-top: 1px solid var(--chat-border);
  border-bottom: 0;
}

.builder-modal__header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
}

.builder-modal__body {
  padding: 14px 16px;
  overflow-y: auto;
}

.modal-close {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--chat-muted);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}

.chart-editor {
  display: grid;
  gap: 12px;
}

.chart-edit-row {
  display: grid;
  grid-template-columns: 1.3fr 1fr 1fr 1fr 1fr;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: rgba(255, 252, 250, 0.78);
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
