<template>
  <div class="staged-board">
    <section v-if="!categoryStates.length" class="staged-intro">
      <article class="staged-question-card staged-question-card--intro">
        <div class="staged-card-head">
          <div>
            <h3>正在思考数据结构</h3>
            <p>识别 Excel 文件、生成数据分类与公共筛选参数</p>
          </div>
          <span>阶段 B1</span>
        </div>
        <div class="staged-question-layout">
          <div class="staged-thinking-panel">
            <BIThinkingSnippet
              :text="categoryThinkingText || latestMessage"
              :typing="true"
              hint="正在阅读上传的 Excel 文件，并抽取可复用的看板骨架"
            />
            <div class="staged-thought-list">
              <div v-for="item in stageOneThoughts" :key="item.title" class="staged-thought-item">
                <span class="staged-thought-dot" />
                <div>
                  <strong>{{ item.title }}</strong>
                  <p>{{ item.desc }}</p>
                </div>
              </div>
            </div>
          </div>
          <div class="staged-motion-panel" aria-hidden="true">
            <div class="motion-chart motion-chart--bars">
              <span v-for="n in 8" :key="n" :style="{ '--i': n }" />
            </div>
            <div class="motion-chart motion-chart--line">
              <i v-for="n in 6" :key="n" :style="{ '--i': n }" />
            </div>
            <div class="motion-chip-row">
              <span>Sheet 分类</span>
              <span>公共筛选</span>
              <span>关联字段</span>
            </div>
          </div>
        </div>
      </article>
    </section>

    <template v-else>
    <aside class="staged-sidebar">
      <div class="staged-sidebar__head">
        <h2>全局筛选</h2>
        <span>{{ globalFilters.length }} 项</span>
      </div>
      <p class="staged-sidebar__hint">筛选将作用于当前看板内所有适用图表，单图筛选优先于全局筛选。</p>

      <div class="staged-filter-list">
        <div v-for="filter in globalFilters" :key="filter.field" class="staged-filter">
          <label>{{ filter.label }}</label>
          <button type="button" class="staged-select">
            <span>选择{{ filter.label }}</span>
            <span>⌄</span>
          </button>
        </div>
      </div>

      <div class="staged-sidebar__meta">
        <div><span>仓库容量</span><strong>{{ totalChartCount || demoCharts.length }} / 100</strong></div>
        <div><span>分类数量</span><strong>{{ categoryStates.length }} / 8</strong></div>
        <div><span>已处理</span><strong>{{ finishedChartCount }} / {{ totalChartCount || '—' }}</strong></div>
        <div v-if="failedChartCount"><span>失败</span><strong>{{ failedChartCount }}</strong></div>
      </div>
    </aside>

    <main class="staged-main">
      <header class="staged-tabs" :class="{ 'staged-tabs--pending': !categoryStates.length }">
        <button
          v-for="cat in categoryStates"
          :key="cat.id"
          type="button"
          class="staged-tab"
          :class="{
            active: activeCategoryId === cat.id,
            [`staged-tab--${cat.status}`]: true
          }"
          @click="activeCategoryId = cat.id"
        >
          <span class="staged-tab__tag">{{ categorySourceLabel(cat) }}</span>
          <span class="staged-tab__name">{{ displayName(cat.name) }}</span>
          <span class="staged-tab__count">{{ cat.total || 8 }}</span>
        </button>

        <div class="staged-warehouse">
          <span>仓库</span>
          <strong>{{ totalChartCount || demoCharts.length }}</strong>
        </div>
      </header>

      <section class="staged-canvas">
        <article v-if="!hasChartPlanReady && activeCategory" key="b2" class="staged-question-card staged-question-card--planning">
          <div class="staged-card-head">
            <div>
              <h3>{{ displayName(activeCategory.name) }}问题规划</h3>
              <p>根据分类定义问题数量与问题名称</p>
            </div>
            <span>阶段 B2</span>
          </div>
          <BIThinkingSnippet
            :text="categoryThinkingText || latestMessage"
            :typing="categoryThinkingTyping"
            hint="正在拆解当前分类下应该回答的经营问题"
          />
          <div class="staged-question-layout staged-question-layout--b2">
            <div class="staged-thinking-panel staged-thinking-panel--large">
              <div class="staged-thought-list staged-thought-list--dense">
                <div v-for="item in stageTwoThoughts" :key="item.title" class="staged-thought-item">
                  <span class="staged-thought-dot" />
                  <div>
                    <strong>{{ item.title }}</strong>
                    <p>{{ item.desc }}</p>
                  </div>
                </div>
              </div>
            </div>
            <div class="staged-motion-grid" aria-hidden="true">
              <div class="motion-mini-card">
                <div class="motion-mini-head"><span /> <i /></div>
                <div class="motion-chart motion-chart--bars motion-chart--small">
                  <span v-for="n in 6" :key="n" :style="{ '--i': n }" />
                </div>
              </div>
              <div class="motion-mini-card">
                <div class="motion-mini-head"><span /> <i /></div>
                <div class="motion-ring">
                  <span />
                </div>
              </div>
              <div class="motion-mini-card motion-mini-card--wide">
                <div class="motion-mini-head"><span /> <i /></div>
                <div class="motion-chart motion-chart--line motion-chart--small-line">
                  <i v-for="n in 7" :key="n" :style="{ '--i': n }" />
                </div>
              </div>
            </div>
          </div>
        </article>

        <div v-else key="b3" class="staged-chart-grid">
          <article
            v-for="chart in activeCharts"
            :key="chart.id"
            class="staged-chart"
            :class="[
              `staged-chart--${chart.status}`,
              { 'staged-chart--full': chart.status === 'completed' && isExpandedChart(chart.id) }
            ]"
          >
            <header class="staged-chart__head">
              <div>
                <h3>{{ chart.title }}</h3>
                <p>{{ renderChartById[chart.id]?.question || chart.question || '正在生成问题描述…' }}</p>
              </div>
              <span>{{ chartStatusLabel(chart.status) }}</span>
            </header>
            <div class="staged-chart__body">
              <BIChartRenderer
                v-if="chart.status === 'completed' && renderChartById[chart.id]"
                :chart="renderChartById[chart.id]"
                :visible="true"
                :expanded="isExpandedChart(chart.id)"
              />
              <template v-else>
                <div class="staged-chart__blank" aria-hidden="true">
                  <span class="staged-chart__blank-axis" />
                  <span class="staged-chart__blank-line staged-chart__blank-line--one" />
                  <span class="staged-chart__blank-line staged-chart__blank-line--two" />
                  <span class="staged-chart__blank-line staged-chart__blank-line--three" />
                </div>
                <BIThinkingSnippet
                  :text="chartThinkingText(chart)"
                  :typing="chart.status === 'processing'"
                  label="图表与 SQL 判断"
                  compact
                  :show-header="true"
                />
              </template>
            </div>
          </article>

          <article v-if="unfinishedCount > 0" class="staged-chart staged-chart--thinking staged-chart--full">
            <header class="staged-chart__head">
              <div>
                <h3>并行生成中</h3>
                <p>继续判断剩余问题的图表类型与 SQL</p>
              </div>
              <span>{{ unfinishedCount }} 个等待</span>
            </header>
            <div class="staged-chart__body staged-chart__body--thinking">
              <BIThinkingSnippet
                :text="categoryThinkingText"
                :typing="true"
                hint="做完一个图表就展示一个，剩余图表保持空白占位"
              />
            </div>
          </article>
        </div>
      </section>
    </main>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { BIProgressEvent } from '../../api'
