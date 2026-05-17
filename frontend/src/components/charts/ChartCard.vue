<template>
  <div
    class="chart-card glass-card"
    :class="{ 'chart-card--full': isFullWidth, 'chart-card--dragging': isDragging }"
    :draggable="canDrag"
    @dragstart="onDragStart"
    @dragend="onDragEnd"
    @mouseup="canDrag = false"
  >
    <!-- 拖拽手柄 + 标题栏 -->
    <div class="chart-card__header">
      <div class="chart-card__title-group">
        <div class="chart-card__drag-handle" title="拖拽排序" @mousedown="canDrag = true">
          <svg width="12" height="16" viewBox="0 0 12 16" fill="none">
            <circle cx="3" cy="3" r="1.5" fill="currentColor" opacity="0.35"/>
            <circle cx="9" cy="3" r="1.5" fill="currentColor" opacity="0.35"/>
            <circle cx="3" cy="8" r="1.5" fill="currentColor" opacity="0.35"/>
            <circle cx="9" cy="8" r="1.5" fill="currentColor" opacity="0.35"/>
            <circle cx="3" cy="13" r="1.5" fill="currentColor" opacity="0.35"/>
            <circle cx="9" cy="13" r="1.5" fill="currentColor" opacity="0.35"/>
          </svg>
        </div>
        <h4 class="chart-card__title">{{ chart.title }}</h4>
        <span class="chart-card__desc" v-if="chart.description">{{ chart.description }}</span>
      </div>
      <div class="chart-card__actions">
        <!-- 筛选来源指示器 -->
        <div
          class="filter-source-badge"
          :class="filterSourceClass"
          :title="filterSourceTooltip"
        >
          <svg v-if="filterSource === 'individual'" width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M1 3h12M3 7h8M5 11h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <svg v-else-if="filterSource === 'global'" width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.2"/>
            <path d="M1.5 7h11M7 1.5a8 8 0 012.5 5.5A8 8 0 007 12.5a8 8 0 01-2.5-5.5A8 8 0 017 1.5z" stroke="currentColor" stroke-width="1.2"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.2" opacity="0.35"/>
          </svg>
          <span class="filter-source-badge__text">{{ filterSourceLabel }}</span>
        </div>

        <!-- 筛选按钮 -->
        <button
          v-if="hasIndividualFilters"
          class="btn-filter"
          :class="{ 'btn-filter--active': filterVisible }"
          @click="filterVisible = !filterVisible"
        >
          <svg v-if="!filterVisible" width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M1 3h12M3 7h8M5 11h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M1 3h12M3 7h8M5 11h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="2" y1="12" x2="12" y2="2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span>筛选</span>
        </button>
        <!-- 重新生成按钮 + 气泡 -->
        <div class="regenerate-wrapper" ref="regeneratePopoverRef">
          <button
            class="btn-regenerate"
            @click="toggleRegenerate"
            :disabled="regenerateLoading"
            title="重新生成图表"
          >
            <svg :class="{ 'spin': regenerateLoading }" width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 1v2M7 11v2M1 7h2M11 7h2M3.05 3.05l1.41 1.41M9.54 9.54l1.41 1.41M3.05 10.95l1.41-1.41M9.54 4.46l1.41-1.41" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
            </svg>
          </button>
          <Transition name="popover-scale">
            <div v-if="regenerateVisible" class="regenerate-popover">
              <div class="regenerate-popover__header">
                <span class="regenerate-popover__title">重新生成图表</span>
                <button class="regenerate-popover__close" @click="regenerateVisible = false">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                </button>
              </div>
              <div class="regenerate-popover__body">
                <input
                  ref="regenerateInputRef"
                  v-model="regenerateInput"
                  class="regenerate-input"
                  maxlength="50"
                  placeholder="描述你想要的图表样式..."
                  @keydown.enter="submitRegenerate"
                  :disabled="regenerateLoading"
                />
                <div class="regenerate-popover__footer">
                  <span class="regenerate-char-count">{{ regenerateInput.length }}/50</span>
                  <button
                    class="btn-regenerate-submit"
                    @click="submitRegenerate"
                    :disabled="!regenerateInput.trim() || regenerateLoading"
                  >
                    <svg v-if="regenerateLoading" class="spin" width="12" height="12" viewBox="0 0 14 14" fill="none">
                      <path d="M11.5 7A4.5 4.5 0 003 4.5M2.5 7a4.5 4.5 0 008.5 2.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                      <path d="M11.5 2.5v2h-2M2.5 11.5v-2h2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    <span>{{ regenerateLoading ? '生成中...' : '生成' }}</span>
                  </button>
                </div>
              </div>
            </div>
          </Transition>
        </div>
        <!-- 删除按钮 -->
        <button class="btn-delete" @click="$emit('delete', chart.id)" title="删除图表">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2.5 4h9M5 4V2.5a1 1 0 011-1h2a1 1 0 011 1V4M4 6v5a1 1 0 001 1h4a1 1 0 001-1V6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 筛选面板 -->
    <Transition name="filter-slide">
      <div v-if="filterVisible && hasIndividualFilters" class="chart-card__filters">
        <div class="filter-grid">
          <div v-for="filter in chart.filters" :key="filter.field" class="filter-item">
            <label class="filter-label">{{ filter.field }}</label>
            <el-select
              v-model="activeFilters[filter.field]"
              :placeholder="`选择${filter.field}`"
              clearable
              size="small"
            >
              <el-option
                v-for="v in (filter.sample_values || [])"
                :key="v"
                :label="String(v)"
                :value="v"
              />
            </el-select>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 图表内容区 -->
    <div class="chart-card__body">
      <!-- 首次加载骨架屏 -->
      <div v-if="initialLoad && loading" class="chart-loading">
        <el-skeleton animated :rows="3" />
      </div>

      <!-- 错误 -->
      <div v-else-if="error && chartData.length === 0" class="chart-error">
        <span class="chart-error__icon">!</span>
        <span class="chart-error__text">数据加载失败</span>
        <el-button size="small" @click="loadChartData">重试</el-button>
      </div>

      <!-- 图表渲染 -->
      <template v-else>
        <!-- 加载遮罩（筛选变更时显示在已有图表上） -->
        <div v-if="loading && !initialLoad" class="chart-loading-overlay">
          <svg class="spin" width="20" height="20" viewBox="0 0 14 14" fill="none">
            <path d="M11.5 7A4.5 4.5 0 003 4.5M2.5 7a4.5 4.5 0 008.5 2.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M11.5 2.5v2h-2M2.5 11.5v-2h2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>

        <!-- ECharts 图表 -->
        <div
          v-if="['bar','line','pie','funnel','gauge','ranking'].includes(chart.chart_type)"
          ref="chartDomRef"
          class="chart-box"
        ></div>
        <!-- 图表分页 -->
        <div
          v-if="['bar','line','pie','funnel','ranking'].includes(chart.chart_type) && needsPagination"
          class="chart-pagination"
        >
          <el-pagination
            small
            layout="prev, pager, next, total"
            :total="totalRows"
            :page-size="pageSize"
            :current-page="currentPage"
            @current-change="onPageChange"
          />
        </div>

        <!-- 数据表格 -->
        <div v-else-if="chart.chart_type === 'table'" class="table-box">
          <el-table
            :data="chartData"
            stripe
            max-height="400"
            size="small"
            class="apple-table"
          >
            <el-table-column
              v-for="col in tableColumns"
              :key="col"
              :prop="col"
              :label="col"
              show-overflow-tooltip
              sortable
            />
          </el-table>
          <div class="table-footer">
            <span class="table-footer__info">共 {{ totalRows || chartData.length }} 条数据</span>
            <el-pagination
              v-if="needsPagination"
              small
              layout="prev, pager, next, sizes, total"
              :total="totalRows"
              :page-size="pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :current-page="currentPage"
              @current-change="onPageChange"
              @size-change="onPageSizeChange"
            />
          </div>
        </div>

        <!-- 不支持的类型 -->
        <div v-else class="chart-unsupported">
          暂不支持图表类型: {{ chart.chart_type }}
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getBIChartData, regenerateChart } from '../../api'

