<template>
  <div v-if="visible" ref="chartRef" class="mock-chart" :class="`mock-chart--${chart.chartType}`" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { BIChartItem } from '../../mocks/biInsightsMock'

const props = defineProps<{
  chart: BIChartItem
  /** 展开时为 true，用于折叠后重新挂载并 resize */
  visible?: boolean
}>()

const chartRef = ref<HTMLElement | null>(null)
let instance: echarts.ECharts | null = null

function buildOption(): echarts.EChartsOption {
  const accent = '#D97757'
  const mock = props.chart.chartMock

  if (props.chart.chartType === 'pie' && mock.pie) {
    return {
      color: [accent, '#E8A87C', '#C4A882', '#A8A29E'],
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '50%'],
        data: mock.pie,
        label: { fontSize: 11, color: '#736C64' }
      }]
    }
  }

  const categories = mock.categories || []
  const values = mock.values || []

  return {
    color: [accent],
    grid: { left: 48, right: 16, top: 20, bottom: 28 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: categories,
      axisLine: { lineStyle: { color: '#E5E0D8' } },
      axisLabel: { color: '#736C64', fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#F0EDE8' } },
      axisLabel: { color: '#A39E96', fontSize: 11 }
    },
    series: [{
      type: props.chart.chartType === 'line' ? 'line' : 'bar',
      data: values,
      smooth: props.chart.chartType === 'line',
      barMaxWidth: 28,
      areaStyle: props.chart.chartType === 'line' ? { opacity: 0.08 } : undefined,
      itemStyle: { borderRadius: props.chart.chartType === 'bar' ? [4, 4, 0, 0] : 0 }
    }]
  }
}

function initChart() {
  if (!props.visible || !chartRef.value) return
  if (props.chart.chartType === 'kpi' || props.chart.chartType === 'table') return
  instance?.dispose()
  instance = echarts.init(chartRef.value)
  instance.setOption(buildOption())
}

function resizeChart() {
  nextTick(() => {
    instance?.resize()
  })
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
  instance?.dispose()
  instance = null
})

watch(() => props.visible, (v) => {
  if (v) {
    nextTick(() => initChart())
  } else {
    instance?.dispose()
    instance = null
  }
})

watch(() => props.chart, () => {
  if (props.visible) initChart()
}, { deep: true })

defineExpose({ resizeChart })
</script>

<style scoped>
.mock-chart {
  width: 100%;
  height: 220px;
  min-height: 180px;
}
</style>
