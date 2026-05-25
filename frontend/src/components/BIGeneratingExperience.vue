<template>
  <div class="bi-gen">
    <!-- 布局容器：默认居中，展开后左右分栏 -->
    <div class="bi-gen__layout" :class="{ 'bi-gen__layout--expanded': showJournal, 'bi-gen__layout--error': error }">
      <!-- 左侧：主卡片 -->
      <div class="bi-gen__left">
        <div class="bi-gen__card">
          <!-- 图表轮播 -->
          <div class="bi-gen__stage" aria-hidden="true">
            <Transition name="chart-fade" mode="out-in">
              <div :key="activeSlide.type" class="bi-gen__chart-wrap">
                <svg
                  class="bi-gen__chart"
                  :style="{ color: activeSlide.color }"
                  viewBox="0 0 120 80"
                  fill="none"
                  v-html="activeSlide.svg"
                />
              </div>
            </Transition>
          </div>

          <div v-if="!error && showFullProgress" class="bi-gen__progress-panel">
            <div class="bi-gen__phase-row">
              <div
                v-for="(phase, index) in phases"
                :key="phase.key"
                class="bi-gen__phase"
                :class="{
                  'bi-gen__phase--active': index === activePhaseIndex,
                  'bi-gen__phase--done': index < activePhaseIndex
                }"
              >
                <span class="bi-gen__phase-dot">{{ index + 1 }}</span>
                <span>{{ phase.label }}</span>
              </div>
            </div>
            <div class="bi-gen__progress-track">
              <span class="bi-gen__progress-fill" :style="{ width: `${progressPercent}%` }" />
            </div>

            <div class="bi-gen__summary-row">
              <div class="bi-gen__summary-item">
                <span class="bi-gen__summary-label">已用时</span>
                <strong>{{ elapsedText }}</strong>
              </div>
              <div class="bi-gen__summary-item">
                <span class="bi-gen__summary-label">分类</span>
                <strong>{{ categoryStates.length || latestCategoriesPayload.length }}</strong>
              </div>
              <div class="bi-gen__summary-item">
                <span class="bi-gen__summary-label">图表</span>
                <strong>{{ completedChartCount }}/{{ totalChartCount || '-' }}</strong>
              </div>
            </div>

            <p class="bi-gen__event-line">{{ latestMessage }}</p>

            <div v-if="categoryStates.length" class="bi-gen__category-list">
              <div
                v-for="cat in categoryStates"
                :key="cat.id"
                class="bi-gen__category-chip"
                :class="`bi-gen__category-chip--${cat.status}`"
                :title="cat.name"
              >
                <span class="bi-gen__status-icon">{{ statusIcon(cat.status) }}</span>
                <span class="bi-gen__category-name">{{ displayName(cat.name) }}</span>
                <span class="bi-gen__category-count">{{ cat.done }}/{{ cat.total }}</span>
              </div>
            </div>

            <div v-if="activeCategoryPlan" class="bi-gen__plan">
              <div class="bi-gen__plan-head">
                <span>{{ displayName(activeCategoryPlan.category_name) }}</span>
                <span>{{ activeCategoryPlan.charts_count }} 个图表</span>
              </div>
              <div class="bi-gen__type-row">
                <span
                  v-for="item in typeSummary(activeCategoryPlan.type_counts)"
                  :key="item.type"
                  class="bi-gen__type-pill"
                >
                  {{ chartTypeLabel(item.type) }} × {{ item.count }}
                </span>
              </div>
            </div>

            <div v-else-if="categoryStates.length" class="bi-gen__plan bi-gen__plan--pending">
              <div class="bi-gen__plan-head">
                <span>正在拆解图表方案</span>
                <span>{{ pendingPlanHint }}</span>
              </div>
              <div class="bi-gen__skeleton-list">
                <span class="bi-gen__skeleton-line" />
                <span class="bi-gen__skeleton-line bi-gen__skeleton-line--short" />
              </div>
            </div>

            <div v-if="visibleCharts.length" class="bi-gen__chart-queue">
              <div
                v-for="chart in visibleCharts"
                :key="chart.id"
                class="bi-gen__chart-item"
                :class="`bi-gen__chart-item--${chart.status}`"
              >
                <span class="bi-gen__status-icon">{{ statusIcon(chart.status) }}</span>
                <span class="bi-gen__chart-title">{{ chart.title }}</span>
                <span class="bi-gen__chart-type">{{ chartTypeLabel(chart.chart_type) }}</span>
                <button
                  v-if="chart.status === 'failed'"
                  type="button"
                  class="bi-gen__retry-link"
                  @click="$emit('retry')"
                >
                  重试
                </button>
              </div>
            </div>

            <div v-if="recentEvents.length" class="bi-gen__recent">
              <div
                v-for="item in recentEvents"
                :key="item.key"
                class="bi-gen__recent-item"
              >
                <span class="bi-gen__recent-dot" />
                <span>{{ item.text }}</span>
              </div>
            </div>
          </div>

          <!-- 思考区：最多 3 行，超出在框内滚动 -->
          <div v-if="!error" class="bi-gen__think">
            <BIThinkingSnippet
              :text="currentThinkText"
              :typing="typewriterActive"
              hint="正在为你生成数据看板，请稍候"
            />

            <!-- 展开/收起思考过程 -->
            <button
              v-if="!showJournal"
              type="button"
              class="bi-gen__journal-toggle"
              @click="showJournal = true"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2 4h10M2 7h7M2 10h5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              </svg>
              查看思考过程
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" class="bi-gen__toggle-arrow">
                <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>

          <div v-else class="bi-gen__error-block">
            <p class="bi-gen__error-title">生成未能完成</p>
            <p class="bi-gen__error-msg">{{ error }}</p>
            <button type="button" class="bi-gen__btn bi-gen__btn--primary" @click="$emit('retry')">重新尝试</button>
          </div>
        </div>
      </div>

      <!-- 右侧：思考日志面板 -->
      <div v-show="!error" class="bi-gen__right">
        <div class="bi-gen__journal-panel">
          <div class="bi-gen__journal-head">
            <div class="bi-gen__journal-title">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2 4h10M2 7h7M2 10h5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              </svg>
              思考过程
            </div>
            <button type="button" class="bi-gen__journal-close" @click="showJournal = false">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M3.5 3.5L10.5 10.5M10.5 3.5L3.5 10.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
          <div class="bi-gen__search">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="6" cy="6" r="4.5" stroke="currentColor" stroke-width="1.2"/>
              <path d="M9.5 9.5L12 12" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
            <input
              v-model="searchQuery"
              type="search"
              class="bi-gen__search-input"
              placeholder="搜索思考记录…"
              @input="onSearchInput"
            />
          </div>
          <div ref="journalListRef" class="bi-gen__journal-list" @scroll="onJournalScroll">
            <p v-if="journalLoading && !filteredEntries.length" class="bi-gen__journal-empty">加载思考记录…</p>
            <p v-else-if="!filteredEntries.length" class="bi-gen__journal-empty">
              {{ searchQuery ? '没有匹配的记录' : '思考记录将在此出现' }}
            </p>
            <div
              v-for="(entry, idx) in filteredEntries"
              :key="entry.id"
              class="bi-gen__journal-item"
              :class="{ 'bi-gen__journal-item--last': idx === filteredEntries.length - 1 }"
            >
              <div class="bi-gen__journal-timeline">
                <span class="bi-gen__journal-dot" />
                <span v-if="idx !== filteredEntries.length - 1" class="bi-gen__journal-line" />
              </div>
              <div class="bi-gen__journal-body">
                <time class="bi-gen__journal-time">{{ formatTime(entry.ts) }}</time>
                <p class="bi-gen__journal-text" v-html="highlightText(entry.text)" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getBIThinking, type BIProgressEvent, type BIThinkingEntry } from '../api'