// ============ Props ============
const props = defineProps<{
  chart: {
    id: string
    chart_type: string
    title: string
    description?: string
    filters?: Array<{ field: string; type: string; sample_values: string[] }>
  }
  fileId: string
  globalFilters?: Record<string, any>
}>()

// ============ Emits ============
const emit = defineEmits<{
  (e: 'delete', chartId: string): void
  (e: 'regenerated', newChart: any): void
  (e: 'dragstart', chartId: string): void
  (e: 'dragend'): void
}>()

// ============ State ============
const loading = ref(true)
const error = ref(false)
const initialLoad = ref(true)
const filterVisible = ref(false)
const activeFilters = ref<Record<string, any>>({})
const chartData = ref<any[]>([])
const bottomData = ref<any[]>([])
const chartDomRef = ref<HTMLElement | null>(null)
const isDragging = ref(false)
const canDrag = ref(false)

// 分页状态
const currentPage = ref(1)
const pageSize = ref(20)
const totalRows = ref(0)

// 重新生成状态
const regenerateVisible = ref(false)
const regenerateInput = ref('')
const regenerateLoading = ref(false)
const regeneratePopoverRef = ref<HTMLElement | null>(null)
const regenerateInputRef = ref<HTMLInputElement | null>(null)

let chartInstance: echarts.ECharts | null = null
let requestId = 0

