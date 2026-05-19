<template>
  <div class="insights-board">
    <!-- 左侧：全局筛选 -->
    <aside class="insights-sidebar">
      <div class="sidebar-head">
        <h2 class="sidebar-title">全局筛选</h2>
        <button
          v-if="hasActiveFilters"
          type="button"
          class="link-clear"
          @click="clearFilters"
        >
          清除
        </button>
      </div>
      <p class="sidebar-hint">筛选将作用于当前看板内所有适用图表，单图筛选优先于全局筛选。</p>
      <div class="filter-list">
        <div v-for="f in globalFilters" :key="f.field" class="filter-item">
          <label class="filter-label">{{ f.label }}</label>
          <el-select
            v-model="filterValues[f.field]"
            :placeholder="`选择${f.label}`"
            clearable
            size="default"
            class="filter-select"
          >
            <el-option
              v-for="opt in f.options"
              :key="opt"
              :label="opt"
              :value="opt"
            />
          </el-select>
        </div>
      </div>

      <div class="sidebar-meta">
        <div class="meta-row">
          <span class="meta-label">仓库容量</span>
          <span class="meta-value">{{ charts.length }} / {{ maxWarehouse }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">分类数量</span>
          <span class="meta-value">{{ categories.length }} / {{ maxCategoriesTotal }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">当前分类展示</span>
          <span class="meta-value">{{ boardCharts.length }} / {{ maxPerCategory }}</span>
        </div>
      </div>
    </aside>

    <!-- 右侧主区 -->
    <div class="insights-main">
      <!-- 顶栏：分类切换 + 仓库 -->
      <header class="insights-topbar">
        <div class="category-tabs">
          <button
            v-for="cat in categories"
            :key="cat.id"
            type="button"
            class="category-tab"
            :class="{
              active: activeCategoryId === cat.id,
              'category-tab--sheet': cat.source === 'sheet',
              'category-tab--custom': cat.source === 'custom'
            }"
            :title="cat.source === 'custom' ? `${cat.name}（双击编辑名称）` : cat.name"
            @click="activeCategoryId = cat.id"
            @dblclick="cat.source === 'custom' && handleRenameCategory(cat)"
          >
            <span
              class="tab-float-tag"
              :class="cat.source === 'sheet' ? 'tab-float-tag--sheet' : 'tab-float-tag--custom'"
            >
              {{ cat.source === 'sheet' ? 'Sheet' : '自定义' }}
            </span>
            <span
              v-if="cat.source === 'custom'"
              class="tab-float-delete"
              role="button"
              tabindex="0"
              aria-label="删除分类"
              @click.stop="handleDeleteCategory(cat)"
              @keydown.enter.stop.prevent="handleDeleteCategory(cat)"
            >
              <el-icon><Close /></el-icon>
            </span>
            <span class="tab-body">
              <span class="tab-name">{{ displayTabName(cat.name) }}</span>
              <span class="tab-count">{{ boardCountByCategory[cat.id] || 0 }}</span>
            </span>
          </button>
          <button
            v-if="canAddCategory"
            type="button"
            class="category-tab category-tab--add"
            title="添加自定义分类"
            @click="handleAddCategory"
          >
            <el-icon class="tab-add-icon"><Plus /></el-icon>
            <span class="tab-add-label">添加</span>
          </button>
        </div>
        <button type="button" class="btn-warehouse" @click="warehouseVisible = true">
          <el-icon><Box /></el-icon>
          <span>仓库</span>
          <span class="warehouse-badge">{{ charts.length }}</span>
        </button>
      </header>

      <!-- 图表区 -->
      <div class="insights-canvas">
        <div v-if="boardCharts.length === 0" class="canvas-empty">
          <p class="empty-title">当前分类暂无展示图表</p>
          <p class="empty-desc">从右上角「仓库」添加图表，或切换其他分类</p>
          <button type="button" class="btn-outline" @click="warehouseVisible = true">打开仓库</button>
        </div>

        <div
          v-else
          class="chart-grid"
          @dragover.prevent="onGridDragOver"
        >
          <div
            v-for="(chart, idx) in boardCharts"
            :key="chart.id"
            class="chart-grid__item"
            :class="{
              'chart-grid__item--full': chart.expanded,
              'chart-grid__item--drag-over': dragOverIndex === idx
            }"
            @dragover.prevent="onItemDragOver(idx)"
            @dragleave="onItemDragLeave"
            @drop.prevent="onItemDrop(idx)"
          >
            <BIChartCard
              :chart="chart"
              :global-filter-fields="globalFilters"
              :global-filter-values="filterValues"
              :is-dragging="draggingId === chart.id"
              @toggle-collapse="toggleCollapse"
              @toggle-expand="toggleExpand"
              @move-to-warehouse="moveToWarehouse"
              @update-chart-filters="updateChartFilters"
              @update-kpi-items="updateKpiItems"
              @dragstart="onCardDragStart"
              @dragend="onCardDragEnd"
            />
          </div>
        </div>

        <p v-if="boardAtLimit" class="limit-hint">
          该分类已达展示上限（{{ maxPerCategory }} 个），请先从看板移出或删除图表后再添加。
        </p>
      </div>
    </div>

    <BIWarehouseModal
      :visible="warehouseVisible"
      :file-id="fileId"
      :charts="charts"
      :categories="categories"
      :dev-mode="devMode"
      :board-count-by-category="boardCountByCategory"
      @close="warehouseVisible = false"
      @delete="deleteChart"
      @add-to-board="addToBoard"
      @remove-from-board="moveToWarehouse"
      @chart-updated="applyChartEdit"
      @update:dev-mode="devMode = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Box, Plus, Close } from '@element-plus/icons-vue'
