<template>
  <div
    v-if="chart.chartType === 'kpi_group' || chart.chartType === 'kpi'"
    class="kpi-group"
    :class="{ 'kpi-group--expanded': expanded }"
  >
    <div
      v-for="(item, index) in kpiItems"
      :key="`${item.value_field}-${index}`"
      class="kpi-item"
    >
      <div class="kpi-item__actions">
        <button type="button" title="左移" :disabled="index === 0" @click="moveItem(index, -1)">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <button type="button" title="右移" :disabled="index === kpiItems.length - 1" @click="moveItem(index, 1)">
          <el-icon><ArrowRight /></el-icon>
        </button>
        <button type="button" title="编辑" @click="editItem(index)">
          <el-icon><Edit /></el-icon>
        </button>
        <button type="button" title="删除" @click="deleteItem(index)">
          <el-icon><Delete /></el-icon>
        </button>
      </div>
      <span class="kpi-item__label">{{ item.label }}</span>
      <strong class="kpi-item__value">{{ formatValue(kpiValue(item), item.format) }}</strong>
    </div>
  </div>

  <div
    v-else-if="chart.chartType === 'gauge'"
    class="progress-chart"
    :class="{ 'progress-chart--expanded': expanded }"
  >
    <div class="progress-chart__head">
      <span class="progress-chart__label">{{ progressLabel }}</span>
      <strong class="progress-chart__value">{{ progressDisplay }}</strong>
    </div>
    <div class="progress-chart__track" role="progressbar" :aria-valuenow="progressPercent" aria-valuemin="0" aria-valuemax="100">
      <span class="progress-chart__fill" :style="{ width: `${progressPercent}%` }" />
    </div>
    <div class="progress-chart__meta">
      <span>0%</span>
      <span>目标 100%</span>
    </div>
    <p v-if="progressStatus" class="progress-chart__status">{{ progressStatus }}</p>
  </div>

  <div
    v-else
    ref="chartRef"
    class="chart-renderer"
    :class="[`chart-renderer--${chart.chartType}`, { 'chart-renderer--expanded': expanded }]"
  />
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ArrowLeft, ArrowRight, Delete, Edit } from '@element-plus/icons-vue'
import type { BIChartItem } from '../../mocks/biInsightsMock'

const props = defineProps<{
  chart: BIChartItem
  visible?: boolean
  expanded?: boolean
}>()

const emit = defineEmits<{
  'update-kpi-items': [items: Array<{ label: string; value_field: string; format?: string }>]
}>()

const chartRef = ref<HTMLElement | null>(null)
let instance: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const rows = computed(() => props.chart.tablePreview?.rows || [])
const columns = computed(() => props.chart.tablePreview?.columns || [])
const expanded = computed(() => props.expanded === true)

const kpiItems = computed(() => {
  if (props.chart.items?.length) return props.chart.items
  if (props.chart.chartType === 'kpi') {
    return [{ label: props.chart.title, value_field: columns.value[0] || 'value', format: 'number' }]
  }
  return columns.value.slice(0, 5).map((col) => ({ label: col, value_field: col, format: inferFormat(col) }))
})

function kpiValue(item: { value_field: string }) {
  const row = rows.value[0] || {}
  return row[item.value_field] ?? row[item.value_field.replace(/^总/, '')] ?? props.chart.chartMock?.kpiValue
}

function cloneItems() {
  return kpiItems.value.map((item) => ({ ...item }))
}

function moveItem(index: number, delta: number) {
  const items = cloneItems()
  const target = index + delta
  if (target < 0 || target >= items.length) return
  const [item] = items.splice(index, 1)
  items.splice(target, 0, item)
  emit('update-kpi-items', items)
}

function deleteItem(index: number) {
  const items = cloneItems()
  items.splice(index, 1)
  emit('update-kpi-items', items)
}

function editItem(index: number) {
  const items = cloneItems()
  const current = items[index]
  const next = window.prompt('指标名称', current.label)
  if (!next?.trim()) return
  current.label = next.trim().slice(0, 24)
  emit('update-kpi-items', items)
}