// ============ Computed ============
const isFullWidth = computed(() =>
  ['table', 'bar', 'line'].includes(props.chart.chart_type)
)

const hasIndividualFilters = computed(() =>
  !!(props.chart.filters && props.chart.filters.length > 0)
)

const tableColumns = computed(() => {
  if (chartData.value.length > 0) {
    return Object.keys(chartData.value[0])
  }
  return []
})

// 分页相关
const needsPagination = computed(() => totalRows.value > pageSize.value)

// 合并后的筛选：全局 + 个别（个别优先级更高），过滤掉空值
const mergedFilters = computed(() => {
  const global = props.globalFilters || {}
  const individual = activeFilters.value
  // 个别筛选覆盖全局筛选
  const merged = { ...global, ...individual }
  // 过滤掉空值（null、undefined、空字符串）
  const result: Record<string, any> = {}
  for (const [key, val] of Object.entries(merged)) {
    if (val !== null && val !== undefined && val !== '') {
      result[key] = val
    }
  }
  return result
})

// 筛选来源判定
const filterSource = computed(() => {
  const hasGlobal = Object.values(props.globalFilters || {}).some(v => v !== null && v !== undefined && v !== '')
  const hasIndividual = Object.values(activeFilters.value).some(v => v !== null && v !== undefined && v !== '')

  if (hasIndividual) return 'individual'
  if (hasGlobal) return 'global'
  return 'none'
})

const filterSourceClass = computed(() => ({
  'filter-source-badge--global': filterSource.value === 'global',
  'filter-source-badge--individual': filterSource.value === 'individual',
  'filter-source-badge--none': filterSource.value === 'none',
}))

const filterSourceLabel = computed(() => {
  switch (filterSource.value) {
    case 'individual': return '单独筛选'
    case 'global': return '全局筛选'
    default: return '无筛选'
  }
})

const filterSourceTooltip = computed(() => {
  switch (filterSource.value) {
    case 'individual': return '当前使用单独筛选（优先于全局）'
    case 'global': return '当前使用全局筛选'
    default: return '未设置筛选条件'
  }
})

// ============ Color Palette ============
const COLORS = ['#5470C6', '#91CC75', '#FAC858', '#EE6666', '#73C0DE', '#3BA272', '#FC8452', '#9A60B4', '#EA7CCC', '#48C9B0']

// ============ Drag & Drop ============
const onDragStart = (e: DragEvent) => {
  if (!canDrag.value) {
    e.preventDefault()
    return
  }
  isDragging.value = true
  e.dataTransfer!.effectAllowed = 'move'
  e.dataTransfer!.setData('text/plain', props.chart.id)
}

const onDragEnd = () => {
  isDragging.value = false
}

// ============ Regenerate ============
const toggleRegenerate = () => {
  regenerateVisible.value = !regenerateVisible.value
  if (regenerateVisible.value) {
    nextTick(() => {
      regenerateInputRef.value?.focus()
    })
  }
}

const submitRegenerate = async () => {
  if (!regenerateInput.value.trim() || regenerateLoading.value) return

  regenerateLoading.value = true
  try {
    const res = await regenerateChart(
      props.fileId,
      props.chart.id,
      regenerateInput.value.trim()
    )
    const newChart = { ...res.data.data.chart, id: props.chart.id }
    regenerateVisible.value = false
    regenerateInput.value = ''
    emit('regenerated', newChart)
  } catch (err: any) {
    console.error('[ChartCard] 图表重新生成失败:', err)
    const msg = err?.response?.data?.detail || '重新生成失败，请重试'
    ElMessage.error(msg)
  } finally {
    regenerateLoading.value = false
  }
}

