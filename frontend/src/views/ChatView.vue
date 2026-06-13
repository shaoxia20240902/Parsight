<template>
  <div class="chat-view">
    <ChatSidebar
      :chat-modes="chatModes"
      :active-mode="activeMode"
      :sessions="filteredSessions"
      :active-session-id="activeSessionId"
      @switch-mode="switchMode"
      @select-session="selectSession"
    />

    <main class="chat-main">
      <div class="chat-panel">
        <div
          ref="chatRef"
          class="chat-messages"
          :class="{ 'chat-messages--welcome': messages.length === 0 }"
        >
          <WelcomeScreen
            v-if="messages.length === 0"
            :chat-modes="chatModes"
            :content-mode="contentMode"
            :content-fading="contentFading"
            :display-mode-config="displayModeConfig"
            :insight-groups="insightGroups"
            :deep-prompts="deepPrompts"
            :builder-prompts="builderPrompts"
            @prompt-click="onPromptClick"
          />

          <MessageList
            v-else
            :messages="messages"
            :sending="sending"
            :thinking-index="thinkingIndex"
            :thinking-texts="thinkingTexts"
            @intent-action="handleIntentAction"
            @action="handleAction"
            @send-message="sendBuilderMessage"
            @open-knowledge="openKnowledgeDialog"
            @open-chart-editor="openChartEditor"
            @submit-questionnaire="submitQuestionnaire"
          />
        </div>

        <ChatComposer
          v-model="composerText"
          :sending="sending"
          :placeholder="activeMode === 'builder' ? '例如：我想看客户销售额 Top10，顺便看尾部客户…' : '输入问题…'"
          @send="sendComposer"
        />

        <KnowledgeDialog
          :open="knowledgeDialog.open"
          :term="knowledgeDialog.term"
          :canonical="knowledgeDialog.canonical"
          :table-name="knowledgeDialog.tableName"
          :sheet-options="knowledgeDialog.sheetOptions"
          @close="closeKnowledgeDialog"
          @confirm="confirmKnowledgeDialog"
          @update:term="knowledgeDialog.term = $event"
          @update:canonical="knowledgeDialog.canonical = $event"
          @update:table-name="knowledgeDialog.tableName = $event"
        />

        <ChartEditorModal
          :open="chartEditor.open"
          :items="chartEditor.items"
          :categories="chartEditor.categories"
          :fields="chartEditor.fields"
          @close="closeChartEditor"
          @submit="submitChartEditor"
        />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CHAT_MODES, getChatMode, type ChatModeId } from '../constants/chatModes'
import { biBuilderChat, deepResearchUrl, quickQA, getChatRecommendations, detectChatIntent } from '../api'
import { getChatHistory, listFiles } from '../api/space'
import {
  INSIGHT_PROMPT_GROUPS,
  DEEP_PROMPT_QUESTIONS,
  BUILDER_PROMPT_QUESTIONS
} from '../mocks/chatPromptsMock'
import ChatSidebar from '../components/chat/ChatSidebar.vue'
import WelcomeScreen from '../components/chat/WelcomeScreen.vue'
import MessageList from '../components/chat/MessageList.vue'
import ChatComposer from '../components/chat/ChatComposer.vue'
import KnowledgeDialog from '../components/chat/KnowledgeDialog.vue'
import ChartEditorModal from '../components/chat/ChartEditorModal.vue'

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
type PendingIntent = { text: string; mode: ChatModeId; fileId: string; spaceId: string }
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
const pendingIntent = ref<PendingIntent | null>(null)
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