import {
  BI_MAX_BOARD_PER_CATEGORY,
  BI_MAX_WAREHOUSE_TOTAL,
  BI_MAX_CUSTOM_CATEGORIES,
  BI_MAX_CATEGORIES_TOTAL,
  type BIChartItem,
  type BICategory,
  type BIGlobalFilterField
} from '../../mocks/biInsightsMock'
import { createBICategory, deleteBICategory, getBIChartData, updateBICategory, updateBIChart } from '../../api'
import BIChartCard from './BIChartCard.vue'
import BIWarehouseModal, { type BIChartEditPayload } from './BIWarehouseModal.vue'

const props = defineProps<{
  fileId: string
  config: any
}>()

const categories = ref<BICategory[]>([])
const charts = ref<BIChartItem[]>([])
const globalFilters = ref<BIGlobalFilterField[]>([])

const activeCategoryId = ref('')
const warehouseVisible = ref(false)
const devMode = ref(false)
const filterValues = reactive<Record<string, string>>({})

const maxPerCategory = BI_MAX_BOARD_PER_CATEGORY
const maxWarehouse = BI_MAX_WAREHOUSE_TOTAL
const maxCategoriesTotal = BI_MAX_CATEGORIES_TOTAL

const customCategoryCount = computed(
  () => categories.value.filter((c) => c.source === 'custom').length
)

const canAddCategory = computed(
  () =>
    categories.value.length < maxCategoriesTotal &&
    customCategoryCount.value < BI_MAX_CUSTOM_CATEGORIES
)

const boardCountByCategory = computed(() => {
  const counts: Record<string, number> = {}
  for (const c of charts.value) {
    // kpi_group 不计入分类数量统计
    if (c.onBoard && c.chartType !== 'kpi_group') {
      counts[c.categoryId] = (counts[c.categoryId] || 0) + 1
    }
  }
  return counts
})

const boardCharts = computed(() =>
  charts.value
    .filter((c) => c.onBoard && c.categoryId === activeCategoryId.value)
    .sort((a, b) => (a.boardOrder ?? 0) - (b.boardOrder ?? 0))
)

const draggingId = ref<string | null>(null)
const dragOverIndex = ref<number | null>(null)

const boardAtLimit = computed(
  () => (boardCountByCategory.value[activeCategoryId.value] || 0) >= maxPerCategory
)

const hasActiveFilters = computed(() =>
  Object.values(filterValues).some((v) => v !== undefined && v !== null && v !== '')
)

const TAB_NAME_MAX_LEN = 4

function displayTabName(name: string) {
  return [...name].slice(0, TAB_NAME_MAX_LEN).join('')
}

function clearFilters() {
  Object.keys(filterValues).forEach((k) => {
    filterValues[k] = ''
  })
  refreshBoardCharts()
}

