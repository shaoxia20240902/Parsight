<template>
  <div class="staged-board">
    <header class="staged-board__topbar">
      <div class="staged-board__meta">
        <h2 class="staged-board__title">BI 智能看板</h2>
        <p class="staged-board__subtitle">
          {{ categoryStates.length }} 个分类 · {{ completedChartCount }}/{{ totalChartCount || '—' }} 图表
          <span v-if="elapsedText"> · {{ elapsedText }}</span>
        </p>
      </div>
      <div class="staged-board__phases" aria-label="生成阶段">
        <span
          v-for="(phase, index) in phases"
          :key="phase.key"
          class="staged-board__phase"
          :class="{
            'staged-board__phase--active': index === activePhaseIndex,
            'staged-board__phase--done': index < activePhaseIndex
          }"
        >
          {{ phase.label }}
        </span>
      </div>
    </header>

    <div class="staged-board__tabs">
      <button
        v-for="cat in categoryStates"
        :key="cat.id"
        type="button"
        class="staged-board__tab"
        :class="{
          active: activeCategoryId === cat.id,
          [`staged-board__tab--${cat.status}`]: true
        }"
        @click="activeCategoryId = cat.id"
      >
        <span class="staged-board__tab-name">{{ displayName(cat.name) }}</span>
        <span class="staged-board__tab-count">{{ cat.done }}/{{ cat.total || '—' }}</span>
      </button>
    </div>

    <section v-if="activeCategory" class="staged-board__section">
      <div v-if="showCategoryThinking" class="staged-board__think-wrap">
        <BIThinkingSnippet
          :text="categoryThinkingText"
          :typing="categoryThinkingTyping"
          hint="正在规划本分类的分析视角与图表方案"
        />
      </div>

      <div v-if="!hasChartPlanReady && !activeCharts.length" class="staged-board__empty-cards">
        <div v-for="n in 2" :key="n" class="staged-board__placeholder-card">
          <BIThinkingSnippet
            :text="categoryThinkingText || latestMessage"
            :typing="categoryThinkingTyping"
            :show-header="n === 1"
            compact
          />
        </div>
      </div>

      <div v-else class="staged-board__grid">
        <article
          v-for="chart in activeCharts"
          :key="chart.id"
          class="staged-chart"
          :class="`staged-chart--${chart.status}`"
        >
          <header class="staged-chart__head">
            <span class="staged-chart__type">{{ chartTypeLabel(chart.chart_type) }}</span>
            <h3 class="staged-chart__title">{{ chart.title }}</h3>
            <span class="staged-chart__status">{{ chartStatusLabel(chart.status) }}</span>
          </header>
          <div class="staged-chart__body">
            <div v-if="chart.status === 'completed'" class="staged-chart__done">
              <span class="staged-chart__check">✓</span>
              <span>图表已生成</span>
            </div>
            <template v-else>
              <div class="staged-chart__skeleton" aria-hidden="true">
                <span />
                <span />
                <span class="staged-chart__skeleton-bar" />
              </div>
              <BIThinkingSnippet
                :text="chartThinkingText(chart)"
                :typing="chart.status === 'processing'"
                label="图表生成中"
                compact
                :show-header="true"
              />
            </template>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { BIProgressEvent } from '../../api'
import { useBiGenerationProgress } from '../../composables/useBiGenerationProgress'
import BIThinkingSnippet from './BIThinkingSnippet.vue'

const props = defineProps<{
  events: BIProgressEvent[]
  generationStartedAt?: string
}>()

const phases = [
  { key: 'category', label: '分类' },
  { key: 'chart_plan', label: '图表方案' },
  { key: 'execution', label: '执行' },
  { key: 'completed', label: '完成' },
]

const {
  categoryStates,
  chartsByCategory,
  totalChartCount,
  completedChartCount,
  latestMessage,
  activePhaseIndex,
  hasChartPlanReady,
  displayName,
  events,
} = useBiGenerationProgress(computed(() => props.events))