function inferFormat(label: string) {
  return /率|占比|比例|percent|rate|ratio|margin/i.test(label) ? 'percent' : 'number'
}

function formatValue(value: unknown, format?: string) {
  const n = Number(String(value ?? '').replace(/,/g, '').replace('%', ''))
  if (Number.isNaN(n)) return value == null || value === '' ? '-' : String(value)
  if (format === 'percent') return `${Math.round(n)}%`
  if (Math.abs(n) >= 100000000) return `${(n / 100000000).toFixed(2)}亿`
  if (Math.abs(n) >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  return Math.round(n).toLocaleString('zh-CN')
}

function numberValue(row: Record<string, any>, field?: string) {
  if (!field) return 0
  const raw = row[field]
  const n = Number(String(raw ?? '').replace(/,/g, '').replace('%', ''))
  return Number.isNaN(n) ? 0 : n
}

const progressField = computed(() => {
  const encoding = props.chart.encoding || {}
  const yEnc = Array.isArray(encoding.y) ? encoding.y : []
  return yEnc[0]?.field || firstNumericColumn(encoding.x?.field) || columns.value[0]
})

const progressRaw = computed(() => numberValue(rows.value[0] || {}, progressField.value))
const progressPercent = computed(() => Math.max(0, Math.min(100, Math.round(progressRaw.value))))
const progressLabel = computed(() => rows.value[0]?.[columns.value[0]] ? String(rows.value[0]?.[columns.value[0]]) : props.chart.title)
const progressDisplay = computed(() => `${progressPercent.value}%`)
const progressStatus = computed(() => {
  if (progressPercent.value >= 100) return '已达成目标'
  if (progressPercent.value >= 85) return '接近目标，保持当前节奏'
  if (progressPercent.value >= 70) return '进度正常，仍有追赶空间'
  return '低于预期，需要关注'
})

function firstNumericColumn(except?: string) {
  return columns.value.find((col) => col !== except && rows.value.some((row) => !Number.isNaN(Number(String(row[col] ?? '').replace(/,/g, '').replace('%', ''))))) || columns.value[1]
}

function numericColumns(except?: string) {
  return columns.value.filter((col) =>
    col !== except &&
    rows.value.some((row) => !Number.isNaN(Number(String(row[col] ?? '').replace(/,/g, '').replace('%', ''))))
  )
}

function buildOption(): echarts.EChartsOption {
  const chartType = props.chart.chartType
  const encoding = props.chart.encoding || {}
  const xField = encoding.x?.field || columns.value[0]
  const yEnc = Array.isArray(encoding.y) ? encoding.y : []
  const yField = yEnc[0]?.field || firstNumericColumn(xField)
  const accent = '#D97757'
  const palette = [accent, '#5470C6', '#91CC75', '#FAC858', '#73C0DE', '#9A60B4']

  const baseGrid = { left: 12, right: 20, top: 24, bottom: 34, containLabel: true }

  if (chartType === 'pie' || chartType === 'donut') {
    const valueField = yField || columns.value[1]
    return {
      color: palette,
      tooltip: {
        trigger: 'item',
        formatter: (p: any) => `${p.name}: ${formatValue(p.value)} (${Math.round(p.percent)}%)`
      },
      series: [{
        type: 'pie',
        radius: chartType === 'donut' ? ['42%', '68%'] : ['0%', '68%'],
        center: ['50%', '50%'],
        data: rows.value.map((row) => ({ name: String(row[xField] ?? ''), value: numberValue(row, valueField) })),
        label: { color: '#736C64', fontSize: 11, formatter: '{b}' }
      }]
    }
  }

  if (chartType === 'treemap') {
    const valueField = yField || columns.value[1]
    return {
      color: palette,
      tooltip: { formatter: (p: any) => `${p.name}: ${formatValue(p.value)}` },
      series: [{
        type: 'treemap',
        roam: false,
        breadcrumb: { show: false },
        data: rows.value.map((row) => ({ name: String(row[xField] ?? ''), value: numberValue(row, valueField) })),
        label: { color: '#fff', fontSize: 12 }
      }]
    }
  }

  if (chartType === 'funnel') {
    const valueField = yField || columns.value[1]
    return {
      color: palette,
      tooltip: { trigger: 'item', formatter: (p: any) => `${p.name}: ${formatValue(p.value)}` },
      series: [{
        type: 'funnel',
        left: '10%',
        width: '80%',
        minSize: '20%',
        maxSize: '95%',
        sort: 'descending',
        gap: 2,
        data: rows.value.map((row) => ({ name: String(row[xField] ?? ''), value: numberValue(row, valueField) })),
        label: { color: '#4A4541', fontSize: 11 }
      }]
    }
  }

  if (chartType === 'scatter' || chartType === 'bubble') {
    const fields = numericColumns().slice(0, 3)
    const xMetric = fields[0] || yField
    const yMetric = fields[1] || firstNumericColumn(xMetric)
    const sizeMetric = fields[2] || yMetric
    return {
      color: [accent],
      grid: baseGrid,
      tooltip: {
        trigger: 'item',
        formatter: (p: any) => `${rows.value[p.dataIndex]?.[xField] ?? ''}<br/>${xMetric}: ${formatValue(p.value[0])}<br/>${yMetric}: ${formatValue(p.value[1])}`
      },
      xAxis: { type: 'value', axisLabel: { color: '#A39E96', formatter: (v: number) => formatValue(v) } },
      yAxis: { type: 'value', axisLabel: { color: '#A39E96', formatter: (v: number) => formatValue(v) } },
      series: [{
        type: 'scatter',
        data: rows.value.map((row) => [numberValue(row, xMetric), numberValue(row, yMetric), numberValue(row, sizeMetric)]),
        symbolSize: chartType === 'bubble' ? (data: number[]) => Math.max(8, Math.min(34, Math.sqrt(Math.abs(data[2] || 1)))) : 10,
        itemStyle: { opacity: 0.76 }
      }]
    }
  }

  if (chartType === 'heatmap') {
    const xValues = [...new Set(rows.value.map((row) => String(row[columns.value[0]] ?? '')))]
    const yFieldName = columns.value[1] || columns.value[0]
    const yValues = [...new Set(rows.value.map((row) => String(row[yFieldName] ?? '')))]
    const valueField = firstNumericColumn(yFieldName)
    return {
      tooltip: { position: 'top' },
      grid: baseGrid,
      xAxis: { type: 'category', data: xValues, axisLabel: { color: '#736C64', fontSize: 11 } },
      yAxis: { type: 'category', data: yValues, axisLabel: { color: '#736C64', fontSize: 11 } },
      visualMap: { min: 0, max: Math.max(...rows.value.map((row) => numberValue(row, valueField)), 1), show: false, inRange: { color: ['#F7E7DF', accent] } },
      series: [{
        type: 'heatmap',
        data: rows.value.map((row) => [
          xValues.indexOf(String(row[columns.value[0]] ?? '')),
          yValues.indexOf(String(row[yFieldName] ?? '')),
          numberValue(row, valueField)
        ]),
        label: { show: false }
      }]
    }
  }

  if (chartType === 'radar') {
    const fields = numericColumns().slice(0, 6)
    const firstRow = rows.value[0] || {}
    return {
      color: [accent],
      tooltip: {},
      radar: {
        indicator: fields.map((field) => ({
          name: field,
          max: Math.max(...rows.value.map((row) => numberValue(row, field)), numberValue(firstRow, field), 1)
        })),
        axisName: { color: '#736C64', fontSize: 11 }
      },
      series: [{ type: 'radar', data: [{ value: fields.map((field) => numberValue(firstRow, field)), name: props.chart.title }] }]
    }
  }

  if (chartType === 'combo') {
    const comboFields = yEnc.length
      ? yEnc
      : numericColumns(xField).slice(0, 2).map((field, index) => ({
          field,
          label: field,
          axis: index === 1 && inferFormat(field) === 'percent' ? 'right' : 'left',
          series_type: index === 1 && inferFormat(field) === 'percent' ? 'line' : 'bar'
        }))
    const series = comboFields.slice(0, 3).map((item: any, index: number) => ({
      name: item.label || item.field,
      type: item.series_type || (item.axis === 'right' ? 'line' : 'bar'),
      yAxisIndex: item.axis === 'right' ? 1 : 0,
      data: rows.value.map((row) => numberValue(row, item.field)),
      smooth: item.series_type === 'line',
      barMaxWidth: 28,
      itemStyle: { color: palette[index % palette.length], borderRadius: item.series_type === 'bar' ? [4, 4, 0, 0] : 0 }
    }))
    return {
      color: palette,
      grid: { ...baseGrid, right: 52 },
      tooltip: { trigger: 'axis' },
      legend: comboFields.length > 1 ? { top: 0, textStyle: { fontSize: 11 } } : undefined,
      xAxis: { type: 'category', data: rows.value.map((row) => String(row[xField] ?? '')), axisLabel: { color: '#736C64', fontSize: 11 } },
      yAxis: [
        { type: 'value', axisLabel: { color: '#A39E96', formatter: (v: number) => formatValue(v) } },
        { type: 'value', axisLabel: { color: '#A39E96', formatter: (v: number) => `${Math.round(v)}%` } }
      ],
      series
    }
  }

  if (chartType === 'ranking' || chartType === 'horizontal_bar') {
    const sorted = [...rows.value].sort((a, b) => numberValue(a, yField) - numberValue(b, yField))
    return {
      color: [accent],
      grid: baseGrid,
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: { type: 'value', axisLabel: { color: '#A39E96', formatter: (v: number) => formatValue(v) } },
      yAxis: { type: 'category', data: sorted.map((row) => String(row[xField] ?? '')), axisLabel: { color: '#736C64', fontSize: 11 } },
      series: [{ type: 'bar', data: sorted.map((row) => numberValue(row, yField)), barMaxWidth: 22, itemStyle: { borderRadius: [0, 4, 4, 0] } }]
    }
  }

  const isLine = ['line', 'multi_line', 'area', 'stacked_area'].includes(chartType)
  const isStacked = ['stacked_bar', 'stacked_area'].includes(chartType)
  const isWaterfall = chartType === 'waterfall'
  const seriesFields = yEnc.length ? yEnc : [{ field: yField, label: yField }]
  return {
    color: palette,
    grid: baseGrid,
    tooltip: { trigger: 'axis' },
    legend: seriesFields.length > 1 ? { top: 0, textStyle: { fontSize: 11 } } : undefined,
    xAxis: { type: 'category', data: rows.value.map((row) => String(row[xField] ?? '')), axisLabel: { color: '#736C64', fontSize: 11 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#F0EDE8' } }, axisLabel: { color: '#A39E96', fontSize: 11, formatter: (v: number) => formatValue(v) } },
    series: seriesFields.map((item: any, index: number) => ({
      name: item.label || item.field,
      type: isLine ? 'line' : 'bar',
      data: rows.value.map((row) => numberValue(row, item.field)),
      smooth: isLine,
      stack: isStacked ? 'total' : undefined,
      barMaxWidth: 28,
      areaStyle: ['area', 'stacked_area'].includes(chartType) ? { opacity: 0.16 } : undefined,
      itemStyle: { color: palette[index % palette.length], borderRadius: isLine || isWaterfall ? 0 : [4, 4, 0, 0] }
    }))
  }
}

function initChart() {
  if (!props.visible || !chartRef.value || ['kpi_group', 'kpi', 'gauge', 'table', 'detail_table'].includes(props.chart.chartType)) return
  instance?.dispose()
  instance = echarts.init(chartRef.value)
  instance.setOption(buildOption(), true)
  resizeObserver?.disconnect()
  resizeObserver = new ResizeObserver(() => instance?.resize())
  resizeObserver.observe(chartRef.value)
}

function onResize() {
  instance?.resize()
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  resizeObserver?.disconnect()
  resizeObserver = null
  instance?.dispose()
  instance = null
})

watch(() => props.visible, (visible) => {
  if (visible) nextTick(() => initChart())
  else {
    resizeObserver?.disconnect()
    resizeObserver = null
    instance?.dispose()
    instance = null
  }
})

watch(() => [props.chart.chartType, props.chart.tablePreview, props.chart.encoding], () => {
  if (props.visible) nextTick(() => initChart())
}, { deep: true })

watch(() => props.expanded, () => {
  nextTick(() => {
    window.setTimeout(() => instance?.resize(), 180)
  })
})

defineExpose({ resizeChart: onResize })
</script>

<style scoped>
.chart-renderer {
  width: 100%;
  height: 240px;
  min-height: 190px;
  transition: height 0.18s ease;
}

.chart-renderer--expanded {
  height: 360px;
  min-height: 320px;
}

.kpi-group {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  min-height: 180px;
  align-content: center;
  transition: gap 0.18s ease, min-height 0.18s ease;
}

.kpi-group--expanded {
  gap: 16px;
  min-height: 260px;
}

.kpi-item {
  position: relative;
  min-width: 0;
  padding: 18px 14px;
  border: 1px solid #E5E0D8;
  border-radius: 8px;
  background: #FAF8F5;
  transition: padding 0.18s ease;
}

.kpi-group--expanded .kpi-item {
  padding: 24px 18px;
}

.kpi-item__actions {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.kpi-item:hover .kpi-item__actions {
  opacity: 1;
}

.kpi-item__actions button {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #E5E0D8;
  border-radius: 6px;
  background: #fff;
  color: #736C64;
  cursor: pointer;
}

.kpi-item__actions button:disabled {
  opacity: 0.35;
  cursor: default;
}

.kpi-item__label {
  display: block;
  margin-bottom: 10px;
  color: #736C64;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kpi-item__value {
  display: block;
  color: #D97757;
  font-size: clamp(22px, 2.8vw, 36px);
  font-weight: 600;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kpi-group--expanded .kpi-item__label {
  font-size: 13px;
  margin-bottom: 12px;
}

.kpi-group--expanded .kpi-item__value {
  font-size: 42px;
}

.progress-chart {
  min-height: 190px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 16px;
  padding: 18px 6px;
  transition: min-height 0.18s ease, padding 0.18s ease, gap 0.18s ease;
}

.progress-chart--expanded {
  min-height: 320px;
  gap: 22px;
  padding: 34px 18px;
}

.progress-chart__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
}

.progress-chart__label {
  min-width: 0;
  color: #736C64;
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.progress-chart__value {
  flex-shrink: 0;
  color: #1C1917;
  font-size: 38px;
  line-height: 1;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.progress-chart--expanded .progress-chart__label {
  font-size: 15px;
}

.progress-chart--expanded .progress-chart__value {
  font-size: 56px;
}

.progress-chart__track {
  position: relative;
  height: 18px;
  overflow: hidden;
  border-radius: 999px;
  background: #EFE9E1;
  border: 1px solid #E5DED4;
  box-shadow: inset 0 1px 2px rgba(58, 45, 34, 0.08);
}

.progress-chart--expanded .progress-chart__track {
  height: 24px;
}

.progress-chart__fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  background: linear-gradient(90deg, #C6613F 0%, #D97757 72%, #E5A076 100%);
  box-shadow: 0 6px 14px rgba(198, 97, 63, 0.18);
  transition: width 0.28s ease;
}

.progress-chart__meta {
  display: flex;
  justify-content: space-between;
  color: #A39E96;
  font-size: 12px;
}

.progress-chart__status {
  margin: 0;
  padding: 10px 12px;
  color: #736C64;
  font-size: 13px;
  line-height: 1.45;
  background: #FAF8F5;
  border: 1px solid #E8E1D8;
  border-radius: 8px;
}

.progress-chart--expanded .progress-chart__status {
  font-size: 14px;
  padding: 12px 14px;
}

@media (max-width: 1100px) {
  .kpi-group {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .kpi-group {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .kpi-group--expanded .kpi-item__value {
    font-size: 34px;
  }

  .progress-chart--expanded .progress-chart__value {
    font-size: 44px;
  }
}
</style>