const onClickOutside = (e: MouseEvent) => {
  if (regenerateVisible.value && regeneratePopoverRef.value) {
    if (!regeneratePopoverRef.value.contains(e.target as Node)) {
      regenerateVisible.value = false
    }
  }
}

// ============ Data Loading ============
const loadChartData = async () => {
  if (!props.fileId || !props.chart.id) return

  // 释放旧的 chart 实例
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }

  loading.value = true
  error.value = false

  const thisRequest = ++requestId

  try {
    const filters = Object.keys(mergedFilters.value).length > 0 ? mergedFilters.value : undefined
    const res = await getBIChartData(
      props.fileId,
      props.chart.id,
      filters,
      undefined,
      currentPage.value,
      pageSize.value
    )

    // 如果已经有更新的请求，忽略本次结果
    if (thisRequest !== requestId) return

    const responseData = res.data
    const innerData = responseData?.data
    const rows = innerData?.rows || []
    chartData.value = rows

    if (innerData?.bottom_rows) {
      bottomData.value = innerData.bottom_rows
    }

    // 更新分页信息
    if (innerData?.total !== undefined) {
      totalRows.value = innerData.total
    }
  } catch (err) {
    if (thisRequest !== requestId) return
    console.error(`[ChartCard] "${props.chart.title}" 数据加载失败:`, err)
    error.value = true
  } finally {
    if (thisRequest === requestId) {
      loading.value = false
      initialLoad.value = false
    }
  }

  // 渲染 ECharts 图表
  if (thisRequest === requestId && !error.value) {
    await nextTick()
    if (chartDomRef.value && ['bar', 'line', 'pie', 'funnel', 'gauge', 'ranking'].includes(props.chart.chart_type)) {
      renderChart()
    }
  }
}

// ============ Pagination ============
const onPageChange = (page: number) => {
  currentPage.value = page
  loadChartData()
}

const onPageSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  loadChartData()
}

// ============ Chart Rendering ============
const renderChart = () => {
  if (!chartDomRef.value || chartData.value.length === 0) return

  // 始终重新初始化（因为 loading 会替换 DOM 元素）
  if (chartInstance) {
    chartInstance.dispose()
  }
  chartInstance = echarts.init(chartDomRef.value)

  const option = getEChartsOption()
  chartInstance.setOption(option, true)
}

const getEChartsOption = () => {
  const type = props.chart.chart_type
  const rows = chartData.value

  switch (type) {
    case 'bar':
      return getBarOption(rows)
    case 'line':
      return getLineOption(rows)
    case 'pie':
      return getPieOption(rows)
    case 'funnel':
      return getFunnelOption(rows)
    case 'gauge':
      return getGaugeOption(rows)
    case 'ranking':
      return getRankingOption(rows, bottomData.value)
    default:
      return {}
  }
}

const getBarOption = (rows: any[]) => {
  if (!rows?.length) return {}
  const keys = Object.keys(rows[0] || {})
  const xKey = keys[0]
  const yKey = keys[1] || keys[0]

  return {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
    },
    grid: { left: '3%', right: '8%', bottom: '3%', top: '3%', containLabel: true },
    xAxis: {
      type: 'category' as const,
      data: rows.map((d: any) => String(d[xKey] || '')),
      axisLabel: { rotate: rows.length > 6 ? 30 : 0, fontSize: 11 },
    },
    yAxis: { type: 'value' as const },
    series: [{
      type: 'bar' as const,
      data: rows.map((d: any, i: number) => ({
        value: Number(d[yKey]) || 0,
        itemStyle: {
          color: COLORS[i % COLORS.length],
          borderRadius: [4, 4, 0, 0],
        },
      })),
      barMaxWidth: 50,
      label: { show: rows.length <= 6, position: 'top' as const, fontSize: 11 },
    }],
  }
}

const getLineOption = (rows: any[]) => {
  if (!rows?.length) return {}
  const keys = Object.keys(rows[0] || {})
  const xKey = keys[0]
  const yKey = keys[1] || keys[0]

  return {
    tooltip: { trigger: 'axis' as const },
    grid: { left: '3%', right: '5%', bottom: '3%', top: '3%', containLabel: true },
    xAxis: {
      type: 'category' as const,
      data: rows.map((d: any) => String(d[xKey] || '').substring(0, 10)),
      axisLabel: { rotate: rows.length > 12 ? 45 : 0, fontSize: 10 },
    },
    yAxis: { type: 'value' as const },
    series: [{
      type: 'line' as const,
      data: rows.map((d: any) => Number(d[yKey]) || 0),
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { width: 2, color: COLORS[0] },
      itemStyle: { color: COLORS[0] },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(84, 112, 198, 0.3)' },
          { offset: 1, color: 'rgba(84, 112, 198, 0.02)' },
        ]),
      },
    }],
  }
}