import { useBiGenerationProgress } from '../../composables/useBiGenerationProgress'
import { createDemoBIConfig } from '../../mocks/demoBIConfig'
import BIThinkingSnippet from './BIThinkingSnippet.vue'
import BIChartRenderer from './BIChartRenderer.vue'

const props = defineProps<{
  events: BIProgressEvent[]
  generationStartedAt?: string
}>()

const {
  categoryStates,
  chartsByCategory,
  totalChartCount,
  failedChartCount,
  finishedChartCount,
  latestMessage,
  hasChartPlanReady,
  displayName,
  events,
} = useBiGenerationProgress(computed(() => props.events))

const activeCategoryId = ref('')
const demoConfig = createDemoBIConfig()
const demoCharts = demoConfig.charts || []

const activeCategory = computed(() =>
  categoryStates.value.find((c) => c.id === activeCategoryId.value)
)

const activeCharts = computed(() => chartsByCategory.value[activeCategoryId.value] || [])

const demoChartById = computed<Record<string, any>>(() =>
  Object.fromEntries(demoCharts.map((chart: any) => [chart.id, normalizeDemoChart(chart)]))
)

const renderChartById = computed<Record<string, any>>(() => {
  const map: Record<string, any> = { ...demoChartById.value }
  for (const chart of activeCharts.value) {
    if (chart.chart) {
      map[chart.id] = normalizeDemoChart(chart.chart)
    }
  }
  return map
})

