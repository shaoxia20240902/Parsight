import type { BIChartType } from './biInsightsMock'

type DemoRow = Record<string, string | number>

interface DemoChartDef {
  title: string
  question: string
  type: BIChartType
  rows: DemoRow[]
  columns?: string[]
  expanded?: boolean
  items?: Array<{ label: string; value_field: string; format?: string }>
  encoding?: Record<string, any>
}

const salesByRegion = [
  { 区域: '华东', 销售额: 4280000, 利润: 918000, 订单数: 146 },
  { 区域: '华南', 销售额: 3720000, 利润: 741000, 订单数: 122 },
  { 区域: '华北', 销售额: 3360000, 利润: 685000, 订单数: 108 },
  { 区域: '西南', 销售额: 2180000, 利润: 389000, 订单数: 78 },
  { 区域: '西北', 销售额: 1560000, 利润: 245000, 订单数: 54 }
]

const monthlySales = [
  { 月份: '01月', 销售额: 1680000, 利润: 318000, 毛利率: 19 },
  { 月份: '02月', 销售额: 1940000, 利润: 371000, 毛利率: 19.1 },
  { 月份: '03月', 销售额: 2280000, 利润: 452000, 毛利率: 19.8 },
  { 月份: '04月', 销售额: 2410000, 利润: 486000, 毛利率: 20.2 },
  { 月份: '05月', 销售额: 2860000, 利润: 601000, 毛利率: 21 },
  { 月份: '06月', 销售额: 3120000, 利润: 678000, 毛利率: 21.7 }
]

const categorySales = [
  { 产品类别: '办公设备', 销售额: 3860000, 利润: 812000, 数量: 1060 },
  { 产品类别: '数码配件', 销售额: 3150000, 利润: 563000, 数量: 1860 },
  { 产品类别: '家具家居', 销售额: 2440000, 利润: 421000, 数量: 720 },
  { 产品类别: '耗材用品', 销售额: 1960000, 利润: 336000, 数量: 2440 },
  { 产品类别: '商用软件', 销售额: 1760000, 利润: 512000, 数量: 280 }
]

const salespersonRows = [
  { 销售员: '张伟', 销售额: 1680000, 目标金额: 1500000, 完成率: 112, 客户数: 18 },
  { 销售员: '李娜', 销售额: 1510000, 目标金额: 1450000, 完成率: 104, 客户数: 16 },
  { 销售员: '王强', 销售额: 1320000, 目标金额: 1400000, 完成率: 94, 客户数: 14 },
  { 销售员: '赵敏', 销售额: 1240000, 目标金额: 1180000, 完成率: 105, 客户数: 13 },
  { 销售员: '陈杰', 销售额: 980000, 目标金额: 1100000, 完成率: 89, 客户数: 11 }
]

const targetRows = [
  { 区域: '华东', 年度目标: 15200000, 已完成: 12840000, 完成率: 84 },
  { 区域: '华南', 年度目标: 13200000, 已完成: 11160000, 完成率: 85 },
  { 区域: '华北', 年度目标: 11800000, 已完成: 9420000, 完成率: 80 },
  { 区域: '西南', 年度目标: 8400000, 已完成: 7060000, 完成率: 84 },
  { 区域: '西北', 年度目标: 6200000, 已完成: 4680000, 完成率: 75 }
]

const customerRows = [
  { 客户等级: '战略客户', 客户数: 6, 销售额: 3580000, 利润: 861000 },
  { 客户等级: '重点客户', 客户数: 12, 销售额: 4260000, 利润: 792000 },
  { 客户等级: '成长客户', 客户数: 9, 销售额: 2160000, 利润: 356000 },
  { 客户等级: '普通客户', 客户数: 3, 销售额: 640000, 利润: 84000 }
]