import BIThinkingSnippet from './bi/BIThinkingSnippet.vue'

const props = defineProps<{
  fileId: string
  active?: boolean
  error?: string
  events?: BIProgressEvent[]
  generationStartedAt?: string
}>()

defineEmits<{ retry: [] }>()

const showJournal = ref(false)

type StatusName = 'waiting' | 'planning' | 'processing' | 'completed' | 'failed' | 'partial_failed'

const phases = [
  { key: 'category', label: '分类规划' },
  { key: 'chart_plan', label: '图表规划' },
  { key: 'execution', label: '图表执行' },
  { key: 'completed', label: '完成' },
]

const thinkingLines = [
  '阅读各张表的结构与六维业务理解…',
  '从不同分析视角出发，构思值得追问的分析场景…',
  '把场景落实为可量化的问题，并审视是否清晰…',
  '为每个问题挑选合适的图表形态与查询语句…',
  '试跑查询、必要时修复，并整理看板布局…',
]

const slides = [
  {
    type: 'bar',
    label: '柱状图',
    color: '#C6613F',
    svg: `<rect x="8" y="38" width="14" height="34" rx="3" fill="currentColor" opacity="0.85"/>
          <rect x="28" y="28" width="14" height="44" rx="3" fill="currentColor" opacity="0.65"/>
          <rect x="48" y="18" width="14" height="54" rx="3" fill="currentColor" opacity="0.9"/>
          <rect x="68" y="32" width="14" height="40" rx="3" fill="currentColor" opacity="0.7"/>
          <rect x="88" y="42" width="14" height="30" rx="3" fill="currentColor" opacity="0.55"/>`,
  },
  {
    type: 'line',
    label: '折线图',
    color: '#6B8F71',
    svg: `<path d="M6 58 Q26 42 46 48 Q66 54 86 28 Q98 18 110 24" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/>
          <circle cx="46" cy="48" r="4" fill="currentColor"/><circle cx="86" cy="28" r="4" fill="currentColor"/>`,
  },
  {
    type: 'pie',
    label: '饼图',
    color: '#8B7355',
    svg: `<path d="M60 12 A38 38 0 0 1 94 52 L60 50 Z" fill="currentColor" opacity="0.88"/>
          <path d="M94 52 A38 38 0 0 1 32 28 L60 50 Z" fill="currentColor" opacity="0.55"/>
          <path d="M32 28 A38 38 0 0 1 60 12 L60 50 Z" fill="currentColor" opacity="0.35"/>`,
  },
  {
    type: 'table',
    label: '表格',
    color: '#7A6E8A',
    svg: `<rect x="10" y="16" width="100" height="52" rx="4" stroke="currentColor" stroke-width="1.5" opacity="0.35" fill="none"/>
          <line x1="10" y1="30" x2="110" y2="30" stroke="currentColor" stroke-width="1.2" opacity="0.4"/>
          <line x1="10" y1="44" x2="110" y2="44" stroke="currentColor" stroke-width="1" opacity="0.25"/>
          <line x1="10" y1="58" x2="110" y2="58" stroke="currentColor" stroke-width="1" opacity="0.25"/>
          <line x1="42" y1="16" x2="42" y2="68" stroke="currentColor" stroke-width="1" opacity="0.2"/>
          <line x1="74" y1="16" x2="74" y2="68" stroke="currentColor" stroke-width="1" opacity="0.2"/>`,
  },
  {
    type: 'area',
    label: '面积图',
    color: '#5C7A8C',
    svg: `<path d="M6 68 L6 52 Q30 36 54 42 Q78 48 102 26 L102 68 Z" fill="currentColor" opacity="0.22"/>
          <path d="M6 52 Q30 36 54 42 Q78 48 102 26" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round"/>`,
  },
  {
    type: 'rank',
    label: '排名',
    color: '#B8860B',
    svg: `<rect x="12" y="22" width="72" height="8" rx="2" fill="currentColor" opacity="0.9"/>
          <rect x="12" y="36" width="58" height="8" rx="2" fill="currentColor" opacity="0.7"/>
          <rect x="12" y="50" width="44" height="8" rx="2" fill="currentColor" opacity="0.5"/>`,
  },
]