const globalFilters = computed(() => {
  const event = [...events.value].reverse().find((item) => Array.isArray(item.global_filters))
  return (event?.global_filters?.length ? event.global_filters : demoConfig.global_filters).map((filter: any) => ({
    field: filter.field || filter.canonical_key,
    label: filter.label || filter.field || filter.canonical_key,
  }))
})

const unfinishedCount = computed(() =>
  activeCharts.value.filter((chart) => chart.status !== 'completed').length
)

const stageOneThoughts = [
  { title: '读取工作簿结构', desc: '确认销售明细、产品、客户、目标等 Sheet 的业务边界。' },
  { title: '抽取公共筛选', desc: '优先选择区域、产品类别、客户等级这类可跨图表复用的字段。' },
  { title: '合并关联线索', desc: '参考表理解与关联总结，判断哪些分类可以直接进入看板。' },
]

function cleanTableName(value?: string) {
  return (value || '').replace(/^admin_\d+_/, '') || '当前主表'
}

function relatedTableText(category: { relatedTables?: string[]; tableName?: string }) {
  const tables = (category.relatedTables || []).map(cleanTableName).filter(Boolean)
  if (tables.length) return tables.slice(0, 3).join('、')
  return cleanTableName(category.tableName)
}

function categoryFallbackThinking(category: NonNullable<typeof activeCategory.value>) {
  const name = displayName(category.name)
  const table = cleanTableName(category.tableName)
  const related = relatedTableText(category)
  if (category.source === 'custom') {
    return `正在围绕「${name}」拆解跨表经营问题：先确认 ${related} 之间的关联视角，再把问题收敛到总览、趋势、结构、贡献和异常识别这些可落到图表的方向。`
  }
  return `正在围绕「${name}」拆解单表经营问题：先读取 ${table} 的字段粒度与业务含义，再筛出可以聚合、对比、排名、趋势化或展示明细的问题名称。`
}

const stageTwoThoughts = computed(() => {
  const category = activeCategory.value
  const name = displayName(category?.name || '当前分类')
  const desc = category?.description || ''
  const table = cleanTableName(category?.tableName)
  const related = category ? relatedTableText(category) : table
  if (category?.source === 'custom') {
    return [
      { title: `识别${name}主题`, desc: desc || `把 ${related} 的关联线索收拢到「${name}」这个经营视角。` },
      { title: `确定${name}主表`, desc: `MVP 先为「${name}」选择最稳的主表落点，再把关联表字段作为解释和筛选依据。` },
      { title: `拆解${name}问题`, desc: `优先生成「${name}」下的总览、结构、趋势、贡献和异常识别问题。` },
      { title: `保留${name}关联`, desc: `问题名称需要体现 ${related} 的业务关系，避免只复述单个字段。` },
      { title: `控制${name}密度`, desc: `根据「${name}」可用字段和关联强度生成 6 到 8 个问题，信息不足时主动减少。` },
    ]
  }
  return [
    { title: `读取${name}语义`, desc: desc || `根据 ${table} 的字段、粒度和表理解确定「${name}」的问题边界。` },
    { title: `筛选${name}问题`, desc: `只保留能基于 ${table} 直接聚合、对比、排名、趋势化或展示明细的问题。` },
    { title: `匹配${name}优先级`, desc: `把「${name}」里最能代表经营状态、用户最常查看的指标放在前面。` },
    { title: `避免${name}堆字段`, desc: `问题名称要表达「${name}」的业务目标，而不是简单排列 ${table} 的字段名。` },
    { title: `控制${name}数量`, desc: `根据「${name}」字段丰富度生成 6 到 8 个问题，字段较少时减少占位。` },
  ]
})

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