const getPieOption = (rows: any[]) => {
  if (!rows?.length) return {}
  const keys = Object.keys(rows[0] || {})
  const nameKey = keys[0]
  const valueKey = keys[1] || keys[0]

  return {
    tooltip: {
      trigger: 'item' as const,
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical' as const,
      left: 'left' as const,
      top: 'middle' as const,
      textStyle: { fontSize: 11 },
    },
    series: [{
      type: 'pie' as const,
      radius: ['45%', '72%'],
      center: ['58%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.15)' },
      },
      data: rows.map((d: any) => ({
        name: String(d[nameKey] || ''),
        value: Number(d[valueKey]) || 0,
      })),
      color: COLORS,
    }],
  }
}

const getFunnelOption = (rows: any[]) => {
  if (!rows?.length) return {}
  const keys = Object.keys(rows[0] || {})
  const nameKey = keys[0]
  const valueKey = keys[1] || keys[0]

  return {
    tooltip: {
      trigger: 'item' as const,
      formatter: '{b}: {c}',
    },
    series: [{
      type: 'funnel' as const,
      left: '15%',
      right: '15%',
      top: 20,
      bottom: 20,
      width: '70%',
      min: 0,
      max: Math.max(...rows.map((d: any) => Number(d[valueKey]) || 0)),
      sort: 'descending' as const,
      gap: 4,
      label: { show: true, position: 'inside' as const, fontSize: 11 },
      itemStyle: { borderColor: '#fff', borderWidth: 0 },
      emphasis: {
        label: { fontSize: 14, fontWeight: 'bold' },
      },
      data: rows.map((d: any, i: number) => ({
        name: String(d[nameKey] || ''),
        value: Number(d[valueKey]) || 0,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
    }],
  }
}

const getGaugeOption = (rows: any[]) => {
  if (!rows?.length) return {}
  const data = rows[0] || {}
  const value = Number(data.value || data.total || 0)
  const max = Number(data.max_val || value * 2) || 100

  return {
    tooltip: { formatter: '{a} <br/>{c}' },
    series: [{
      name: props.chart.title,
      type: 'gauge' as const,
      min: 0,
      max: max,
      splitNumber: 5,
      axisLine: {
        lineStyle: {
          color: [
            [0.3, '#34C759'],
            [0.7, '#FF9500'],
            [1, '#FF3B30'],
          ],
          width: 8,
        },
      },
      pointer: { length: '60%', width: 4, itemStyle: { color: 'auto' } },
      axisTick: { distance: -8, length: 6, lineStyle: { width: 1, color: '#999' } },
      splitLine: { distance: -14, length: 12, lineStyle: { width: 2, color: '#999' } },
      axisLabel: { distance: 16, fontSize: 10, color: '#999' },
      detail: {
        valueAnimation: true,
        formatter: '{value}',
        fontSize: 28,
        fontWeight: 'bold',
        offsetCenter: [0, '80%'],
      },
      data: [{ value: value, name: props.chart.title }],
    }],
  }
}

const getRankingOption = (topRows: any[], bottomRows: any[]) => {
  if (!topRows?.length) return {}
  const keys = Object.keys(topRows[0] || {})

  if (keys.length >= 2) {
    const nameKey = keys[0]
    const valueKey = keys[1] || keys[0]

    const topNames = topRows.map((d: any) => String(d[nameKey] || ''))
    const topValues = topRows.map((d: any) => Number(d[valueKey]) || 0)

    const bottomValues = bottomRows.map((d: any) => Number(d[valueKey]) || 0)

    return {
      tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
      legend: {
        data: ['Top 5', 'Bottom 5'],
        top: 0,
        textStyle: { fontSize: 11 },
      },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '12%', containLabel: true },
      xAxis: { type: 'value' as const },
      yAxis: {
        type: 'category' as const,
        data: [...topNames].reverse(),
        axisLabel: { fontSize: 10 },
      },
      series: [
        {
          name: 'Top 5',
          type: 'bar' as const,
          data: [...topValues].reverse().map(v => ({
            value: v,
            itemStyle: { color: '#5470C6', borderRadius: [0, 4, 4, 0] },
          })),
          barGap: '20%',
          label: { show: true, position: 'right' as const, fontSize: 10 },
        },
        {
          name: 'Bottom 5',
          type: 'bar' as const,
          data: [...bottomValues].reverse().map(v => ({
            value: v,
            itemStyle: { color: '#EE6666', borderRadius: [0, 4, 4, 0] },
          })),
          label: { show: true, position: 'right' as const, fontSize: 10 },
        },
      ],
    }
  }

  return {}
}

// ============ Resize ============
const handleResize = () => {
  chartInstance?.resize()
}

// ============ Lifecycle ============
onMounted(() => {
  loadChartData()
  window.addEventListener('resize', handleResize)
  document.addEventListener('mousedown', onClickOutside)
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
  chartInstance = null
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('mousedown', onClickOutside)
})

// ============ Watch ============
watch(() => props.chart.id, () => {
  activeFilters.value = {}
  initialLoad.value = true
  currentPage.value = 1
  totalRows.value = 0
  loadChartData()
})

// 监听全局筛选变化 - 用 computed 返回值字符串确保触发
const globalFilterSnapshot = computed(() => {
  const f = props.globalFilters || {}
  return Object.keys(f).sort().map(k => `${k}=${f[k]}`).join('|')
})
watch(globalFilterSnapshot, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    currentPage.value = 1
    loadChartData()
  }
})