const activeCategoryId = ref('')
const now = ref(Date.now())
let clockTimer: ReturnType<typeof setInterval> | null = null

const activeCategory = computed(() =>
  categoryStates.value.find((c) => c.id === activeCategoryId.value)
)

const activeCharts = computed(() => chartsByCategory.value[activeCategoryId.value] || [])

watch(
  categoryStates,
  (cats) => {
    if (!cats.length) return
    if (!activeCategoryId.value || !cats.some((c) => c.id === activeCategoryId.value)) {
      const busy = cats.find((c) => c.status === 'planning' || c.status === 'processing')
      activeCategoryId.value = busy?.id || cats[0].id
    }
  },
  { immediate: true }
)

const showCategoryThinking = computed(() => {
  const cat = activeCategory.value
  if (!cat) return true
  return cat.status === 'planning' || cat.status === 'waiting' || !hasChartPlanReady.value
})

const streamThinkingByCategory = computed(() => {
  const map: Record<string, string> = {}
  for (const event of events.value) {
    if (event.step !== 'thinking_entry' || !event.entry?.text) continue
    const catName = event.entry.sheet_name || event.category_name
    if (!catName) continue
    const cat = categoryStates.value.find(
      (c) => c.name === catName || displayName(c.name) === displayName(catName)
    )
    if (cat) map[cat.id] = event.entry.text
  }
  return map
})

const globalThinkingText = computed(() => {
  const entries = events.value.filter((e) => e.step === 'thinking_entry' && e.entry?.text)
  const last = entries[entries.length - 1]
  return last?.entry?.text || ''
})

const categoryThinkingText = computed(() => {
  if (activeCategoryId.value && streamThinkingByCategory.value[activeCategoryId.value]) {
    return streamThinkingByCategory.value[activeCategoryId.value]
  }
  const u = [...events.value].reverse().find((e) => e.step === 'understanding_loaded')
  if (u?.understanding_preview) {
    return `【${u.sheet_name || '数据表'}】${u.understanding_preview}`
  }
  return globalThinkingText.value || latestMessage.value || '正在分析数据表结构与业务含义…'
})

const categoryThinkingTyping = computed(() => {
  const cat = activeCategory.value
  return cat?.status === 'planning' || cat?.status === 'processing'
})

function chartThinkingText(chart: { status: string; title: string; message?: string }) {
  if (chart.status === 'failed') return chart.message || '图表生成失败'
  if (chart.status === 'processing') {
    const evt = [...events.value].reverse().find((e) => e.step === 'chart_start' && e.title === chart.title)
    return evt?.message || `正在生成「${chart.title}」的查询与可视化…`
  }
  return `等待生成「${chart.title}」`
}

function chartStatusLabel(status: string) {
  if (status === 'completed') return '完成'
  if (status === 'failed') return '失败'
  if (status === 'processing') return '生成中'
  return '等待'
}

function chartTypeLabel(type?: string) {
  const labels: Record<string, string> = {
    kpi_group: '指标组',
    bar: '柱状图',
    line: '折线图',
    pie: '饼图',
    table: '汇总表',
    ranking: '排行图',
  }
  return labels[type || ''] || '图表'
}

const startedAt = computed(() => {
  const raw = props.generationStartedAt || events.value.find((e) => e.generation_started_at)?.generation_started_at
  if (!raw) return Date.now()
  const parsed = Date.parse(raw)
  return Number.isNaN(parsed) ? Date.now() : parsed
})

const elapsedText = computed(() => {
  const seconds = Math.max(0, Math.floor((now.value - startedAt.value) / 1000))
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
})

function startClock() {
  stopClock()
  now.value = Date.now()
  clockTimer = setInterval(() => {
    now.value = Date.now()
  }, 1000)
}

function stopClock() {
  if (clockTimer) {
    clearInterval(clockTimer)
    clockTimer = null
  }
}