const streamThinkingByCategory = computed(() => {
  const map: Record<string, string> = {}
  for (const event of events.value) {
    if (event.step !== 'thinking_entry' || !event.entry?.text) continue
    if (event.entry.category_id) {
      map[event.entry.category_id] = event.entry.text
      continue
    }
    const catName = event.entry.category_name || event.entry.sheet_name || event.category_name
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
  if (activeCategory.value) {
    return categoryFallbackThinking(activeCategory.value)
  }
  return globalThinkingText.value || latestMessage.value || '正在分析数据表结构与业务含义…'
})

const categoryThinkingTyping = computed(() => {
  const cat = activeCategory.value
  return cat?.status === 'planning' || cat?.status === 'processing' || !hasChartPlanReady.value
})

function chartThinkingText(chart: { status: string; title: string; message?: string }) {
  if (chart.status === 'failed') return chart.message || '图表生成失败'
  if (chart.status === 'processing') {
    const evt = [...events.value].reverse().find((e) => e.step === 'chart_start' && e.title === chart.title)
    return evt?.message || `正在生成「${chart.title}」的图表类型与 SQL…`
  }
  return `等待判断「${chart.title}」应该使用哪类图表，并生成对应 SQL。`
}

function chartStatusLabel(status: string) {
  if (status === 'completed') return '完成'
  if (status === 'failed') return '失败'
  if (status === 'processing') return '生成中'
  return '占位'
}

function categorySourceLabel(category: { name: string; source?: string }) {
  return category.source === 'custom' ? '自定义' : 'Sheet'
}

function normalizeDemoChart(chart: any) {
  return {
    id: chart.id,
    categoryId: chart.category_id || chart.categoryId,
    title: chart.title,
    question: chart.question || chart.description || '',
    chartType: chart.chart_type || chart.chartType || 'table',
    sql: chart.sql || '',
    onBoard: true,
    collapsed: false,
    expanded: chart.expanded ?? true,
    boardOrder: chart.board_order ?? chart.boardOrder ?? 0,
    chartFilters: {},
    encoding: chart.encoding || {},
    items: chart.items || [],
    layout: chart.layout || {},
    tablePreview: chart.tablePreview || chart.preview || { columns: [], rows: [] },
    chartMock: chart.chartMock || {},
  }
}

function isExpandedChart(id: string) {
  return renderChartById.value[id]?.expanded !== false
}

</script>

<style scoped>
.staged-board {
  --bi-accent: #C6613F;
  --bi-accent-hover: #A84F33;
  --bi-bg: #F4F1EA;
  --bi-surface: #FDFBF8;
  --bi-surface-muted: #F8F4EE;
  --bi-border: #E8E1D8;
  --bi-border-strong: #D8CEC2;
  --bi-text: #1F1A17;
  --bi-muted: #736A61;
  --bi-faint: #A39B92;

  display: flex;
  height: calc(100vh - var(--header-height, 52px) - 20px);
  min-height: 0;
  color: var(--bi-text);
  background: var(--bi-bg);
}

.staged-intro {
  flex: 1;
  min-width: 0;
  min-height: 100%;
  padding: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.staged-intro .staged-question-card {
  width: min(1120px, 100%);
  min-height: 560px;
  animation: intro-card-in 0.38s ease both;
}

.staged-sidebar {
  width: 252px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 18px 16px;
  overflow-y: auto;
  background: rgba(253, 251, 248, 0.74);
  border-right: 1px solid var(--bi-border);
}

.staged-sidebar__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.staged-sidebar__head h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.staged-sidebar__head span,
.staged-sidebar__hint {
  font-size: 11px;
  color: var(--bi-faint);
}

.staged-sidebar__hint {
  margin: 0 0 16px;
  line-height: 1.45;
}

.staged-filter-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.staged-filter {
  padding: 10px;
  background: rgba(255, 255, 255, 0.54);
  border: 1px solid rgba(232, 225, 216, 0.78);
  border-radius: 8px;
}

.staged-filter label {
  display: block;
  margin-bottom: 6px;
  color: var(--bi-muted);
  font-size: 12px;
  font-weight: 500;
}

.staged-select {
  width: 100%;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border: 1px solid var(--bi-border);
  border-radius: 8px;
  background: var(--bi-surface);
  color: #A6A098;
  font: inherit;
  cursor: default;
}

.staged-sidebar__meta {
  margin-top: auto;
  padding-top: 20px;
  border-top: 1px solid var(--bi-border);
}

.staged-sidebar__meta div {
  display: flex;
  justify-content: space-between;
  padding: 7px 0;
  border-bottom: 1px solid rgba(232, 225, 216, 0.58);
  font-size: 12px;
}

.staged-sidebar__meta span {
  color: var(--bi-muted);
}

.staged-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.staged-tabs {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 17px 18px 12px;
  overflow: hidden;
  background: rgba(253, 251, 248, 0.88);
  border-bottom: 1px solid var(--bi-border);
}

.staged-tabs--pending {
  min-height: 69px;
}

.staged-tab {
  position: relative;
  flex: 1 1 0;
  min-width: 92px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px 9px 6px;
  border: 1px solid var(--bi-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.52);
  color: var(--bi-muted);
  font: inherit;
  cursor: pointer;
}

.staged-tab.active {
  background: #FFF8F4;
  border-color: rgba(198, 97, 63, 0.42);
  color: var(--bi-accent-hover);
  box-shadow: inset 0 -2px 0 rgba(198, 97, 63, 0.24);
}

.staged-tab--completed.active {
  background: rgba(45, 138, 86, 0.08);
  border-color: rgba(45, 138, 86, 0.35);
}

.staged-tab__tag {
  position: absolute;
  top: -7px;
  left: 6px;
  padding: 2px 5px;
  border: 1px solid rgba(78, 109, 128, 0.22);
  border-radius: 6px;
  background: rgba(78, 109, 128, 0.1);
  color: #4E6D80;
  font-size: 9px;
  font-weight: 600;
  line-height: 1;
}

.staged-tab__name {
  max-width: 58px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 12px;
  font-weight: 500;
}

.staged-tab__count,
.staged-warehouse strong {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: rgba(31, 26, 23, 0.06);
  color: var(--bi-muted);
  font-size: 10px;
  line-height: 18px;
  text-align: center;
}

.staged-tab.active .staged-tab__count,
.staged-warehouse strong {
  background: var(--bi-accent);
  color: #fff;
}

.staged-warehouse {
  flex-shrink: 0;
  height: 36px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  border: 1px solid var(--bi-border);
  border-radius: 8px;
  background: var(--bi-surface);
  font-size: 13px;
  font-weight: 500;
}

.staged-canvas {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px;
}

.staged-question-card,
.staged-chart {
  background: var(--bi-surface);
  border: 1px solid var(--bi-border);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(28, 25, 23, 0.04);
}

.staged-question-card {
  min-height: 520px;
  padding: 28px;
}

.staged-question-card--intro,
.staged-question-card--planning {
  min-height: calc(100vh - var(--header-height, 52px) - 132px);
}

.staged-card-head,
.staged-chart__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.staged-card-head {
  margin-bottom: 22px;
}

.staged-card-head h3,
.staged-chart__head h3 {
  margin: 0 0 6px;
  color: var(--bi-text);
  font-size: 16px;
  font-weight: 600;
}

.staged-card-head p,
.staged-chart__head p {
  margin: 0;
  color: var(--bi-muted);
  font-size: 12px;
  line-height: 1.45;
}

.staged-card-head > span,
.staged-chart__head > span {
  flex-shrink: 0;
  padding: 3px 8px;
  border-radius: 8px;
  background: rgba(198, 97, 63, 0.1);
  color: var(--bi-accent-hover);
  font-size: 11px;
  font-weight: 600;
}

.staged-question-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.95fr);
  gap: 22px;
  align-items: stretch;
  margin-top: 18px;
}