const carouselIndex = ref(0)
const thinkIndex = ref(0)
const searchQuery = ref('')
const journalEntries = ref<BIThinkingEntry[]>([])
const journalLoading = ref(false)
const journalListRef = ref<HTMLElement | null>(null)
const userScrolled = ref(false)
const startedAt = ref(Date.now())
const now = ref(Date.now())

// SSE 流式内容收集
const streamEntries = ref<Array<{ type: 'thinking' | 'understanding'; text: string; id: string; ts: number }>>([])
const typewriterDisplay = ref('')
const typewriterIndex = ref(0)
const typewriterActive = ref(false)
let typewriterTimer: ReturnType<typeof setTimeout> | null = null

// 收集 SSE 流式事件 —— 逐条处理，不遗漏同一 tick 内的多个事件
let processedEventCount = 0
watch(
  () => props.events,
  (events) => {
    if (!events || events.length === 0) return
    const newEvents = events.slice(processedEventCount)
    processedEventCount = events.length

    for (const event of newEvents) {
      if (event.step === 'thinking_entry' && event.entry) {
        const entry = event.entry
        const text = entry.text || ''
        if (text) {
          streamEntries.value.push({
            type: 'thinking',
            text,
            id: entry.id || `${Date.now()}-${Math.random()}`,
            ts: Date.now(),
          })
          // 同步到 journalEntries，让右侧日志面板实时显示
          journalEntries.value.push({
            id: entry.id || `${Date.now()}-${Math.random()}`,
            ts: entry.ts || new Date().toISOString(),
            step: entry.step || 'thinking',
            level: entry.level || 'info',
            text: entry.text || '',
            run_id: entry.run_id,
            sheet_name: entry.sheet_name,
            table_name: entry.table_name,
            role_name: entry.role_name,
            scenario_name: entry.scenario_name,
          })
          // 自动滚动到底部
          if (journalListRef.value && !userScrolled.value) {
            requestAnimationFrame(() => {
              journalListRef.value?.scrollTo({ top: journalListRef.value.scrollHeight, behavior: 'smooth' })
            })
          }
        }
      }
      if (event.step === 'understanding_loaded') {
        const preview = event.understanding_preview || ''
        const sheetName = event.sheet_name || '数据表'
        if (preview) {
          streamEntries.value.push({
            type: 'understanding',
            text: `【${sheetName}】${preview}`,
            id: `u-${event.table_name || Date.now()}`,
            ts: Date.now(),
          })
        }
      }
    }
  },
  { immediate: false, deep: true }
)

// 打字机效果
function startTypewriter(text: string, speed = 28) {
  stopTypewriter()
  typewriterDisplay.value = ''
  typewriterIndex.value = 0
  typewriterActive.value = true

  function typeNext() {
    if (typewriterIndex.value < text.length) {
      typewriterDisplay.value += text.charAt(typewriterIndex.value)
      typewriterIndex.value++
      // 根据字符类型调整速度：标点停顿稍长
      const char = text.charAt(typewriterIndex.value - 1)
      const delay = /[，。！？；：]/.test(char) ? speed * 3 : speed
      typewriterTimer = setTimeout(typeNext, delay)
    } else {
      typewriterActive.value = false
    }
  }
  typeNext()
}

function stopTypewriter() {
  if (typewriterTimer) {
    clearTimeout(typewriterTimer)
    typewriterTimer = null
  }
  typewriterActive.value = false
}

// 自动触发最新内容的打字机效果
const pendingStreamIndex = ref(0)
watch(
  streamEntries,
  (entries) => {
    if (entries.length === 0) return
    // 当有新内容且当前不在打字时，开始打字
    if (!typewriterActive.value && pendingStreamIndex.value < entries.length) {
      const next = entries[pendingStreamIndex.value]
      pendingStreamIndex.value++
      startTypewriter(next.text, next.type === 'understanding' ? 22 : 28)
    }
  },
  { deep: true }
)

// 当前一条打字完成后，自动触发下一条
watch(typewriterActive, (active) => {
  if (!active && pendingStreamIndex.value < streamEntries.value.length) {
    const next = streamEntries.value[pendingStreamIndex.value]
    pendingStreamIndex.value++
    // 短暂停顿后开始下一条
    setTimeout(() => startTypewriter(next.text, next.type === 'understanding' ? 22 : 28), 400)
  }
})