async function handleAddCategory() {
  if (!canAddCategory.value) {
    ElMessage.warning(
      customCategoryCount.value >= BI_MAX_CUSTOM_CATEGORIES
        ? `自定义分类已满（最多 ${BI_MAX_CUSTOM_CATEGORIES} 个）`
        : `分类已满（最多 ${maxCategoriesTotal} 个）`
    )
    return
  }
  try {
    const { value } = await ElMessageBox.prompt(
      '为看板新增一个自定义分类，可将图表归类到该 Tab 下。',
      '添加自定义分类',
      {
        confirmButtonText: '添加',
        cancelButtonText: '取消',
        inputPlaceholder: '最多 4 个字，如：专题分析',
        inputPattern: /^.{1,4}$/,
        inputErrorMessage: '分类名称最多 4 个字'
      }
    )
    const name = displayTabName(value.trim())
    const { data } = await createBICategory(props.fileId, name)
    const saved = data.data
    categories.value.push({
      id: saved.id,
      name: saved.display_name || saved.name,
      icon: 'chart',
      source: 'custom'
    })
    activeCategoryId.value = saved.id
    ElMessage.success(`已添加分类「${name}」`)
  } catch {
    /* 用户取消 */
  }
}

async function handleRenameCategory(cat: BICategory) {
  if (cat.source !== 'custom') return
  try {
    const { value } = await ElMessageBox.prompt('修改自定义分类名称。', '编辑分类', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: cat.name,
      inputPattern: /^.{1,4}$/,
      inputErrorMessage: '分类名称最多 4 个字'
    })
    const name = displayTabName(value.trim())
    const { data } = await updateBICategory(props.fileId, cat.id, name)
    cat.name = data.data.display_name || data.data.name || name
    ElMessage.success('已保存')
  } catch {
    /* 用户取消 */
  }
}

