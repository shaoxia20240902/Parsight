/** 洞察看板 Mock 数据（前端调试专用，后续对接真实 BI API） */

export const BI_MAX_BOARD_PER_CATEGORY = 10
export const BI_MAX_WAREHOUSE_TOTAL = 100
/** Sheet 对应分类上限（与上传 Excel 的 Sheet 一一对应） */
export const BI_MAX_SHEET_CATEGORIES = 5
/** 用户可自定义添加的分类上限 */
export const BI_MAX_CUSTOM_CATEGORIES = 3
export const BI_MAX_CATEGORIES_TOTAL = BI_MAX_SHEET_CATEGORIES + BI_MAX_CUSTOM_CATEGORIES

export type BIChartType = 'kpi_group' | 'bar' | 'line' | 'pie' | 'combo' | 'ranking' | 'table' | 'detail_table' | 'kpi'
export type BICategorySource = 'sheet' | 'custom'

export interface BICategory {
  id: string
  name: string
  icon: string
  source: BICategorySource
  /** Sheet 分类时关联的表名（Mock / 后续对接 sheet_meta） */
  sheetKey?: string
}

export interface BITablePreview {
  columns: string[]
  rows: Record<string, string | number>[]
}

export interface BIChartItem {
  id: string
  categoryId: string
  title: string
  /** 业务问题描述 */
  question: string
  chartType: BIChartType
  sql: string
  /** 是否在主看板展示 */
  onBoard: boolean
  /** 看板上是否收起 */
  collapsed: boolean
  /** 看板栅格：false=半宽(1/2)，true=通栏 */
  expanded?: boolean
  /** 同分类看板内排序（越小越靠前） */
  boardOrder?: number
  /** 图表独立筛选（优先于全局） */
  chartFilters?: Record<string, string>
  intentType?: string
  encoding?: Record<string, any>
  items?: Array<{ label: string; value_field: string; format?: string }>
  layout?: { max_per_row?: number }
  tablePreview: BITablePreview
  /** ECharts 配置（Mock 渲染） */
  chartMock: {
    categories?: string[]
    values?: number[]
    pie?: { name: string; value: number }[]
    kpiValue?: string
    kpiSub?: string
  }
}

export interface BIGlobalFilterField {
  field: string
  label: string
  options: string[]
}

export interface BIInsightsState {
  categories: BICategory[]
  charts: BIChartItem[]
  globalFilters: BIGlobalFilterField[]
}

const previewSales = (): BITablePreview => ({
  columns: ['区域', '月份', '销售额'],
  rows: [
    { 区域: '华东', 月份: '2025-01', 销售额: 1280000 },
    { 区域: '华南', 月份: '2025-01', 销售额: 960000 },
    { 区域: '华北', 月份: '2025-01', 销售额: 1120000 },
    { 区域: '西部', 月份: '2025-01', 销售额: 540000 }
  ]
})

const previewOrders = (): BITablePreview => ({
  columns: ['状态', '订单数'],
  rows: [
    { 状态: '已完成', 订单数: 4200 },
    { 状态: '处理中', 订单数: 680 },
    { 状态: '已取消', 订单数: 120 }
  ]
})

/** Mock：当前空间已上传 Sheet 列表（后续由 API 返回） */
export const MOCK_SPACE_SHEETS = [
  '销售明细',
  '客户信息',
  '订单流水',
  '库存表',
  '渠道数据'
] as const

export function buildSheetCategories(sheetNames: readonly string[]): BICategory[] {
  return sheetNames.slice(0, BI_MAX_SHEET_CATEGORIES).map((name, i) => ({
    id: `sheet-${i}`,
    name,
    icon: 'sheet',
    source: 'sheet' as const,
    sheetKey: name
  }))
}