const productRows = [
  { 产品名称: '智能会议屏', 标准价格: 19800, 成本价格: 14200, 库存数量: 86, 销售额: 1782000 },
  { 产品名称: '商用笔记本', 标准价格: 7600, 成本价格: 5940, 库存数量: 144, 销售额: 2128000 },
  { 产品名称: '人体工学椅', 标准价格: 1680, 成本价格: 980, 库存数量: 320, 销售额: 1186000 },
  { 产品名称: '云协作套件', 标准价格: 9800, 成本价格: 4300, 库存数量: 64, 销售额: 1568000 },
  { 产品名称: '打印耗材包', 标准价格: 460, 成本价格: 260, 库存数量: 1260, 销售额: 822000 }
]

const industryRows = [
  { 行业: '制造业', 客户数: 9, 销售额: 3860000, 利润: 742000 },
  { 行业: '金融', 客户数: 5, 销售额: 2960000, 利润: 713000 },
  { 行业: '教育', 客户数: 6, 销售额: 1880000, 利润: 318000 },
  { 行业: '医疗', 客户数: 4, 销售额: 1640000, 利润: 275000 },
  { 行业: '零售', 客户数: 6, 销售额: 1420000, 利润: 226000 }
]

const heatmapRows = [
  { 区域: '华东', 产品类别: '办公设备', 销售额: 1240000 },
  { 区域: '华东', 产品类别: '数码配件', 销售额: 920000 },
  { 区域: '华南', 产品类别: '办公设备', 销售额: 880000 },
  { 区域: '华南', 产品类别: '耗材用品', 销售额: 760000 },
  { 区域: '华北', 产品类别: '家具家居', 销售额: 690000 },
  { 区域: '西南', 产品类别: '商用软件', 销售额: 540000 }
]

const funnelRows = [
  { 阶段: '潜在客户', 数量: 126 },
  { 阶段: '需求确认', 数量: 86 },
  { 阶段: '方案报价', 数量: 54 },
  { 阶段: '合同谈判', 数量: 31 },
  { 阶段: '成交', 数量: 22 }
]

const radarRows = [
  { 销售额指数: 92, 利润指数: 84, 目标完成: 86, 库存健康: 78, 客户覆盖: 88, 增长速度: 81 }
]

const kpiRows = [
  { 销售额: 15120000, 利润: 3021000, 订单数: 508, 客户数: 30, 完成率: 84 }
]