onMounted(startClock)
onUnmounted(stopClock)
</script>

<style scoped>
.staged-board {
  min-height: calc(100vh - var(--header-height, 52px) - 20px);
  background: #F4F1EA;
}

.staged-board__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  background: rgba(253, 251, 248, 0.9);
  border-bottom: 1px solid #E8E1D8;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.staged-board__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1F1A17;
}

.staged-board__subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: #A39B92;
}

.staged-board__phases {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.staged-board__phase {
  padding: 4px 10px;
  border-radius: 8px;
  background: #EDE8E1;
  color: #8B8278;
  font-size: 11px;
  white-space: nowrap;
}

.staged-board__phase--active {
  background: rgba(198, 97, 63, 0.14);
  color: #9A4E32;
  font-weight: 600;
}

.staged-board__phase--done {
  background: rgba(45, 138, 86, 0.12);
  color: #2D7A4B;
}

.staged-board__tabs {
  display: flex;
  gap: 8px;
  padding: 12px 20px;
  overflow-x: auto;
  border-bottom: 1px solid #E8E1D8;
  background: #F8F4EE;
}

.staged-board__tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid #E5E0D8;
  border-radius: 8px;
  background: #fff;
  color: #736C64;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.staged-board__tab.active {
  border-color: rgba(198, 97, 63, 0.4);
  background: rgba(198, 97, 63, 0.08);
  color: #8B4513;
  font-weight: 600;
}

.staged-board__tab--processing.active {
  border-color: rgba(198, 97, 63, 0.45);
}

.staged-board__tab--completed.active {
  border-color: rgba(45, 138, 86, 0.35);
  background: rgba(45, 138, 86, 0.08);
  color: #2D7A4B;
}

.staged-board__tab-count {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  opacity: 0.8;
}

.staged-board__section {
  padding: 20px;
  max-width: 1280px;
  margin: 0 auto;
}

.staged-board__think-wrap {
  margin-bottom: 16px;
}

.staged-board__empty-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.staged-board__placeholder-card {
  min-height: 160px;
}

.staged-board__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.staged-chart {
  border: 1px solid #E8E1D8;
  border-radius: 12px;
  background: #FDFCFA;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(28, 25, 23, 0.04);
}

.staged-chart--processing {
  border-color: rgba(198, 97, 63, 0.32);
}

.staged-chart--completed {
  border-color: rgba(45, 138, 86, 0.28);
}

.staged-chart--failed {
  border-color: rgba(180, 35, 24, 0.28);
}

.staged-chart__head {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid #EDE8E1;
  background: #F8F4EE;
}

.staged-chart__type {
  font-size: 11px;
  color: #5C7A8C;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(92, 122, 140, 0.1);
}

.staged-chart__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #3D3835;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.staged-chart__status {
  font-size: 11px;
  color: #A39E96;
}

.staged-chart--processing .staged-chart__status {
  color: #C6613F;
}

.staged-chart--completed .staged-chart__status {
  color: #2D7A4B;
}

.staged-chart__body {
  padding: 14px;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.staged-chart__skeleton {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.staged-chart__skeleton span {
  display: block;
  height: 10px;
  border-radius: 6px;
  background: #EDE8E1;
  animation: staged-skeleton 1.3s ease infinite;
}

.staged-chart__skeleton-bar {
  height: 72px !important;
  margin-top: 4px;
}

@keyframes staged-skeleton {
  0%, 100% { opacity: 0.55; }
  50% { opacity: 1; }
}

.staged-chart__done {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #2D7A4B;
  font-size: 14px;
}

.staged-chart__check {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(45, 138, 86, 0.12);
  font-weight: 700;
}

@media (max-width: 900px) {
  .staged-board__topbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .staged-board__empty-cards,
  .staged-board__grid {
    grid-template-columns: 1fr;
  }
}
</style>