async function handleDeleteCategory(cat: BICategory) {
  if (cat.source !== 'custom') return
  const related = charts.value.filter((c) => c.categoryId === cat.id)
  const fallback = categories.value.find((c) => c.source === 'sheet')
  const fallbackLabel = fallback ? displayTabName(fallback.name) : '默认'
  const msg =
    related.length > 0
      ? `该分类下有 ${related.length} 个图表，删除后将归入「${fallbackLabel}」分类。`
      : '确定删除此自定义分类？'
  try {
    await ElMessageBox.confirm(msg, '删除分类', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteBICategory(props.fileId, cat.id)
    if (fallback) {
      for (const c of related) c.categoryId = fallback.id
    }
    categories.value = categories.value.filter((c) => c.id !== cat.id)
    if (activeCategoryId.value === cat.id) {
      activeCategoryId.value = categories.value[0]?.id || ''
    }
    ElMessage.success('已删除分类')
  } catch {
    /* 用户取消 */
  }
}

function toggleCollapse(id: string) {
  const c = charts.value.find((x) => x.id === id)
  if (c) c.collapsed = !c.collapsed
}

function moveToWarehouse(id: string) {
  const c = charts.value.find((x) => x.id === id)
  if (c) {
    c.onBoard = false
    ElMessage.success('已移入仓库')
  }
}

function toggleExpand(id: string) {
  const c = charts.value.find((x) => x.id === id)
  if (c) c.expanded = !c.expanded
}

function updateChartFilters(id: string, filters: Record<string, string>) {
  const c = charts.value.find((x) => x.id === id)
  if (c) {
    c.chartFilters = { ...filters }
    refreshChartData(c)
  }
}

async function updateKpiItems(id: string, items: Array<{ label: string; value_field: string; format?: string }>) {
  const c = charts.value.find((x) => x.id === id)
  if (!c) return
  const previous = c.items ? c.items.map((item) => ({ ...item })) : []
  c.items = items
  try {
    await updateBIChart(props.fileId, id, {
      title: c.title,
      description: c.question,
      category_id: c.categoryId,
      items,
      encoding: c.encoding,
      layout: c.layout
    })
    ElMessage.success('已保存指标卡片')
  } catch (e: any) {
    c.items = previous
    ElMessage.error(e.response?.data?.detail || e.message || '保存指标卡片失败')
  }
}

function onCardDragStart(id: string, e: DragEvent) {
  draggingId.value = id
  e.dataTransfer?.setData('text/plain', id)
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}

function onCardDragEnd() {
  draggingId.value = null
  dragOverIndex.value = null
}

function onGridDragOver(e: DragEvent) {
  e.dataTransfer!.dropEffect = 'move'
}

function onItemDragOver(index: number) {
  dragOverIndex.value = index
}

function onItemDragLeave() {
  dragOverIndex.value = null
}

function onItemDrop(targetIndex: number) {
  const sourceId = draggingId.value
  dragOverIndex.value = null
  if (!sourceId) return

  const list = boardCharts.value
  const sourceIndex = list.findIndex((c) => c.id === sourceId)
  if (sourceIndex === -1 || sourceIndex === targetIndex) return

  const reordered = [...list]
  const [moved] = reordered.splice(sourceIndex, 1)
  reordered.splice(targetIndex, 0, moved)
  reordered.forEach((c, i) => {
    const item = charts.value.find((x) => x.id === c.id)
    if (item) item.boardOrder = i
  })
}

function applyChartEdit(payload: BIChartEditPayload) {
  const c = charts.value.find((x) => x.id === payload.id)
  if (!c) return
  c.title = payload.title
  c.question = payload.description
  c.categoryId = payload.categoryId
}

function addToBoard(id: string) {
  const c = charts.value.find((x) => x.id === id)
  if (!c) return
  const count = boardCountByCategory.value[c.categoryId] || 0
  if (count >= maxPerCategory) {
    ElMessage.warning(`该分类看板最多展示 ${maxPerCategory} 个图表`)
    return
  }
  c.onBoard = true
  activeCategoryId.value = c.categoryId
  ElMessage.success('已添加到看板')
}

async function deleteChart(id: string) {
  try {
    await ElMessageBox.confirm('确定从仓库删除此图表？删除后不可恢复。', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    charts.value = charts.value.filter((c) => c.id !== id)
    ElMessage.success('已删除')
  } catch {
    /* cancel */
  }
}

function normalizeConfig(config: any) {
  const rawCategories = [
    ...(config?.categories || []),
    ...((config?.custom_categories || []).filter((cat: any) =>
      !(config?.categories || []).some((c: any) => c.id === cat.id)
    ))
  ]
  categories.value = rawCategories.map((cat: any, i: number) => ({
    id: cat.id || cat.category_id || cat.name || `category-${i}`,
    name: cat.display_name || cat.name || `分类${i + 1}`,
    icon: cat.icon || (cat.source === 'sheet' ? 'sheet' : 'chart'),
    source: cat.source === 'custom' ? 'custom' : 'sheet',
    sheetKey: cat.sheet_key || cat.sheetKey || cat.table_name
  }))

  const findCategoryId = (chart: any) => {
    const explicit = chart.category_id || chart.categoryId || chart.default_category_id
    if (explicit) return explicit

    const label = chart.category || chart.category_name || chart.categoryName
    const matched = categories.value.find((cat) =>
      cat.id === label ||
      cat.name === label ||
      cat.sheetKey === label
    )
    return matched?.id || categories.value[0]?.id || ''
  }

  charts.value = (config?.charts || []).map((chart: any, i: number) => {
    const preview = chart.preview || chart.tablePreview || { columns: [], rows: [] }
    const categoryId = findCategoryId(chart)
    const chartType = chart.chart_type || chart.chartType || chart.type || 'table'
    return {
      id: chart.id || `chart-${i}`,
      categoryId,
      title: chart.title || '未命名图表',
      question: chart.question || chart.description || '',
      chartType,
      sql: chart.sql || '',
      onBoard: chart.on_board ?? chart.onBoard ?? true,
      collapsed: chart.collapsed ?? false,
      expanded: chart.expanded ?? ['table', 'detail_table', 'bar', 'line', 'combo', 'ranking', 'kpi_group'].includes(chartType),
      boardOrder: chart.board_order ?? chart.boardOrder ?? i,
      chartFilters: chart.chartFilters || {},
      intentType: chart.intent_type || chart.intentType,
      encoding: chart.encoding || {},
      items: chart.items || [],
      layout: chart.layout || {},
      tablePreview: {
        columns: preview.columns || [],
        rows: preview.rows || []
      },
      chartMock: chart.chartMock || buildChartMock(chartType, preview),
      comparison: chart.comparison || {},
    } as BIChartItem & { comparison?: Record<string, any> }
  })

  globalFilters.value = (config?.global_filters || config?.globalFilters || []).map((f: any) => ({
    field: f.field || f.canonical_key,
    label: f.label || f.field || f.canonical_key,
    options: f.options || f.sample_values || []
  })).filter((f: BIGlobalFilterField) => f.field)

  Object.keys(filterValues).forEach((k) => delete filterValues[k])
  activeCategoryId.value = categories.value[0]?.id || ''
}

function buildChartMock(chartType: string, preview: { columns: string[]; rows: Record<string, any>[] }) {
  const columns = preview.columns || []
  const rows = preview.rows || []
  if (!rows.length || columns.length === 0) return {}
  if (chartType === 'kpi' || chartType === 'kpi_group') {
    const value = rows[0]?.[columns[0]]
    return { kpiValue: formatValue(value), kpiSub: '' }
  }
  if (chartType === 'pie') {
    const nameCol = columns[0]
    const valueCol = columns.find((c) => c !== nameCol && rows.some((r) => Number(r[c]) || Number(r[c]) === 0)) || columns[1]
    return {
      pie: rows.map((r) => ({ name: String(r[nameCol]), value: Number(r[valueCol]) || 0 }))
    }
  }
  const xCol = columns[0]
  const yCol = columns.find((c) => c !== xCol && rows.some((r) => Number(r[c]) || Number(r[c]) === 0)) || columns[1]
  return {
    categories: rows.map((r) => String(r[xCol])),
    values: rows.map((r) => Number(r[yCol]) || 0)
  }
}

function formatValue(value: any) {
  const n = Number(value)
  if (!Number.isNaN(n)) return n.toLocaleString('zh-CN')
  return value == null ? '—' : String(value)
}

async function refreshChartData(chart: BIChartItem) {
  try {
    const res = await getBIChartData(
      props.fileId,
      chart.id,
      compactFilters(filterValues),
      compactFilters(chart.chartFilters || {})
    )
    const data = res.data.data
    const rows = data.rows || []
    const columns = rows[0] ? Object.keys(rows[0]) : chart.tablePreview.columns
    chart.tablePreview = { columns, rows }
    chart.chartMock = buildChartMock(chart.chartType, { columns, rows })
    ;(chart as any).comparison = data.comparison || {}
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || `图表「${chart.title}」加载失败`)
  }
}

function refreshBoardCharts() {
  boardCharts.value.forEach((chart) => refreshChartData(chart))
}

function compactFilters(source: Record<string, string>) {
  return Object.fromEntries(
    Object.entries(source).filter(([, value]) => value !== undefined && value !== null && value !== '')
  )
}

watch(
  () => props.config,
  (config) => normalizeConfig(config),
  { immediate: true, deep: true }
)

watch(
  () => ({ ...filterValues }),
  () => refreshBoardCharts(),
  { deep: true }
)
</script>

<style scoped>
.insights-board {
  --bi-accent: #D97757;
  --bi-accent-hover: #C6613F;
  --bi-accent-soft: rgba(217, 119, 87, 0.12);
  --bi-bg: #F5F2EB;
  --bi-surface: #FFFFFF;
  --bi-surface-muted: #FAF8F5;
  --bi-border: #E5E0D8;
  --bi-text: #1C1917;
  --bi-muted: #736C64;
  --bi-faint: #A39E96;

  display: flex;
  height: calc(100vh - var(--header-height, 52px) - 20px);
  min-height: 0;
  gap: 0;
  color: var(--bi-text);
}

/* 左侧筛选 */
.insights-sidebar {
  width: 240px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-right: 1px solid rgba(0, 0, 0, 0.06);
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.sidebar-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}

.link-clear {
  font-size: 12px;
  color: var(--bi-accent);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}

.sidebar-hint {
  font-size: 11px;
  color: var(--bi-faint);
  line-height: 1.45;
  margin: 0 0 16px;
}

.filter-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.filter-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--bi-muted);
  margin-bottom: 6px;
}