// 当前思考区展示的文本：优先打字机内容，回退到轮播
const currentThinkText = computed(() => {
  // 打字机有内容时优先显示；打字机空闲且没内容时回退到默认轮播
  if (typewriterDisplay.value) {
    return typewriterDisplay.value
  }
  if (typewriterActive.value) {
    return ''
  }
  return thinkingLines[thinkIndex.value]
})

let carouselTimer: ReturnType<typeof setInterval> | null = null
let thinkTimer: ReturnType<typeof setInterval> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let searchDebounce: ReturnType<typeof setTimeout> | null = null
let clockTimer: ReturnType<typeof setInterval> | null = null

// 检测用户是否接近底部（40px 容差）
function isNearBottom(el: HTMLElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight < 40
}

function onJournalScroll() {
  if (!journalListRef.value) return
  // 用户手动滚动到底部附近时，恢复自动滚动
  userScrolled.value = !isNearBottom(journalListRef.value)
}

const activeSlide = computed(() => slides[carouselIndex.value])

const events = computed(() => props.events || [])
const latestEvent = computed(() => events.value[events.value.length - 1])
const latestMessage = computed(() => latestEvent.value?.message || thinkingLines[thinkIndex.value])
const serverStartedAt = computed(() =>
  props.generationStartedAt ||
  [...events.value].find((event) => event.generation_started_at)?.generation_started_at ||
  ''
)
const elapsedText = computed(() => {
  const seconds = Math.max(0, Math.floor((now.value - startedAt.value) / 1000))
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
})

const activePhaseIndex = computed(() => {
  const step = latestEvent.value?.step
  if (step === 'bi_completed') return 3
  if (['category_start', 'chart_start', 'chart_done', 'chart_failed', 'category_done'].includes(step || '')) return 2
  if (['chart_planning', 'category_plan_start', 'category_plan_done', 'chart_plan_ready'].includes(step || '')) return 1
  return 0
})

const progressPercent = computed(() => {
  const base = [18, 42, 72, 100][activePhaseIndex.value] || 8
  if (activePhaseIndex.value !== 2) return base
  const totals = categoryStates.value.reduce((acc, cat) => {
    acc.done += cat.done
    acc.total += cat.total
    return acc
  }, { done: 0, total: 0 })
  if (!totals.total) return base
  return Math.min(96, 52 + Math.round((totals.done / totals.total) * 38))
})

const latestCategoriesPayload = computed(() => {
  const found = [...events.value].reverse().find((e) => Array.isArray(e.categories))
  return found?.categories || []
})

const showFullProgress = computed(
  () => categoryStates.value.length > 0 || latestCategoriesPayload.value.length > 0
)

const latestChartPlan = computed(() => {
  const found = [...events.value].reverse().find((e) => Array.isArray(e.chart_plan))
  return found?.chart_plan || []
})

const chartStateById = computed<Record<string, { status: StatusName; message?: string }>>(() => {
  const map: Record<string, { status: StatusName; message?: string }> = {}
  for (const event of events.value) {
    if (!event.chart_id) continue
    if (event.step === 'chart_start') map[event.chart_id] = { status: 'processing' }
    if (event.step === 'chart_done') map[event.chart_id] = { status: 'completed' }
    if (event.step === 'chart_failed') map[event.chart_id] = { status: 'failed', message: event.message }
  }
  return map
})

const allPlannedCharts = computed(() => latestChartPlan.value.flatMap((plan: any) =>
  (plan.charts || []).map((chart: any) => ({
    id: chart.id,
    title: chart.title || '未命名图表',
    chart_type: chart.chart_type || 'table',
    category_id: chart.category_id || plan.category_id,
    status: chartStateById.value[chart.id]?.status || 'waiting',
    message: chartStateById.value[chart.id]?.message,
  }))
))

const totalChartCount = computed(() => {
  const planned = latestChartPlan.value.reduce((sum: number, plan: any) => sum + Number(plan.charts_count || 0), 0)
  if (planned) return planned
  const event = [...events.value].reverse().find((e) => Number(e.charts_count || 0) > 0)
  return Number(event?.charts_count || 0)
})

const completedChartCount = computed(() =>
  Object.values(chartStateById.value).filter((item) => item.status === 'completed').length
)

const activeCategoryId = computed(() => {
  const active = [...events.value].reverse().find((e) =>
    ['category_plan_start', 'category_plan_done', 'category_start', 'chart_start', 'chart_done', 'chart_failed', 'category_done'].includes(e.step) && e.category_id
  )
  return active?.category_id || latestChartPlan.value[0]?.category_id || latestCategoriesPayload.value[0]?.id
})

const activeCategoryPlan = computed(() =>
  latestChartPlan.value.find((plan: any) => plan.category_id === activeCategoryId.value)
)

const visibleCharts = computed(() => {
  const active = activeCategoryId.value
  const list = allPlannedCharts.value.filter((chart: any) => chart.category_id === active)
  const activeOrFailed = list.filter((chart: any) => chart.status !== 'waiting')
  return (activeOrFailed.length ? activeOrFailed : list).slice(-8)
})

