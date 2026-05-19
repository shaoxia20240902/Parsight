/** 对话推荐问题 Mock（当动态推荐问题未生成时展示通用默认值） */

export interface InsightPromptGroup {
  title: string
  questions: [string, string, string]
}

export const INSIGHT_PROMPT_GROUPS: InsightPromptGroup[] = [
  {
    title: '数据分布',
    questions: [
      '各分组的数据量分布如何？',
      '数值最高的类别是哪些？',
      '不同维度间的对比情况如何？'
    ]
  },
  {
    title: '指标概览',
    questions: [
      '核心指标的汇总情况如何？',
      '哪些维度的数值占比较大？',
      '各记录类型的数量统计？'
    ]
  },
  {
    title: '趋势与排名',
    questions: [
      '按时间变化的走势如何？',
      'Top10 和 Bottom10 分别是哪些？',
      '各维度之间的差异程度如何？'
    ]
  }
]

export const DEEP_PROMPT_QUESTIONS: string[] = [
  '某类数据近阶段的变化趋势及可能原因分析',
  '各维度之间的关联性分析与潜在规律探索',
  '异常数据的识别与根因追溯'
]

export const BUILDER_PROMPT_QUESTIONS: string[] = [
  '查看某字段的 Top10 和 Bottom10 对比',
  '按某维度汇总对比，并展示变化趋势',
  '筛选特定条件的数据明细清单'
]
