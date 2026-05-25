import { computed, type Ref } from 'vue'
import type { BIProgressEvent } from '../api'

export type BIGenChartStatus = 'waiting' | 'planning' | 'processing' | 'completed' | 'failed' | 'partial_failed'

export type BIGenCategoryState = {
  id: string
  name: string
  total: number
  done: number
  failed: boolean
  status: BIGenChartStatus
}

export type BIGenPlannedChart = {
  id: string
  title: string
  chart_type: string
  category_id: string
  status: BIGenChartStatus
  message?: string
}

function displayName(name?: string) {
  return [...(name || '分类')].slice(0, 6).join('')
}

function isCategoryPlanning(events: BIProgressEvent[], categoryId: string) {
  const last = [...events].reverse().find(
    (event) =>
      event.category_id === categoryId &&
      ['category_plan_start', 'category_plan_done', 'category_start', 'category_done'].includes(event.step)
  )
  return last?.step === 'category_plan_start'
}

function isCategoryExecuting(events: BIProgressEvent[], categoryId: string) {
  const last = [...events].reverse().find(
    (event) =>
      event.category_id === categoryId &&
      ['category_start', 'chart_start', 'chart_done', 'chart_failed', 'category_done'].includes(event.step)
  )
  return !!last && last.step !== 'category_done'
}

export function useBiGenerationProgress(eventsRef: Ref<BIProgressEvent[]>) {
  const events = computed(() => eventsRef.value || [])

  const hasCategoriesReady = computed(() =>
    events.value.some((e) => e.step === 'categories_ready' && Array.isArray(e.categories) && e.categories.length > 0)
  )

  const hasChartPlanReady = computed(() => events.value.some((e) => e.step === 'chart_plan_ready'))

  const generationView = computed<'planning' | 'board'>(() =>
    hasCategoriesReady.value ? 'board' : 'planning'
  )

  const latestCategoriesPayload = computed(() => {
    const found = [...events.value].reverse().find((e) => Array.isArray(e.categories))
    return found?.categories || []
  })

  const latestChartPlan = computed(() => {
    const found = [...events.value].reverse().find((e) => Array.isArray(e.chart_plan))
    return found?.chart_plan || []
  })

  const chartStateById = computed<Record<string, { status: BIGenChartStatus; message?: string }>>(() => {
    const map: Record<string, { status: BIGenChartStatus; message?: string }> = {}
    for (const event of events.value) {
      if (!event.chart_id) continue
      if (event.step === 'chart_start') map[event.chart_id] = { status: 'processing' }
      if (event.step === 'chart_done') map[event.chart_id] = { status: 'completed' }
      if (event.step === 'chart_failed') map[event.chart_id] = { status: 'failed', message: event.message }
    }
    return map
  })

  const allPlannedCharts = computed<BIGenPlannedChart[]>(() =>
    latestChartPlan.value.flatMap((plan: any) =>
      (plan.charts || []).map((chart: any) => ({
        id: chart.id,
        title: chart.title || '未命名图表',
        chart_type: chart.chart_type || 'table',
        category_id: chart.category_id || plan.category_id,
        status: chartStateById.value[chart.id]?.status || 'waiting',
        message: chartStateById.value[chart.id]?.message,
      }))
    )
  )

  const categoryStates = computed<BIGenCategoryState[]>(() => {
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
      const charts = allPlannedCharts.value.filter((chart) => chart.category_id === cat.id)
      const done = charts.filter((chart) => ['completed', 'failed'].includes(chart.status)).length
      const failed = charts.some((chart) => chart.status === 'failed')
      const processing =
        charts.some((chart) => chart.status === 'processing') || isCategoryExecuting(events.value, cat.id)
      const planning = isCategoryPlanning(events.value, cat.id)
      let status: BIGenChartStatus = 'waiting'
      if (failed && done >= (cat.total || charts.length)) status = 'partial_failed'
      else if ((cat.total || charts.length) > 0 && done >= (cat.total || charts.length)) status = 'completed'
      else if (processing) status = 'processing'
      else if (planning) status = 'planning'
      return { ...cat, done, failed, status }
    })
  })

  const totalChartCount = computed(() => {
    const planned = latestChartPlan.value.reduce(
      (sum: number, plan: any) => sum + Number(plan.charts_count || 0),
      0
    )
    if (planned) return planned
    const event = [...events.value].reverse().find((e) => Number(e.charts_count || 0) > 0)
    return Number(event?.charts_count || 0)
  })

  const completedChartCount = computed(() =>
    Object.values(chartStateById.value).filter((item) => item.status === 'completed').length
  )

  const latestMessage = computed(() => {
    const last = events.value[events.value.length - 1]
    return last?.message || ''
  })

  const activePhaseIndex = computed(() => {
    const step = events.value[events.value.length - 1]?.step
    if (step === 'bi_completed') return 3
    if (['category_start', 'chart_start', 'chart_done', 'chart_failed', 'category_done'].includes(step || ''))
      return 2
    if (['chart_planning', 'category_plan_start', 'category_plan_done', 'chart_plan_ready'].includes(step || ''))
      return 1
    return 0
  })

  const chartsByCategory = computed(() => {
    const map: Record<string, BIGenPlannedChart[]> = {}
    for (const chart of allPlannedCharts.value) {
      if (!map[chart.category_id]) map[chart.category_id] = []
      map[chart.category_id].push(chart)
    }
    return map
  })

  return {
    events,
    generationView,
    hasCategoriesReady,
    hasChartPlanReady,
    latestCategoriesPayload,
    latestChartPlan,
    categoryStates,
    allPlannedCharts,
    chartsByCategory,
    totalChartCount,
    completedChartCount,
    latestMessage,
    activePhaseIndex,
    displayName,
  }
}