export function createMockBIState(): BIInsightsState {
  const categories: BICategory[] = [
    ...buildSheetCategories(MOCK_SPACE_SHEETS),
    { id: 'custom-1', name: '经营概览', icon: 'chart', source: 'custom' },
    { id: 'custom-2', name: '专题分析', icon: 'chart', source: 'custom' }
  ]

  const charts: BIChartItem[] = [
    {
      id: 'c1',
      categoryId: 'sheet-0',
      title: '各区域月度销售额',
      question: '各销售区域在本月的销售额对比如何？是否存在明显短板？',
      chartType: 'bar',
      sql: `SELECT region AS 区域, month AS 月份, SUM(amount) AS 销售额
FROM sales_fact
WHERE month = '2025-01'
GROUP BY region, month
ORDER BY 销售额 DESC`,
      onBoard: true,
      collapsed: false,
      tablePreview: previewSales(),
      chartMock: {
        categories: ['华东', '华南', '华北', '西部'],
        values: [128, 96, 112, 54]
      }
    },
    {
      id: 'c2',
      categoryId: 'sheet-0',
      title: '销售额趋势',
      question: '近 6 个月整体销售额是否呈上升或季节性波动？',
      chartType: 'line',
      sql: `SELECT month, SUM(amount) AS total
FROM sales_fact
GROUP BY month
ORDER BY month
LIMIT 6`,
      onBoard: true,
      collapsed: false,
      tablePreview: {
        columns: ['月份', '销售额'],
        rows: [
          { 月份: '08', 销售额: 320 },
          { 月份: '09', 销售额: 380 },
          { 月份: '10', 销售额: 410 }
        ]
      },
      chartMock: {
        categories: ['08', '09', '10', '11', '12', '01'],
        values: [320, 380, 410, 395, 450, 490]
      }
    },
    {
      id: 'c3',
      categoryId: 'sheet-0',
      title: 'Top 品类占比',
      question: '销售额主要由哪些品类贡献？集中度是否过高？',
      chartType: 'pie',
      sql: `SELECT category, SUM(amount) AS amt
FROM sales_fact GROUP BY category`,
      onBoard: true,
      collapsed: true,
      tablePreview: previewSales(),
      chartMock: {
        pie: [
          { name: '数码', value: 38 },
          { name: '家居', value: 27 },
          { name: '服饰', value: 22 },
          { name: '其他', value: 13 }
        ]
      }
    },
    {
      id: 'c4',
      categoryId: 'sheet-1',
      title: '客户分层分布',
      question: '高价值客户占比多少？是否需要针对性运营？',
      chartType: 'pie',
      sql: `SELECT tier, COUNT(*) FROM customers GROUP BY tier`,
      onBoard: true,
      collapsed: false,
      tablePreview: {
        columns: ['层级', '人数'],
        rows: [
          { 层级: 'VIP', 人数: 1200 },
          { 层级: '普通', 人数: 8600 }
        ]
      },
      chartMock: {
        pie: [
          { name: 'VIP', value: 12 },
          { name: '活跃', value: 35 },
          { name: '沉默', value: 53 }
        ]
      }
    },
    {
      id: 'c5',
      categoryId: 'sheet-1',
      title: '复购率 KPI',
      question: '本季度客户复购率是否达到目标？',
      chartType: 'kpi',
      sql: `SELECT ROUND(COUNT(DISTINCT repeat_user)*100.0/COUNT(DISTINCT user_id),1) AS rate
FROM orders WHERE quarter = '2025-Q1'`,
      onBoard: true,
      collapsed: false,
      tablePreview: previewOrders(),
      chartMock: { kpiValue: '34.2%', kpiSub: '环比 +2.1pt' }
    },
    {
      id: 'c6',
      categoryId: 'sheet-3',
      title: 'SKU 动销排行',
      question: '哪些 SKU 动销最慢，需要清仓或促销？',
      chartType: 'bar',
      sql: `SELECT sku_name, sold_qty FROM inventory ORDER BY sold_qty ASC LIMIT 10`,
      onBoard: true,
      collapsed: false,
      tablePreview: previewSales(),
      chartMock: {
        categories: ['SKU-A', 'SKU-B', 'SKU-C', 'SKU-D'],
        values: [12, 28, 45, 67]
      }
    },
    {
      id: 'c7',
      categoryId: 'sheet-3',
      title: '库存明细表',
      question: '当前低库存 SKU 有哪些？',
      chartType: 'table',
      sql: `SELECT sku, warehouse, qty FROM stock WHERE qty < safety_stock`,
      onBoard: false,
      collapsed: false,
      tablePreview: {
        columns: ['SKU', '仓库', '库存'],
        rows: [
          { SKU: 'X-01', 仓库: '上海', 库存: 8 },
          { SKU: 'Y-12', 仓库: '广州', 库存: 15 }
        ]
      },
      chartMock: {}
    },
    {
      id: 'c8',
      categoryId: 'sheet-2',
      title: '订单履约时长',
      question: '平均履约时长是否因仓配策略变化而拉长？',
      chartType: 'line',
      sql: `SELECT week, AVG(fulfill_hours) FROM fulfill_log GROUP BY week`,
      onBoard: true,
      collapsed: false,
      tablePreview: previewOrders(),
      chartMock: {
        categories: ['W1', 'W2', 'W3', 'W4'],
        values: [18, 16, 19, 15]
      }
    },
    {
      id: 'c9',
      categoryId: 'sheet-2',
      title: '订单状态分布',
      question: '取消率是否异常升高？',
      chartType: 'table',
      sql: `SELECT status, COUNT(*) FROM orders GROUP BY status`,
      onBoard: false,
      collapsed: false,
      tablePreview: previewOrders(),
      chartMock: {}
    },
    {
      id: 'c10',
      categoryId: 'sheet-0',
      title: '客单价对比',
      question: '各区域客单价差异是否反映定价策略不同？',
      chartType: 'bar',
      sql: `SELECT region, AVG(order_amount) FROM orders GROUP BY region`,
      onBoard: false,
      collapsed: false,
      tablePreview: previewSales(),
      chartMock: {
        categories: ['华东', '华南', '华北'],
        values: [268, 241, 255]
      }
    },
    {
      id: 'c11',
      categoryId: 'sheet-1',
      title: '新客获取成本',
      question: '获客成本是否在渠道扩张后显著上升？',
      chartType: 'line',
      sql: `SELECT channel, SUM(cost)/COUNT(new_users) AS cac FROM marketing GROUP BY channel`,
      onBoard: false,
      collapsed: false,
      tablePreview: previewOrders(),
      chartMock: {
        categories: ['1月', '2月', '3月'],
        values: [42, 48, 45]
      }
    }
  ]

  const normalizedCharts = charts.map((c, i) => ({
    ...c,
    expanded: c.expanded ?? false,
    boardOrder: c.boardOrder ?? i,
    chartFilters: c.chartFilters ?? {}
  }))

  return {
    categories,
    charts: normalizedCharts,
    globalFilters: [
      { field: 'region', label: '区域', options: ['全部', '华东', '华南', '华北', '西部'] },
      { field: 'month', label: '月份', options: ['2025-01', '2024-12', '2024-11'] },
      { field: 'channel', label: '渠道', options: ['全部', '线上', '线下', '分销'] }
    ]
  }
}