const categoryDefs: Array<{
  id: string
  name: string
  icon: string
  source: 'sheet' | 'custom'
  charts: DemoChartDef[]
}> = [
  {
    id: 'demo-sheet-sales',
    name: '销售明细',
    icon: 'sheet',
    source: 'sheet',
    charts: [
      { title: '销售核心指标', question: '整体销售额、利润、订单与客户规模是否健康？', type: 'kpi_group', rows: kpiRows, items: [
        { label: '销售额', value_field: '销售额', format: 'number' },
        { label: '利润', value_field: '利润', format: 'number' },
        { label: '订单数', value_field: '订单数', format: 'number' },
        { label: '客户数', value_field: '客户数', format: 'number' },
        { label: '完成率', value_field: '完成率', format: 'percent' }
      ] },
      { title: '区域销售额对比', question: '不同区域销售贡献是否均衡？', type: 'bar', rows: salesByRegion, encoding: { x: { field: '区域' }, y: [{ field: '销售额' }] } },
      { title: '月度销售趋势', question: '最近 6 个月销售额是否持续增长？', type: 'line', rows: monthlySales, encoding: { x: { field: '月份' }, y: [{ field: '销售额' }] } },
      { title: '产品类别占比', question: '哪些产品类别贡献了主要收入？', type: 'donut', rows: categorySales, encoding: { x: { field: '产品类别' }, y: [{ field: '销售额' }] } },
      { title: '利润贡献排名', question: '利润最高的区域集中在哪里？', type: 'ranking', rows: salesByRegion, encoding: { x: { field: '区域' }, y: [{ field: '利润' }] } },
      { title: '品类销售利润组合', question: '品类销售额与利润是否同步？', type: 'combo', rows: categorySales, encoding: { x: { field: '产品类别' }, y: [{ field: '销售额', series_type: 'bar' }, { field: '利润', series_type: 'line' }] } },
      { title: '区域品类热力', question: '区域与品类的销售高点在哪里？', type: 'heatmap', rows: heatmapRows },
      { title: '销售明细样例', question: '关键订单字段的明细样例。', type: 'detail_table', rows: [
        { 订单号: 'SO-2026-0018', 日期: '2026-05-12', 区域: '华东', 产品名称: '智能会议屏', 销售额: 198000, 利润: 41200 },
        { 订单号: 'SO-2026-0021', 日期: '2026-05-13', 区域: '华南', 产品名称: '商用笔记本', 销售额: 152000, 利润: 28600 },
        { 订单号: 'SO-2026-0029', 日期: '2026-05-18', 区域: '华北', 产品名称: '云协作套件', 销售额: 117600, 利润: 52000 }
      ], expanded: true }
    ]
  },
  {
    id: 'demo-sheet-salesperson',
    name: '销售员信息',
    icon: 'sheet',
    source: 'sheet',
    charts: [
      { title: '销售员目标完成', question: '各销售员目标完成率排序如何？', type: 'horizontal_bar', rows: salespersonRows, encoding: { x: { field: '销售员' }, y: [{ field: '完成率' }] } },
      { title: '销售额与客户数', question: '销售额是否来自足够客户覆盖？', type: 'bubble', rows: salespersonRows, encoding: { x: { field: '销售员' } } },
      { title: '个人业绩矩形树图', question: '团队销售额贡献集中度如何？', type: 'treemap', rows: salespersonRows, encoding: { x: { field: '销售员' }, y: [{ field: '销售额' }] } },
      { title: '目标与实际对比', question: '哪些销售员与目标存在差距？', type: 'combo', rows: salespersonRows, encoding: { x: { field: '销售员' }, y: [{ field: '目标金额', series_type: 'bar' }, { field: '销售额', series_type: 'line' }] } },
      { title: '销售员完成率', question: '团队平均目标达成是否稳定？', type: 'gauge', rows: [{ 指标: '平均完成率', 完成率: 101 }], encoding: { x: { field: '指标' }, y: [{ field: '完成率' }] } },
      { title: '销售员客户覆盖', question: '客户数分布是否均衡？', type: 'pie', rows: salespersonRows, encoding: { x: { field: '销售员' }, y: [{ field: '客户数' }] } },
      { title: '销售员利润排名', question: '销售额高的人是否也带来利润？', type: 'ranking', rows: salespersonRows.map((r) => ({ ...r, 利润: Math.round(Number(r.销售额) * 0.2) })), encoding: { x: { field: '销售员' }, y: [{ field: '利润' }] } },
      { title: '销售员信息表', question: '销售员基础信息与负责区域。', type: 'table', rows: [
        { 姓名: '张伟', 部门: '华东销售部', 职级: '高级销售', 负责区域: '华东', 入职年限: 5 },
        { 姓名: '李娜', 部门: '华南销售部', 职级: '销售经理', 负责区域: '华南', 入职年限: 4 },
        { 姓名: '王强', 部门: '华北销售部', 职级: '销售顾问', 负责区域: '华北', 入职年限: 3 }
      ], expanded: true }
    ]
  },
  {
    id: 'demo-sheet-product',
    name: '产品信息',
    icon: 'sheet',
    source: 'sheet',
    charts: [
      { title: '产品库存健康', question: '库存是否集中在高价值产品？', type: 'bar', rows: productRows, encoding: { x: { field: '产品名称' }, y: [{ field: '库存数量' }] } },
      { title: '产品价格带分布', question: '标准价格分布是否覆盖主力价格带？', type: 'scatter', rows: productRows, encoding: { x: { field: '产品名称' } } },
      { title: '产品销售额占比', question: '收入是否集中在少数产品？', type: 'pie', rows: productRows, encoding: { x: { field: '产品名称' }, y: [{ field: '销售额' }] } },
      { title: '价格成本差额', question: '不同产品的毛利空间如何？', type: 'waterfall', rows: productRows.map((r) => ({ 产品名称: r.产品名称, 毛利空间: Number(r.标准价格) - Number(r.成本价格) })), encoding: { x: { field: '产品名称' }, y: [{ field: '毛利空间' }] } },
      { title: '库存结构树图', question: '库存规模在产品间如何分布？', type: 'treemap', rows: productRows, encoding: { x: { field: '产品名称' }, y: [{ field: '库存数量' }] } },
      { title: '产品利润率雷达', question: '主力产品在价格、成本、库存维度是否均衡？', type: 'radar', rows: radarRows },
      { title: '产品线销售趋势', question: '产品线月度销售走势是否分化？', type: 'multi_line', rows: monthlySales.map((r) => ({ 月份: r.月份, 办公设备: Number(r.销售额) * 0.36, 数码配件: Number(r.销售额) * 0.28, 商用软件: Number(r.销售额) * 0.18 })), encoding: { x: { field: '月份' }, y: [{ field: '办公设备' }, { field: '数码配件' }, { field: '商用软件' }] } },
      { title: '产品主数据', question: '产品基础价格、成本与库存样例。', type: 'detail_table', rows: productRows, expanded: true }
    ]
  },
  {
    id: 'demo-sheet-target',
    name: '区域目标',
    icon: 'sheet',
    source: 'sheet',
    charts: [
      { title: '年度目标完成率', question: '各区域年度目标达成进度如何？', type: 'gauge', rows: [{ 指标: '整体完成率', 完成率: 82 }], encoding: { x: { field: '指标' }, y: [{ field: '完成率' }] } },
      { title: '区域目标对比', question: '年度目标与已完成规模差距有多大？', type: 'combo', rows: targetRows, encoding: { x: { field: '区域' }, y: [{ field: '年度目标', series_type: 'bar' }, { field: '已完成', series_type: 'line' }] } },
      { title: '目标差距排行', question: '哪些区域需要优先追赶？', type: 'horizontal_bar', rows: targetRows.map((r) => ({ 区域: r.区域, 差距: Number(r.年度目标) - Number(r.已完成) })), encoding: { x: { field: '区域' }, y: [{ field: '差距' }] } },
      { title: '区域完成率分布', question: '目标完成率是否存在明显分层？', type: 'bar', rows: targetRows, encoding: { x: { field: '区域' }, y: [{ field: '完成率' }] } },
      { title: '季度目标拆解', question: '季度目标设置是否均衡？', type: 'stacked_bar', rows: [
        { 区域: '华东', Q1: 360, Q2: 390, Q3: 420, Q4: 350 },
        { 区域: '华南', Q1: 310, Q2: 340, Q3: 360, Q4: 310 },
        { 区域: '华北', Q1: 280, Q2: 300, Q3: 320, Q4: 280 }
      ], encoding: { x: { field: '区域' }, y: [{ field: 'Q1' }, { field: 'Q2' }, { field: 'Q3' }, { field: 'Q4' }] } },
      { title: '目标完成面积趋势', question: '整体达成进度是否逐月改善？', type: 'area', rows: monthlySales.map((r) => ({ 月份: r.月份, 完成金额: Number(r.销售额), 目标金额: Number(r.销售额) * 1.08 })), encoding: { x: { field: '月份' }, y: [{ field: '完成金额' }] } },
      { title: '区域目标地图视图', question: '省区目标完成的空间分布如何？', type: 'map', rows: targetRows, encoding: { x: { field: '区域' }, y: [{ field: '完成率' }] } },
      { title: '区域目标明细', question: '年度目标、已完成与负责人明细。', type: 'table', rows: targetRows.map((r, i) => ({ ...r, 负责人: ['张伟', '李娜', '王强', '赵敏', '陈杰'][i] })), expanded: true }
    ]
  },
  {
    id: 'demo-sheet-customer',
    name: '客户信息',
    icon: 'sheet',
    source: 'sheet',
    charts: [
      { title: '客户等级结构', question: '客户等级分布是否健康？', type: 'donut', rows: customerRows, encoding: { x: { field: '客户等级' }, y: [{ field: '客户数' }] } },
      { title: '行业销售贡献', question: '收入主要来自哪些行业？', type: 'treemap', rows: industryRows, encoding: { x: { field: '行业' }, y: [{ field: '销售额' }] } },
      { title: '客户等级利润', question: '不同等级客户的利润贡献如何？', type: 'bar', rows: customerRows, encoding: { x: { field: '客户等级' }, y: [{ field: '利润' }] } },
      { title: '行业客户数排名', question: '客户覆盖最多的行业是什么？', type: 'ranking', rows: industryRows, encoding: { x: { field: '行业' }, y: [{ field: '客户数' }] } },
      { title: '客户价值散点', question: '客户数与销售额是否匹配？', type: 'scatter', rows: industryRows, encoding: { x: { field: '行业' } } },
      { title: '客户规模漏斗', question: '客户从线索到成交的转化是否顺畅？', type: 'funnel', rows: funnelRows },
      { title: '行业利润趋势', question: '重点行业利润是否持续增长？', type: 'stacked_area', rows: monthlySales.map((r) => ({ 月份: r.月份, 制造业: Number(r.利润) * 0.32, 金融: Number(r.利润) * 0.26, 教育: Number(r.利润) * 0.18 })), encoding: { x: { field: '月份' }, y: [{ field: '制造业' }, { field: '金融' }, { field: '教育' }] } },
      { title: '客户基础信息', question: '客户行业、等级与合作信息样例。', type: 'detail_table', rows: [
        { 客户名称: '东辰制造', 行业: '制造业', 规模: '大型', 区域: '华东', 客户等级: '战略客户' },
        { 客户名称: '华南金融', 行业: '金融', 规模: '大型', 区域: '华南', 客户等级: '重点客户' },
        { 客户名称: '明德教育', 行业: '教育', 规模: '中型', 区域: '华北', 客户等级: '成长客户' }
      ], expanded: true }
    ]
  },
  {
    id: 'demo-custom-overview',
    name: '经营总览',
    icon: 'chart',
    source: 'custom',
    charts: [
      { title: '经营总览 KPI', question: '经营主指标是否达标？', type: 'kpi_group', rows: kpiRows, items: [
        { label: '销售额', value_field: '销售额', format: 'number' },
        { label: '利润', value_field: '利润', format: 'number' },
        { label: '订单', value_field: '订单数', format: 'number' },
        { label: '客户', value_field: '客户数', format: 'number' }
      ] },
      { title: '销售利润双轴', question: '销售额增长是否带动利润增长？', type: 'combo', rows: monthlySales, encoding: { x: { field: '月份' }, y: [{ field: '销售额', series_type: 'bar' }, { field: '利润', series_type: 'line' }] } },
      { title: '区域收入结构', question: '区域收入结构是否过于集中？', type: 'pie', rows: salesByRegion, encoding: { x: { field: '区域' }, y: [{ field: '销售额' }] } },
      { title: '利润率走势', question: '毛利率是否持续改善？', type: 'line', rows: monthlySales, encoding: { x: { field: '月份' }, y: [{ field: '毛利率' }] } },
      { title: '经营能力雷达', question: '销售、利润、目标、库存、客户能力是否均衡？', type: 'radar', rows: radarRows },
      { title: '产品收入树图', question: '产品收入贡献是否健康？', type: 'treemap', rows: productRows, encoding: { x: { field: '产品名称' }, y: [{ field: '销售额' }] } },
      { title: '成交漏斗', question: '销售漏斗在哪一阶段损耗最大？', type: 'funnel', rows: funnelRows },
      { title: '经营明细汇总', question: '核心经营数据摘要。', type: 'table', rows: salesByRegion, expanded: true }
    ]
  },
  {
    id: 'demo-custom-target',
    name: '目标达成',
    icon: 'chart',
    source: 'custom',
    charts: [
      { title: '总目标完成率', question: '整体年度目标完成到什么程度？', type: 'gauge', rows: [{ 指标: '完成率', 完成率: 84 }], encoding: { x: { field: '指标' }, y: [{ field: '完成率' }] } },
      { title: '区域目标达成', question: '各区域完成率排名。', type: 'ranking', rows: targetRows, encoding: { x: { field: '区域' }, y: [{ field: '完成率' }] } },
      { title: '目标缺口瀑布', question: '目标缺口主要来自哪些区域？', type: 'waterfall', rows: targetRows.map((r) => ({ 区域: r.区域, 缺口: Number(r.年度目标) - Number(r.已完成) })), encoding: { x: { field: '区域' }, y: [{ field: '缺口' }] } },
      { title: '季度目标堆叠', question: '季度目标压力分布如何？', type: 'stacked_bar', rows: [
        { 区域: '华东', Q1: 360, Q2: 390, Q3: 420, Q4: 350 },
        { 区域: '华南', Q1: 310, Q2: 340, Q3: 360, Q4: 310 },
        { 区域: '华北', Q1: 280, Q2: 300, Q3: 320, Q4: 280 },
        { 区域: '西南', Q1: 190, Q2: 210, Q3: 230, Q4: 210 }
      ], encoding: { x: { field: '区域' }, y: [{ field: 'Q1' }, { field: 'Q2' }, { field: 'Q3' }, { field: 'Q4' }] } },
      { title: '月度完成趋势', question: '目标完成节奏是否符合预期？', type: 'area', rows: monthlySales, encoding: { x: { field: '月份' }, y: [{ field: '销售额' }] } },
      { title: '目标风险热力', question: '区域与品类风险高点在哪里？', type: 'heatmap', rows: heatmapRows },
      { title: '销售员目标表现', question: '销售员目标完成是否分化？', type: 'horizontal_bar', rows: salespersonRows, encoding: { x: { field: '销售员' }, y: [{ field: '完成率' }] } },
      { title: '目标达成明细', question: '目标、完成、差距明细。', type: 'detail_table', rows: targetRows.map((r) => ({ ...r, 差距: Number(r.年度目标) - Number(r.已完成) })), expanded: true }
    ]
  },
  {
    id: 'demo-custom-customer-product',
    name: '客户产品',
    icon: 'chart',
    source: 'custom',
    charts: [
      { title: '客户产品矩阵', question: '客户等级与产品类别收入组合。', type: 'heatmap', rows: [
        { 客户等级: '战略客户', 产品类别: '办公设备', 销售额: 1280000 },
        { 客户等级: '战略客户', 产品类别: '商用软件', 销售额: 940000 },
        { 客户等级: '重点客户', 产品类别: '数码配件', 销售额: 1120000 },
        { 客户等级: '成长客户', 产品类别: '耗材用品', 销售额: 560000 },
        { 客户等级: '普通客户', 产品类别: '家具家居', 销售额: 260000 }
      ] },
      { title: '行业产品销售', question: '行业对产品类别的偏好如何？', type: 'stacked_bar', rows: [
        { 行业: '制造业', 办公设备: 1260, 数码配件: 880, 商用软件: 620 },
        { 行业: '金融', 办公设备: 920, 数码配件: 640, 商用软件: 960 },
        { 行业: '教育', 办公设备: 680, 数码配件: 520, 商用软件: 410 },
        { 行业: '医疗', 办公设备: 540, 数码配件: 480, 商用软件: 390 }
      ], encoding: { x: { field: '行业' }, y: [{ field: '办公设备' }, { field: '数码配件' }, { field: '商用软件' }] } },
      { title: '客户等级收入', question: '不同等级客户带来的收入占比。', type: 'donut', rows: customerRows, encoding: { x: { field: '客户等级' }, y: [{ field: '销售额' }] } },
      { title: '产品客户气泡', question: '产品收入、库存与客户覆盖是否匹配？', type: 'bubble', rows: productRows.map((r) => ({ ...r, 客户数: Math.round(Number(r.销售额) / 120000) })), encoding: { x: { field: '产品名称' } } },
      { title: '行业利润排名', question: '哪些行业带来的利润最高？', type: 'ranking', rows: industryRows, encoding: { x: { field: '行业' }, y: [{ field: '利润' }] } },
      { title: '产品复购漏斗', question: '从购买到复购的留存情况。', type: 'funnel', rows: [
        { 阶段: '购买客户', 数量: 30 },
        { 阶段: '二次购买', 数量: 21 },
        { 阶段: '跨品类购买', 数量: 14 },
        { 阶段: '年度续购', 数量: 9 }
      ] },
      { title: '客户产品趋势', question: '重点客户产品收入是否稳定增长？', type: 'multi_line', rows: monthlySales.map((r) => ({ 月份: r.月份, 战略客户: Number(r.销售额) * 0.42, 重点客户: Number(r.销售额) * 0.34, 成长客户: Number(r.销售额) * 0.18 })), encoding: { x: { field: '月份' }, y: [{ field: '战略客户' }, { field: '重点客户' }, { field: '成长客户' }] } },
      { title: '客户产品明细', question: '客户与产品交叉销售样例。', type: 'detail_table', rows: [
        { 客户名称: '东辰制造', 产品类别: '办公设备', 销售额: 820000, 利润: 172000 },
        { 客户名称: '华南金融', 产品类别: '商用软件', 销售额: 760000, 利润: 312000 },
        { 客户名称: '明德教育', 产品类别: '数码配件', 销售额: 420000, 利润: 76000 }
      ], expanded: true }
    ]
  }
]