const categoryStates = computed(() => {
  const plans = latestChartPlan.value
  const categories = plans.length
    ? plans.map((plan: any) => ({
        id: plan.category_id,
        name: plan.category_name,
        total: plan.charts_count || (plan.charts || []).length,
      }))
    : latestCategoriesPayload.value.map((cat: any) => ({
        id: cat.id || cat.category_id,
        name: cat.display_name || cat.name,
        total: 0,
      }))

  return categories.map((cat: any) => {
    const charts = allPlannedCharts.value.filter((chart: any) => chart.category_id === cat.id)
    const done = charts.filter((chart: any) => ['completed', 'failed'].includes(chart.status)).length
    const failed = charts.some((chart: any) => chart.status === 'failed')
    const processing = charts.some((chart: any) => chart.status === 'processing') || isCategoryExecuting(cat.id)
    const planning = isCategoryPlanning(cat.id)
    let status: StatusName = 'waiting'
    if (failed && done >= (cat.total || charts.length)) status = 'partial_failed'
    else if ((cat.total || charts.length) > 0 && done >= (cat.total || charts.length)) status = 'completed'
    else if (processing) status = 'processing'
    else if (planning) status = 'planning'
    return { ...cat, done, failed, status }
  })
})

const pendingPlanHint = computed(() => {
  const current = categoryStates.value.find((cat) => cat.status === 'planning' || cat.status === 'processing')
  return current ? displayName(current.name) : '等待模型返回'
})

const recentEvents = computed(() => {
  return [...events.value]
    .reverse()
    .filter((event) => event.message || event.title || event.category_name)
    .slice(0, 4)
    .map((event, index) => ({
      key: `${events.value.length}-${index}-${event.step}`,
      text: event.message || event.title || event.category_name || '',
    }))
})

const filteredEntries = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return journalEntries.value
  return journalEntries.value.filter((e) => {
    const blob = [e.text, e.sheet_name, e.table_name, e.role_name, e.scenario_name]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return blob.includes(q)
  })
})

function formatTime(ts?: string) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ts
  }
}

function displayName(name?: string) {
  return [...(name || '分类')].slice(0, 6).join('')
}

function statusIcon(status: StatusName) {
  if (status === 'completed') return '✓'
  if (status === 'failed' || status === 'partial_failed') return '!'
  if (status === 'processing' || status === 'planning') return '…'
  return '○'
}

function isCategoryPlanning(categoryId: string) {
  const last = [...events.value].reverse().find((event) =>
    event.category_id === categoryId &&
    ['category_plan_start', 'category_plan_done', 'category_start', 'category_done'].includes(event.step)
  )
  return last?.step === 'category_plan_start'
}

function isCategoryExecuting(categoryId: string) {
  const last = [...events.value].reverse().find((event) =>
    event.category_id === categoryId &&
    ['category_start', 'chart_start', 'chart_done', 'chart_failed', 'category_done'].includes(event.step)
  )
  return !!last && last.step !== 'category_done'
}

function typeSummary(counts?: Record<string, number>) {
  return Object.entries(counts || {})
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)
}

function chartTypeLabel(type?: string) {
  const labels: Record<string, string> = {
    kpi_group: '指标组',
    kpi: '指标卡',
    bar: '柱状图',
    stacked_bar: '堆叠柱',
    horizontal_bar: '条形图',
    line: '折线图',
    multi_line: '多折线',
    area: '面积图',
    stacked_area: '堆叠面积',
    pie: '饼图',
    donut: '环形图',
    combo: '组合图',
    ranking: '排行图',
    table: '汇总表',
    detail_table: '明细表',
    treemap: '矩形树图',
    funnel: '漏斗图',
    scatter: '散点图',
    bubble: '气泡图',
    heatmap: '热力图',
    radar: '雷达图',
    gauge: '仪表盘',
    waterfall: '瀑布图',
    map: '地图',
  }
  return labels[type || ''] || '图表'
}

function escapeHtml(s: string) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function highlightText(text: string) {
  const safe = escapeHtml(text || '')
  const q = searchQuery.value.trim()
  if (!q) return safe
  const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return safe.replace(re, '<mark>$1</mark>')
}

async function fetchJournal() {
  if (!props.fileId) return
  journalLoading.value = true
  const shouldAutoScroll = journalListRef.value ? isNearBottom(journalListRef.value) && !userScrolled.value : false
  try {
    const res = await getBIThinking(props.fileId, searchQuery.value.trim() || undefined)
    journalEntries.value = res.data.data?.entries || []
    if (journalListRef.value && shouldAutoScroll) {
      requestAnimationFrame(() => {
        journalListRef.value?.scrollTo({ top: journalListRef.value.scrollHeight, behavior: 'smooth' })
      })
    }
  } catch {
    /* 保持已有条目 */
  } finally {
    journalLoading.value = false
  }
}

function onSearchInput() {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    fetchJournal()
  }, 300)
}

function startCarousel() {
  stopCarousel()
  carouselTimer = setInterval(() => {
    carouselIndex.value = (carouselIndex.value + 1) % slides.length
  }, 2000)
}

function stopCarousel() {
  if (carouselTimer) {
    clearInterval(carouselTimer)
    carouselTimer = null
  }
}

function startThinkCycle() {
  stopThinkCycle()
  thinkTimer = setInterval(() => {
    thinkIndex.value = (thinkIndex.value + 1) % thinkingLines.length
  }, 4200)
}

function stopThinkCycle() {
  if (thinkTimer) {
    clearInterval(thinkTimer)
    thinkTimer = null
  }
}