async function sendBuilderMessage(text: string, event?: any, options?: { showUser?: boolean }) {
  const fileId = await latestFileId()
  if (!fileId) {
    ElMessage.warning('请先在数据页上传并分析文件')
    return
  }
  const eventType = event?.type || 'user_message'
  if (eventType === 'user_message' && text && options?.showUser !== false) {
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

async function sendChatMessage(text: string, event?: any, options?: { confirmed?: boolean; showUser?: boolean }) {
  if (activeMode.value === 'builder' || contentMode.value === 'builder') {
    if (!options?.confirmed && !event) {
      await requestIntentConfirmation(text)
      return
    }
    await sendBuilderMessage(text, event, { showUser: options?.showUser })
    return
  }
  if (activeMode.value === 'deep' || contentMode.value === 'deep') {
    if (!options?.confirmed) {
      await requestIntentConfirmation(text)
      return
    }
    await sendDeepMessage(text, { showUser: options?.showUser })
    return
  }
  if (!options?.confirmed) {
    await requestIntentConfirmation(text)
    return
  }
  await sendInsightMessage(text, { showUser: options?.showUser })
}

async function requestIntentConfirmation(text: string) {
  const fileId = await latestFileId()
  if (!fileId) {
    ElMessage.warning('请先在数据页上传并分析文件')
    return
  }
  const spaceId = localStorage.getItem(SPACE_KEY) || ''
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  startThinkingCycle()
  await nextTick()
  scrollToBottom()
  try {
    const res = await detectChatIntent({
      file_id: fileId,
      question: text,
      mode: activeMode.value,
      space_id: spaceId,
    })
    const intent = res.data.data || {}
    pendingIntent.value = { text, mode: activeMode.value, fileId, spaceId }
    messages.value.push({
      role: 'assistant',
      content: intent.auto_execute ? '已识别问题类型，马上进入真实执行链路。' : '这个问题还不够明确，我需要先和你确认一下。',
      blocks: [{ type: 'intent_confirmation', ...intent, source_text: text, source_mode: activeMode.value }],
    })
    await nextTick()
    scrollToBottom()
    if (intent.auto_execute) {
      await executeConfirmedIntent(text, {
        ...intent,
        source_text: text,
        source_mode: activeMode.value,
      })
    }
  } catch (e: any) {
    const detail = e.response?.data?.detail
    const errText = (typeof detail === 'string' ? detail : null) || e.message || '意图识别失败'
    ElMessage.error(errText)
    messages.value.push({ role: 'assistant', content: errText })
  } finally {
    sending.value = false
    stopThinkingCycle()
    await nextTick()
    scrollToBottom()
  }
}

async function sendInsightMessage(text: string, options?: { showUser?: boolean }) {
  const fileId = await latestFileId()
  if (!fileId) {
    ElMessage.warning('请先在数据页上传并分析文件')
    return
  }
  if (options?.showUser !== false) messages.value.push({ role: 'user', content: text })
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
    if (Array.isArray(data.agent_steps) && data.agent_steps.length) {
      blocks.unshift({
        type: 'agent_steps',
        items: data.agent_steps,
      })
    }
    messages.value.push({ role: 'assistant', content: data.answer || '已完成分析。', blocks })
    await loadHistory()
  } catch (e: any) {
    const detail = e.response?.data?.detail
    const errText =
      (typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: any) => d.msg || d).join('；') : null) ||
      e.message ||
      '洞察处理失败'
    ElMessage.error(errText)
    messages.value.push({ role: 'assistant', content: errText })
  } finally {
    sending.value = false
    stopThinkingCycle()
    await nextTick()
    scrollToBottom()
  }
}