function columnsOf(rows: DemoRow[], explicit?: string[]) {
  if (explicit?.length) return explicit
  return Object.keys(rows[0] || {})
}

function buildChart(categoryId: string, def: DemoChartDef, index: number, offset: number) {
  const columns = columnsOf(def.rows, def.columns)
  return {
    id: `${categoryId}-chart-${index + 1}`,
    category_id: categoryId,
    categoryId,
    title: def.title,
    question: def.question,
    description: def.question,
    chart_type: def.type,
    chartType: def.type,
    sql: '-- demo data chart',
    on_board: true,
    onBoard: true,
    collapsed: false,
    expanded: def.expanded ?? !['kpi', 'pie', 'donut', 'gauge'].includes(def.type),
    board_order: offset + index,
    boardOrder: offset + index,
    encoding: def.encoding || {},
    items: def.items || [],
    layout: def.type === 'kpi_group' ? { max_per_row: 5 } : {},
    intent_type: 'demo',
    preview: { columns, rows: def.rows },
    tablePreview: { columns, rows: def.rows }
  }
}

export function createDemoBIConfig() {
  const categories = categoryDefs.map((cat) => ({
    id: cat.id,
    name: cat.name,
    display_name: cat.name,
    icon: cat.icon,
    source: cat.source,
    sheet_key: cat.source === 'sheet' ? cat.name : undefined,
    table_name: cat.source === 'sheet' ? cat.name : undefined
  }))

  return {
    version: 3,
    file_id: 'demo-sales-bi',
    demo: true,
    categories: categories.filter((cat) => cat.source === 'sheet'),
    custom_categories: categories.filter((cat) => cat.source === 'custom'),
    global_filters: [
      { field: '区域', label: '区域', options: ['华东', '华南', '华北', '西南', '西北'] },
      { field: '产品类别', label: '产品类别', options: ['办公设备', '数码配件', '家具家居', '耗材用品', '商用软件'] },
      { field: '客户等级', label: '客户等级', options: ['战略客户', '重点客户', '成长客户', '普通客户'] }
    ],
    charts: categoryDefs.flatMap((cat, catIndex) =>
      cat.charts.map((chart, chartIndex) => buildChart(cat.id, chart, chartIndex, catIndex * 10))
    )
  }
}