// 监听个别筛选变化
watch(activeFilters, () => {
  currentPage.value = 1
  loadChartData()
}, { deep: true })
</script>

<style scoped>
/* ============ 卡片容器 ============ */
.chart-card {
  background: var(--color-white);
  border-radius: var(--radius-xl);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-card);
  transition: box-shadow var(--transition-normal), opacity 0.2s ease;
  margin-bottom: var(--spacing-lg);
  cursor: default;
}

.chart-card:hover {
  box-shadow: var(--shadow-card-hover);
}

.chart-card--dragging {
  opacity: 0.5;
}

/* ============ 标题栏 ============ */
.chart-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--spacing-md);
}

.chart-card__title-group {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
}

.chart-card__drag-handle {
  cursor: grab;
  color: var(--color-text-tertiary);
  padding: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.chart-card:hover .chart-card__drag-handle {
  opacity: 1;
}

.chart-card__drag-handle:active {
  cursor: grabbing;
}

.chart-card__title {
  margin: 0;
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.chart-card__desc {
  display: block;
  margin-top: var(--spacing-xs);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.chart-card__actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
  align-items: center;
}

.btn-filter,
.btn-delete {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 28px;
  padding: 0 10px;
  font-size: var(--text-xs);
  font-family: inherit;
  border-radius: var(--radius-base);
  background: var(--color-bg);
  border: 1px solid var(--color-separator);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-filter:hover {
  background: rgba(0, 122, 255, 0.06);
  border-color: rgba(0, 122, 255, 0.2);
  color: var(--color-primary);
}

.btn-filter--active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.btn-filter--active:hover {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
  color: #fff;
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.btn-delete {
  padding: 0 8px;
}

.btn-delete:hover {
  color: var(--color-danger);
  background: rgba(255, 59, 48, 0.08);
  border-color: rgba(255, 59, 48, 0.2);
}

/* ============ 重新生成按钮 + 气泡 ============ */
.regenerate-wrapper {
  position: relative;
}

.btn-regenerate {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  width: 28px;
  padding: 0;
  font-size: var(--text-xs);
  font-family: inherit;
  border-radius: var(--radius-base);
  background: var(--color-bg);
  border: 1px solid var(--color-separator);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-regenerate:hover {
  background: rgba(0, 122, 255, 0.06);
  border-color: rgba(0, 122, 255, 0.2);
  color: var(--color-primary);
}

.btn-regenerate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.regenerate-popover {
  position: absolute;
  top: 50%;
  right: calc(100% + 8px);
  transform: translateY(-50%);
  width: 300px;
  z-index: 200;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: var(--radius-lg);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08),
              0 16px 48px rgba(0, 0, 0, 0.12);
  overflow: hidden;
}

.regenerate-popover__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md) var(--spacing-base);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.regenerate-popover__title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.regenerate-popover__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  background: none;
  color: var(--color-text-tertiary);
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.regenerate-popover__close:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--color-text-secondary);
}

.regenerate-popover__body {
  padding: var(--spacing-base);
}

.regenerate-input {
  width: 100%;
  height: 36px;
  padding: 0 var(--spacing-md);
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: var(--radius-base);
  font-size: var(--text-base);
  font-family: inherit;
  color: var(--color-text-primary);
  outline: none;
  transition: all 0.15s ease;
  box-sizing: border-box;
}

.regenerate-input::placeholder {
  color: var(--color-text-tertiary);
}

.regenerate-input:focus {
  background: rgba(255, 255, 255, 0.9);
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.15);
}