.staged-question-layout--b2 {
  margin-top: 20px;
  grid-template-columns: minmax(420px, 0.94fr) minmax(460px, 1.06fr);
}

.staged-thinking-panel {
  min-height: 360px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 18px;
  border: 1px solid rgba(232, 225, 216, 0.86);
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.7), rgba(248, 244, 238, 0.8));
}

.staged-thinking-panel--large {
  min-height: 330px;
}

.staged-thought-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  margin-top: auto;
}

.staged-thought-list--dense {
  gap: 10px;
  margin-top: 0;
}

.staged-thought-item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(232, 225, 216, 0.72);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.58);
}

.staged-thought-dot {
  width: 7px;
  height: 7px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--bi-accent);
  box-shadow: 0 0 0 6px rgba(198, 97, 63, 0.1);
  animation: thought-dot 1.5s ease infinite;
}

.staged-thought-item strong {
  display: block;
  margin-bottom: 4px;
  color: var(--bi-text);
  font-size: 13px;
  font-weight: 600;
}

.staged-thought-item p {
  margin: 0;
  color: var(--bi-muted);
  font-size: 12px;
  line-height: 1.55;
}

.staged-motion-panel,
.staged-motion-grid {
  min-height: 360px;
  border: 1px solid rgba(232, 225, 216, 0.86);
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(253, 251, 248, 0.82), rgba(248, 244, 238, 0.72)),
    repeating-linear-gradient(to bottom, transparent 0, transparent 43px, rgba(232, 225, 216, 0.52) 44px);
  overflow: hidden;
}