.filter-select {
  width: 100%;
}

.insights-sidebar :deep(.el-select__wrapper) {
  border-radius: 10px;
  box-shadow: none;
  border: 1px solid var(--bi-border);
}

.sidebar-meta {
  margin-top: auto;
  padding-top: 20px;
  border-top: 1px solid var(--bi-border);
}

.meta-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 6px 0;
}

.meta-label {
  color: var(--bi-muted);
}

.meta-value {
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

/* 右侧 */
.insights-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bi-bg);
}

.insights-topbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px 10px;
  overflow: visible;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--bi-border);
}

.category-tabs {
  display: flex;
  gap: 8px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  flex-wrap: nowrap;
  padding-top: 6px;
}

.category-tab {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1 1 0;
  min-width: 88px;
  height: 38px;
  padding: 8px 8px 6px;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  color: var(--bi-muted);
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--bi-border);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.category-tab:hover {
  background: #fff;
  color: var(--bi-text);
  border-color: #D4CEC4;
}

.category-tab.active {
  background: var(--bi-accent-soft);
  border-color: rgba(217, 119, 87, 0.45);
  color: var(--bi-accent-hover);
}

.tab-body {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  flex-shrink: 0;
}

.tab-name {
  white-space: nowrap;
  flex-shrink: 0;
  font-size: 13px;
  line-height: 1.2;
  letter-spacing: 0;
}