.regenerate-input:disabled {
  background: var(--color-bg);
  color: var(--color-text-tertiary);
  cursor: not-allowed;
}

.regenerate-popover__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--spacing-sm);
}

.regenerate-char-count {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.btn-regenerate-submit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 28px;
  padding: 0 14px;
  background: var(--color-primary);
  color: #fff;
  font-size: var(--text-sm);
  font-weight: 500;
  font-family: inherit;
  border: none;
  border-radius: var(--radius-base);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-regenerate-submit:hover {
  background: var(--color-primary-hover);
}

.btn-regenerate-submit:active {
  background: var(--color-primary-active);
  transform: scale(0.98);
}

.btn-regenerate-submit:disabled {
  background: var(--color-text-tertiary);
  cursor: not-allowed;
}

/* 气泡动画 */
.popover-scale-enter-active,
.popover-scale-leave-active {
  transition: all 0.2s var(--ease-out);
}

.popover-scale-enter-from,
.popover-scale-leave-to {
  opacity: 0;
  transform: translateY(-50%) scale(0.96);
  transform-origin: right center;
}

.popover-scale-enter-to,
.popover-scale-leave-from {
  opacity: 1;
  transform: translateY(-50%) scale(1);
}

/* ============ 筛选来源指示器 ============ */
.filter-source-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 8px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 500;
  transition: all 0.15s ease;
}

.filter-source-badge--individual {
  background: rgba(0, 122, 255, 0.12);
  color: #0062CC;
}

.filter-source-badge--global {
  background: rgba(52, 199, 89, 0.12);
  color: #248A3D;
}

.filter-source-badge--none {
  background: var(--color-bg);
  color: var(--color-text-tertiary);
}

.filter-source-badge__text {
  white-space: nowrap;
}

/* ============ 筛选面板 ============ */
.chart-card__filters {
  margin-bottom: 12px;
  padding: 12px;
  background: var(--color-bg);
  border-radius: var(--radius-base);
}

.filter-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.filter-label {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--color-text-secondary);
}

.filter-item :deep(.el-select) {
  width: 160px;
}

/* ============ 内容区 ============ */
.chart-card__body {
  position: relative;
}

.chart-box {
  height: 320px;
  width: 100%;
}

.chart-loading {
  padding: 40px;
}

.chart-loading-overlay {
  position: absolute;
  top: 0;
  right: 0;
  z-index: 10;
  padding: 8px;
  color: var(--color-text-tertiary);
  opacity: 0.6;
}

.chart-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 8px;
}

.chart-error__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 59, 48, 0.1);
  color: var(--color-danger);
  font-weight: 700;
  font-size: 18px;
}

.chart-error__text {
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
}

.chart-unsupported {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 160px;
  color: var(--color-text-tertiary);
  font-size: var(--text-sm);
}

/* ============ 表格 ============ */
.table-box {
  overflow-x: auto;
}

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 4px 0;
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.table-footer__info {
  flex-shrink: 0;
}

/* ============ 图表分页 ============ */
.chart-pagination {
  display: flex;
  justify-content: center;
  padding: 8px 0 0;
}

.chart-pagination :deep(.el-pagination) {
  --el-pagination-font-size: 12px;
  --el-pagination-button-height: 24px;
}

.chart-pagination :deep(.el-pagination .el-pager li) {
  min-width: 24px;
  height: 24px;
  line-height: 24px;
}

/* ============ 动画 ============ */
.filter-slide-enter-active,
.filter-slide-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.filter-slide-enter-from,
.filter-slide-leave-to {
  opacity: 0;
  max-height: 0;
  margin-bottom: 0;
}
.filter-slide-enter-to,
.filter-slide-leave-from {
  opacity: 1;
  max-height: 300px;
}
</style>