.staged-motion-panel {
  position: relative;
  padding: 26px;
}

.staged-motion-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  padding: 14px;
}

.motion-chart--bars {
  position: absolute;
  left: 30px;
  right: 30px;
  bottom: 42px;
  height: 180px;
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  gap: 12px;
}

.motion-chart--bars span {
  flex: 1;
  max-width: 42px;
  height: calc(34px + var(--i) * 13px);
  border-radius: 8px 8px 0 0;
  background: linear-gradient(180deg, rgba(217, 119, 87, 0.92), rgba(198, 97, 63, 0.62));
  transform-origin: bottom;
  animation: bar-jump 2.2s ease-in-out infinite;
  animation-delay: calc(var(--i) * -0.19s);
}

.motion-chart--line {
  position: absolute;
  left: 54px;
  right: 54px;
  top: 54px;
  height: 116px;
}

.motion-chart--line i {
  position: absolute;
  left: calc((var(--i) - 1) * 17%);
  top: calc(54px - var(--i) * 5px);
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: #4E6D80;
  box-shadow: 0 0 0 5px rgba(78, 109, 128, 0.12);
  animation: point-float 2.4s ease-in-out infinite;
  animation-delay: calc(var(--i) * -0.21s);
}

.motion-chart--line::before {
  content: '';
  position: absolute;
  left: 6px;
  right: 8px;
  top: 58px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, #4E6D80, rgba(78, 109, 128, 0.18));
  transform: rotate(-8deg);
}

.motion-chip-row {
  position: absolute;
  left: 26px;
  right: 26px;
  top: 26px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.motion-chip-row span {
  padding: 5px 9px;
  border: 1px solid rgba(78, 109, 128, 0.2);
  border-radius: 8px;
  background: rgba(78, 109, 128, 0.08);
  color: #4E6D80;
  font-size: 11px;
  font-weight: 600;
}

.motion-mini-card {
  position: relative;
  min-height: 152px;
  padding: 14px;
  border: 1px solid rgba(232, 225, 216, 0.78);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.56);
  overflow: hidden;
}

.motion-mini-card--wide {
  grid-column: 1 / -1;
  min-height: 168px;
}

.motion-mini-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.motion-mini-head span {
  width: 92px;
  height: 10px;
  border-radius: 999px;
  background: rgba(31, 26, 23, 0.12);
}

.motion-mini-head i {
  width: 28px;
  height: 10px;
  border-radius: 999px;
  background: rgba(198, 97, 63, 0.18);
}