function startPoll() {
  stopPoll()
  pollTimer = setInterval(() => fetchJournal(), 10000)
}

function startClock() {
  stopClock()
  startedAt.value = resolveStartedAtMs()
  now.value = Date.now()
  clockTimer = setInterval(() => {
    now.value = Date.now()
  }, 1000)
}

function resolveStartedAtMs() {
  if (!serverStartedAt.value) return Date.now()
  const parsed = Date.parse(serverStartedAt.value)
  return Number.isNaN(parsed) ? Date.now() : parsed
}

function stopClock() {
  if (clockTimer) {
    clearInterval(clockTimer)
    clockTimer = null
  }
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(
  () => props.active,
  (on) => {
    if (on && !props.error) {
      startCarousel()
      startThinkCycle()
      startPoll()
      startClock()
    } else {
      stopCarousel()
      stopThinkCycle()
      stopPoll()
      stopClock()
    }
  },
  { immediate: true }
)

watch(
  serverStartedAt,
  () => {
    if (props.active) {
      startedAt.value = resolveStartedAtMs()
      now.value = Date.now()
    }
  }
)

onMounted(() => {
  if (props.active && !props.error) {
    startCarousel()
    startThinkCycle()
    startPoll()
    startClock()
  }
})

onUnmounted(() => {
  stopCarousel()
  stopThinkCycle()
  stopPoll()
  stopClock()
  stopTypewriter()
  if (searchDebounce) clearTimeout(searchDebounce)
})
</script>

<style scoped>
.bi-gen {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - var(--header-height, 52px) - 48px);
  padding: 32px 20px;
  background: #F4F1EA;
  animation: bi-gen-fade-in 0.4s ease;
}

@keyframes bi-gen-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* ========== 布局容器 ========== */
.bi-gen__layout {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  max-width: 760px;
  transition: max-width 0.5s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.bi-gen__layout--expanded {
  max-width: 1180px;
  gap: 20px;
}

.bi-gen__layout--error {
  max-width: 420px;
}

/* ========== 左侧主卡片 ========== */
.bi-gen__left {
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  transition: all 0.5s cubic-bezier(0.25, 0.1, 0.25, 1);
  width: 100%;
}

.bi-gen__layout--expanded .bi-gen__left {
  width: 560px;
}

.bi-gen__card {
  width: 100%;
  max-width: 760px;
  padding: 30px 32px 28px;
  background: #FDFCFA;
  border: 1px solid #E8E1D8;
  border-radius: 8px;
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.04),
    0 18px 44px rgba(58, 45, 34, 0.08);
  text-align: center;
  animation: bi-gen-card-in 0.45s cubic-bezier(0.25, 0.1, 0.25, 1);
  transition: transform 0.5s cubic-bezier(0.25, 0.1, 0.25, 1), box-shadow 0.5s ease;
}

.bi-gen__layout--expanded .bi-gen__card {
  transform: scale(0.95);
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.03),
    0 8px 24px rgba(28, 25, 23, 0.05);
}

@keyframes bi-gen-card-in {
  from {
    opacity: 0;
    transform: translateY(16px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.bi-gen__stage {
  margin-bottom: 16px;
}

.bi-gen__chart-wrap {
  display: flex;
  align-items: center;
  min-height: 108px;
  justify-content: center;
}

.bi-gen__chart {
  width: 170px;
  height: 113px;
}

.bi-gen__progress-panel {
  margin: 0 0 24px;
  padding: 14px;
  text-align: left;
  border: 1px solid #E8E1D8;
  border-radius: 8px;
  background: #F8F4EE;
}

.bi-gen__phase-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin-bottom: 10px;
}

.bi-gen__phase {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 0;
  font-size: 11px;
  color: #A39E96;
  white-space: nowrap;
}

.bi-gen__phase-dot {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #EDE8E1;
  color: #8B7355;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.bi-gen__phase--active {
  color: #C6613F;
  font-weight: 600;
}

.bi-gen__phase--active .bi-gen__phase-dot,
.bi-gen__phase--done .bi-gen__phase-dot {
  background: #C6613F;
  color: #fff;
}

.bi-gen__progress-track {
  position: relative;
  height: 6px;
  overflow: hidden;
  border-radius: 8px;
  background: #EDE8E1;
}

.bi-gen__progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #C6613F;
  transition: width 0.3s ease;
}

.bi-gen__event-line {
  margin: 10px 0 0;
  color: #4A4541;
  font-size: 12px;
  line-height: 1.45;
}

.bi-gen__summary-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.bi-gen__summary-item {
  min-width: 0;
  padding: 8px 9px;
  border: 1px solid rgba(28, 25, 23, 0.06);
  border-radius: 8px;
  background: #fff;
}

.bi-gen__summary-label {
  display: block;
  margin-bottom: 3px;
  color: #A39E96;
  font-size: 10px;
}

.bi-gen__summary-item strong {
  color: #3D3835;
  font-size: 14px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.bi-gen__category-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.bi-gen__category-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 7px 8px;
  border: 1px solid #E5E0D8;
  border-radius: 8px;
  background: #fff;
  color: #736C64;
  font-size: 12px;
}

.bi-gen__category-chip--processing {
  border-color: rgba(198, 97, 63, 0.35);
  background: rgba(198, 97, 63, 0.08);
  color: #8B4513;
}

.bi-gen__category-chip--planning {
  border-color: rgba(92, 122, 140, 0.32);
  background: rgba(92, 122, 140, 0.08);
  color: #4E6D80;
}

.bi-gen__category-chip--completed {
  border-color: rgba(45, 138, 86, 0.28);
  background: rgba(45, 138, 86, 0.08);
  color: #2D7A4B;
}

.bi-gen__category-chip--failed,
.bi-gen__category-chip--partial_failed {
  border-color: rgba(180, 35, 24, 0.28);
  background: rgba(180, 35, 24, 0.08);
  color: #B42318;
}

.bi-gen__status-icon {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 7px;
  background: rgba(28, 25, 23, 0.06);
  font-size: 11px;
  font-weight: 700;
}

.bi-gen__category-name,
.bi-gen__chart-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bi-gen__category-count {
  margin-left: auto;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: inherit;
  opacity: 0.75;
}

.bi-gen__plan {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #EDE8E1;
}

.bi-gen__plan--pending {
  color: #736C64;
}

.bi-gen__plan-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 12px;
  color: #6B6560;
  font-weight: 600;
}