.tab-count {
  flex-shrink: 0;
  font-size: 10px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  line-height: 18px;
  border-radius: 9px;
  text-align: center;
  background: rgba(28, 25, 23, 0.06);
  color: var(--bi-muted);
  font-variant-numeric: tabular-nums;
}

.category-tab.active .tab-count {
  background: rgba(217, 119, 87, 0.2);
  color: var(--bi-accent-hover);
}

.tab-float-tag {
  position: absolute;
  top: -7px;
  left: 6px;
  z-index: 2;
  font-size: 9px;
  font-weight: 600;
  line-height: 1;
  padding: 2px 5px;
  border-radius: 4px;
  white-space: nowrap;
  pointer-events: none;
  box-shadow: 0 1px 3px rgba(28, 25, 23, 0.08);
}

.tab-float-tag--sheet {
  background: rgba(30, 96, 213, 0.12);
  color: #1E60D5;
  border: 1px solid rgba(30, 96, 213, 0.2);
}

.tab-float-tag--custom {
  background: rgba(217, 119, 87, 0.12);
  color: var(--bi-accent-hover);
  border: 1px solid rgba(217, 119, 87, 0.25);
}

.tab-float-delete {
  position: absolute;
  top: -7px;
  right: -7px;
  z-index: 3;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #fff;
  border: 1px solid var(--bi-border);
  color: var(--bi-muted);
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: 0 1px 3px rgba(28, 25, 23, 0.08);
}

.tab-float-delete:hover {
  color: #FF3B30;
  border-color: rgba(255, 59, 48, 0.35);
  background: rgba(255, 59, 48, 0.08);
}

.tab-float-delete .el-icon {
  font-size: 11px;
}

.category-tab--custom {
  padding-right: 8px;
}

.category-tab--add {
  flex: 0 0 56px;
  max-width: 56px;
  min-width: 56px;
  padding: 0;
  gap: 0;
  border: 1.5px dashed #D4CEC4;
  background: rgba(255, 255, 255, 0.5);
  color: var(--bi-muted);
}

.category-tab--add:hover {
  border-color: var(--bi-accent);
  border-style: dashed;
  color: var(--bi-accent-hover);
  background: var(--bi-accent-soft);
}

.tab-add-icon {
  font-size: 14px;
}

.tab-add-label {
  display: none;
}

.btn-warehouse {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  color: var(--bi-text);
  background: var(--bi-surface);
  border: 1px solid var(--bi-border);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-warehouse:hover {
  border-color: #D4CEC4;
  background: var(--bi-surface-muted);
}

.warehouse-badge {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  font-size: 11px;
  font-weight: 600;
  line-height: 20px;
  text-align: center;
  border-radius: 10px;
  background: var(--bi-accent);
  color: #fff;
}

.insights-canvas {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.canvas-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  text-align: center;
}

.empty-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--bi-muted);
  margin: 0 0 6px;
}

.empty-desc {
  font-size: 13px;
  color: var(--bi-faint);
  margin: 0 0 16px;
}

.btn-outline {
  height: 36px;
  padding: 0 18px;
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  color: var(--bi-accent);
  background: #fff;
  border: 1px solid rgba(217, 119, 87, 0.45);
  border-radius: 10px;
  cursor: pointer;
}

.btn-outline:hover {
  background: var(--bi-accent-soft);
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  align-content: start;
}

.chart-grid__item {
  min-width: 0;
  transition: outline 0.15s ease;
}

.chart-grid__item--full {
  grid-column: 1 / -1;
}

.chart-grid__item--drag-over {
  outline: 2px dashed rgba(217, 119, 87, 0.55);
  outline-offset: 4px;
  border-radius: 16px;
}

@media (max-width: 900px) {
  .chart-grid {
    grid-template-columns: 1fr;
  }
  .chart-grid__item--full {
    grid-column: auto;
  }
}

.limit-hint {
  margin-top: 12px;
  font-size: 12px;
  color: #B45309;
  padding: 10px 12px;
  background: rgba(255, 149, 0, 0.08);
  border-radius: 8px;
}
</style>