.motion-chart--small {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 18px;
  height: 94px;
}

.motion-chart--small span {
  max-width: 24px;
}

.motion-chart--small-line {
  left: 28px;
  right: 28px;
  top: 50px;
  height: 90px;
}

.motion-ring {
  position: absolute;
  inset: 46px 0 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.motion-ring span {
  width: 86px;
  height: 86px;
  border-radius: 50%;
  background:
    conic-gradient(from 0deg, #D97757 0 34%, #5470C6 34% 62%, #91CC75 62% 82%, #FAC858 82% 100%);
  -webkit-mask: radial-gradient(circle, transparent 0 44%, #000 45%);
  mask: radial-gradient(circle, transparent 0 44%, #000 45%);
  animation: ring-turn 4s linear infinite;
}

@keyframes thought-dot {
  0%, 100% { transform: scale(0.9); opacity: 0.68; }
  50% { transform: scale(1.14); opacity: 1; }
}

@keyframes bar-jump {
  0%, 100% { transform: scaleY(0.72); opacity: 0.72; }
  35% { transform: scaleY(1.08); opacity: 1; }
  70% { transform: scaleY(0.88); opacity: 0.84; }
}

@keyframes point-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-16px); }
}

@keyframes ring-turn {
  to { transform: rotate(360deg); }
}

@keyframes intro-card-in {
  from {
    opacity: 0;
    transform: translateY(10px);
    filter: blur(2px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
    filter: blur(0);
  }
}

.staged-chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  align-content: start;
}

.staged-chart {
  min-width: 0;
  overflow: hidden;
}

.staged-chart--full {
  grid-column: 1 / -1;
}

.staged-chart--processing {
  border-color: rgba(198, 97, 63, 0.34);
}

.staged-chart--completed {
  border-color: rgba(45, 138, 86, 0.26);
}

.staged-chart__head {
  min-height: 64px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--bi-border);
  background: var(--bi-surface-muted);
}

.staged-chart__body {
  min-height: 246px;
  padding: 14px;
}

.staged-chart--full .staged-chart__body {
  min-height: 300px;
}

.staged-chart__blank {
  position: relative;
  height: 138px;
  margin-bottom: 12px;
  border: 1px dashed var(--bi-border-strong);
  border-radius: 8px;
  background:
    linear-gradient(to right, transparent 0, transparent 18%, rgba(232, 225, 216, 0.55) 18.5%, transparent 19%),
    repeating-linear-gradient(to bottom, transparent 0, transparent 33px, rgba(232, 225, 216, 0.54) 34px);
}

.staged-chart__blank-axis {
  position: absolute;
  left: 28px;
  right: 18px;
  bottom: 24px;
  height: 1px;
  background: #B9B0A6;
}

.staged-chart__blank-line {
  position: absolute;
  left: 56px;
  bottom: 36px;
  width: 54px;
  height: 44px;
  border-radius: 8px 8px 0 0;
  background: rgba(198, 97, 63, 0.18);
  animation: staged-pulse 1.4s ease infinite;
}

.staged-chart__blank-line--two {
  left: 134px;
  height: 76px;
  animation-delay: 0.12s;
}

.staged-chart__blank-line--three {
  left: 212px;
  height: 58px;
  animation-delay: 0.24s;
}

.staged-chart__body--thinking {
  min-height: 120px;
}

@keyframes staged-pulse {
  0%, 100% { opacity: 0.45; }
  50% { opacity: 0.92; }
}

@media (max-width: 900px) {
  .staged-board {
    flex-direction: column;
    height: auto;
    min-height: calc(100vh - var(--header-height, 52px) - 20px);
  }

  .staged-sidebar {
    width: auto;
    border-right: 0;
    border-bottom: 1px solid var(--bi-border);
  }

  .staged-tabs {
    overflow-x: auto;
  }

  .staged-tab {
    flex: 0 0 108px;
  }

  .staged-chart-grid {
    grid-template-columns: 1fr;
  }

  .staged-question-layout,
  .staged-question-layout--b2 {
    grid-template-columns: 1fr;
  }

  .staged-chart--full {
    grid-column: auto;
  }
}
</style>