.bi-gen__type-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.bi-gen__type-pill {
  padding: 3px 7px;
  border-radius: 8px;
  background: rgba(92, 122, 140, 0.1);
  color: #5C7A8C;
  font-size: 11px;
}

.bi-gen__skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.bi-gen__skeleton-line {
  display: block;
  height: 10px;
  border-radius: 8px;
  background: #EDE8E1;
  animation: skeleton-pulse 1.3s ease infinite;
}

.bi-gen__skeleton-line--short {
  width: 68%;
}

@keyframes skeleton-pulse {
  0%, 100% { opacity: 0.62; }
  50% { opacity: 1; }
}

.bi-gen__chart-queue {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
  max-height: 190px;
  overflow-y: auto;
  padding-right: 2px;
}

.bi-gen__chart-item {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #EDE8E1;
  font-size: 12px;
  color: #6B6560;
}

.bi-gen__chart-item--processing {
  border-color: rgba(198, 97, 63, 0.3);
}

.bi-gen__chart-item--completed {
  color: #2D7A4B;
}

.bi-gen__chart-item--failed {
  color: #B42318;
  border-color: rgba(180, 35, 24, 0.25);
}

.bi-gen__chart-type {
  color: #A39E96;
  font-size: 11px;
  white-space: nowrap;
}

.bi-gen__retry-link {
  padding: 2px 7px;
  border: 1px solid rgba(180, 35, 24, 0.25);
  border-radius: 7px;
  background: #fff;
  color: #B42318;
  font-size: 11px;
  font-family: inherit;
  cursor: pointer;
}

.bi-gen__journal-toggle:focus-visible,
.bi-gen__retry-link:focus-visible,
.bi-gen__btn:focus-visible,
.bi-gen__journal-close:focus-visible,
.bi-gen__search-input:focus-visible {
  outline: 2px solid rgba(198, 97, 63, 0.36);
  outline-offset: 2px;
}

.bi-gen__recent {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #EDE8E1;
}

.bi-gen__recent-item {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  min-width: 0;
  color: #8B8278;
  font-size: 11px;
  line-height: 1.45;
}

.bi-gen__recent-dot {
  width: 6px;
  height: 6px;
  margin-top: 5px;
  flex-shrink: 0;
  border-radius: 4px;
  background: #D4CEC6;
}

.chart-fade-enter-active,
.chart-fade-leave-active {
  transition: opacity 0.35s ease, transform 0.35s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.chart-fade-enter-from {
  opacity: 0;
  transform: scale(0.92) translateY(6px);
}

.chart-fade-leave-to {
  opacity: 0;
  transform: scale(1.04) translateY(-4px);
}

/* ========== 思考区 ========== */
.bi-gen__think {
  text-align: left;
  padding: 0 4px;
}

.bi-gen__think-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.bi-gen__pulse {
  width: 8px;
  height: 8px;
  border-radius: 4px;
  background: #C6613F;
  box-shadow: 0 0 0 0 rgba(198, 97, 63, 0.45);
  animation: pulse-ring 1.8s ease-out infinite;
}

@keyframes pulse-ring {
  0% { box-shadow: 0 0 0 0 rgba(198, 97, 63, 0.45); }
  70% { box-shadow: 0 0 0 10px rgba(198, 97, 63, 0); }
  100% { box-shadow: 0 0 0 0 rgba(198, 97, 63, 0); }
}

.bi-gen__think-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #8B7355;
  text-transform: uppercase;
}

.bi-gen__think :deep(.bi-think-snippet) {
  margin-bottom: 12px;
  border: none;
  background: transparent;
  padding: 0 4px;
}

.bi-gen__think :deep(.bi-think-snippet__hint) {
  margin-bottom: 16px;
}

.think-line-enter-active,
.think-line-leave-active {
  transition: opacity 0.28s ease, transform 0.28s ease;
}

.think-line-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.think-line-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ========== 展开思考过程按钮 ========== */
.bi-gen__journal-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  padding: 6px 14px;
  background: rgba(198, 97, 63, 0.06);
  border: 1px solid rgba(198, 97, 63, 0.12);
  border-radius: 8px;
  color: #A67C5B;
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.bi-gen__journal-toggle:hover {
  background: rgba(198, 97, 63, 0.1);
  border-color: rgba(198, 97, 63, 0.2);
  color: #8B5E3C;
}