async function sendDeepMessage(text: string, options?: { showUser?: boolean }) {
  const fileId = await latestFileId()
  if (!fileId) {
    ElMessage.warning('请先在数据页上传并分析文件')
    return
  }
  const spaceId = localStorage.getItem(SPACE_KEY) || ''
  const sessionId = activeSessionId.value || crypto.randomUUID()
  activeSessionId.value = sessionId
  if (options?.showUser !== false) messages.value.push({ role: 'user', content: text })
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
    const agentSteps: any[] = []
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
        if (event.step && event.status && ['completed', 'confirmed', 'need_confirm'].includes(event.status)) {
          const name = deepStepName(event.step)
          if (!agentSteps.some((s) => s.name === name)) {
            agentSteps.push({
              name,
              detail: event.status === 'need_confirm' ? '识别到需要澄清的条件，已纳入执行上下文' : event.message || '已完成',
            })
          }
        }
        if (event.report) finalReport = event.report
        if (event.result?.report) finalReport = event.result.report
        assistantMsg.content = finalReport || progress.slice(-6).join('\n')
        assistantMsg.blocks = agentSteps.length ? [{ type: 'agent_steps', items: agentSteps }] : []
      }
      await nextTick()
      scrollToBottom()
    }
    assistantMsg.content = finalReport || assistantMsg.content || '深度洞察完成。'
    assistantMsg.blocks = agentSteps.length ? [{ type: 'agent_steps', items: agentSteps }] : assistantMsg.blocks
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

function deepStepName(step: string) {
  const map: Record<string, string> = {
    keyword_match: '意图与关键词澄清',
    role_decomposition: '多角色问题拆解',
    sub_questions: '子问题筛选',
    sql_generation: '查询生成',
    sql_execution: '数据验证',
    chart_generation: '证据图表生成',
    report_generation: '洞察报告生成',
    completed: '深度洞察完成',
  }
  return map[step] || step
}

async function handleIntentAction(action: any, block: any) {
  if (sending.value || block.resolved) return
  const sourceText = block.source_text || pendingIntent.value?.text || ''
  if (action.type === 'cancel_intent') {
    block.resolved = true
    block.resolved_label = '已取消执行'
    messages.value.push({ role: 'assistant', content: '已停止执行。你可以补充问题，或切换另一种问答类型重新发起。' })
    pendingIntent.value = null
    await nextTick()
    scrollToBottom()
    return
  }
  if (action.type === 'refine_intent') {
    block.resolved = true
    block.resolved_label = '等待补充问题'
    composerText.value = sourceText
    messages.value.push({ role: 'assistant', content: '请在输入框里补充指标、维度、时间范围或你希望的输出形式，我会重新识别。' })
    pendingIntent.value = null
    await nextTick()
    scrollToBottom()
    return
  }
  if (action.type !== 'confirm_intent') return

  block.resolved = true
  block.resolved_label = '已确认执行'
  messages.value.push({ role: 'assistant', content: `已确认，进入「${block.mode_label || currentModeConfig.value.label}」执行链路。` })
  pendingIntent.value = null
  await executeConfirmedIntent(sourceText, block)
}

async function executeConfirmedIntent(text: string, block: any) {
  const sourceMode = (block.source_mode || pendingIntent.value?.mode || activeMode.value) as ChatModeId
  const normalizedMode = block.mode === 'quick' ? 'insight' : (block.mode || sourceMode)
  const targetMode = (normalizedMode === 'quick' ? 'insight' : normalizedMode) as ChatModeId

  if (targetMode === 'builder') {
    messages.value.push({ role: 'assistant', content: '正在调用生成 BI Agent，识别已有图表并规划可写入的报表方案…' })
    await sendBuilderMessage(text, undefined, { showUser: false })
    return
  }
  if (targetMode === 'deep') {
    messages.value.push({ role: 'assistant', content: '正在调用深度洞察 Agent，进入多步推理、SQL 查询和报告生成链路…' })
    await sendDeepMessage(text, { showUser: false })
    return
  }
  messages.value.push({ role: 'assistant', content: '正在调用快速问答 LLM Agent，并根据生成的 SQL 执行真实数据查询…' })
  await sendInsightMessage(text, { showUser: false })
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

async function submitQuestionnaire(_block: any, values: Record<string, any>) {
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

async function submitChartEditor(items: any[]) {
  const chartList = items.map((chart) => ({
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

function switchMode(mode: ChatModeId) {
  if (mode === activeMode.value && !contentFading.value) return

  const gen = ++switchGen
  activeMode.value = mode
  activeSessionId.value = null
  messages.value = []
  pendingIntent.value = null
  if (mode !== 'builder') builderSessionId.value = null

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
</style>