.bi-gen__toggle-arrow {
  transition: transform 0.2s ease;
}

.bi-gen__journal-toggle:hover .bi-gen__toggle-arrow {
  transform: translateY(1px);
}

/* ========== 错误状态 ========== */
.bi-gen__error-block {
  padding: 8px 4px 0;
}

.bi-gen__error-title {
  margin: 0 0 8px;
  font-size: 17px;
  font-weight: 600;
  color: #1C1917;
}

.bi-gen__error-msg {
  margin: 0 0 20px;
  font-size: 14px;
  color: #736C64;
  line-height: 1.55;
}

.bi-gen__btn {
  height: 36px;
  padding: 0 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
}

.bi-gen__btn--primary {
  background: #C6613F;
  color: #FFF;
}

.bi-gen__btn--primary:hover {
  background: #B55534;
}

.bi-gen__btn--primary:active {
  transform: scale(0.98);
}

/* ========== 右侧日志面板 ========== */
.bi-gen__right {
  width: 0;
  opacity: 0;
  overflow: hidden;
  flex-shrink: 0;
  transform: translateX(30px);
  transition: all 0.5s cubic-bezier(0.25, 0.1, 0.25, 1);
  pointer-events: none;
}

.bi-gen__layout--expanded .bi-gen__right {
  width: 520px;
  opacity: 1;
  transform: translateX(0);
  pointer-events: auto;
}

.bi-gen__journal-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 480px;
  max-height: 640px;
  background: #FAF8F5;
  border: 1px solid #E8E1D8;
  border-radius: 8px;
  padding: 18px;
  overflow: hidden;
  animation: journal-slide-in 0.45s cubic-bezier(0.25, 0.1, 0.25, 1) 0.1s both;
}

@keyframes journal-slide-in {
  from {
    opacity: 0;
    transform: translateX(16px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.bi-gen__journal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(28, 25, 23, 0.06);
  margin-bottom: 12px;
  flex-shrink: 0;
}

.bi-gen__journal-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #6B6560;
}

.bi-gen__journal-close {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid rgba(28, 25, 23, 0.1);
  border-radius: 8px;
  color: #A39E96;
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 0;
}

.bi-gen__journal-close:hover {
  background: rgba(28, 25, 23, 0.04);
  border-color: rgba(28, 25, 23, 0.15);
  color: #736C64;
}

.bi-gen__search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: rgba(28, 25, 23, 0.03);
  border: 1px solid rgba(28, 25, 23, 0.08);
  border-radius: 8px;
  color: #A39E96;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.bi-gen__search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #1C1917;
  outline: none;
  font-family: inherit;
}

.bi-gen__search-input::placeholder {
  color: #C4BDB4;
}

.bi-gen__journal-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}

.bi-gen__journal-list::-webkit-scrollbar {
  width: 4px;
}

.bi-gen__journal-list::-webkit-scrollbar-thumb {
  background: #D4CEC6;
  border-radius: 2px;
}

.bi-gen__journal-empty {
  margin: 0;
  padding: 48px 0;
  font-size: 13px;
  color: #A39E96;
  text-align: center;
}

/* 时间线样式 */
.bi-gen__journal-item {
  display: flex;
  gap: 12px;
  padding: 10px 0;
}

.bi-gen__journal-timeline {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 14px;
  padding-top: 4px;
}

.bi-gen__journal-dot {
  width: 8px;
  height: 8px;
  border-radius: 4px;
  background: #C6613F;
  flex-shrink: 0;
}

.bi-gen__journal-line {
  flex: 1;
  width: 1.5px;
  background: rgba(198, 97, 63, 0.18);
  margin-top: 4px;
  min-height: 20px;
}

.bi-gen__journal-item--last .bi-gen__journal-line {
  display: none;
}

.bi-gen__journal-body {
  flex: 1;
  min-width: 0;
}

.bi-gen__journal-time {
  display: block;
  font-size: 11px;
  color: #C4BDB4;
  margin-bottom: 4px;
  font-variant-numeric: tabular-nums;
}

.bi-gen__journal-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: #4A4541;
}

.bi-gen__journal-text :deep(mark) {
  background: rgba(198, 97, 63, 0.18);
  color: #8B4513;
  border-radius: 2px;
  padding: 0 2px;
}

/* ========== 响应式 ========== */
@media (max-width: 980px) {
  .bi-gen__layout--expanded {
    flex-direction: column;
    align-items: center;
    max-width: 520px;
  }

  .bi-gen__layout--expanded .bi-gen__left {
    width: 100%;
  }

  .bi-gen__layout--expanded .bi-gen__card {
    transform: scale(1);
  }

  .bi-gen__layout--expanded .bi-gen__right {
    width: 100%;
    transform: translateY(20px);
  }

  .bi-gen__layout--expanded .bi-gen__right {
    transform: translateY(0);
  }

  .bi-gen__journal-panel {
    max-height: 480px;
    min-height: 360px;
  }
}

@media (max-width: 640px) {
  .bi-gen {
    padding: 20px 14px;
  }

  .bi-gen__card {
    padding: 24px 18px;
  }

  .bi-gen__phase-row,
  .bi-gen__summary-row,
  .bi-gen__category-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .bi-gen__chart-item {
    grid-template-columns: 18px minmax(0, 1fr) auto;
  }

  .bi-gen__retry-link {
    grid-column: 2 / -1;
    justify-self: start;
  }
}
</style>
