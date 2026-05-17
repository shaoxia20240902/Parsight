/** 对话推荐问题 Mock（发送逻辑后续接入） */

export interface InsightPromptGroup {
  title: string
  questions: [string, string, string]
}

export const INSIGHT_PROMPT_GROUPS: InsightPromptGroup[] = [
  {
    title: '销售表现',
    questions: [
      '本月各区域销售额排名如何？',
      '哪个区域同比增长最快？',
      '销售额最低的区域是哪里？'
    ]
  },
  {
    title: '客户与订单',
    questions: [
      '已完成订单占比多少？',
      '处理中订单主要集中在哪些状态？',
      '取消订单的主要原因是什么？'
    ]
  },
  {
    title: '渠道与库存',
    questions: [
      '各渠道 ROI 表现如何？',
      '库存周转最慢的 SKU 有哪些？',
      '渠道投入与产出是否匹配？'
    ]
  }
]

export const DEEP_PROMPT_QUESTIONS: string[] = [
  '华东区域近三个月销售额持续下滑，请从渠道、品类、客户分层三个维度做根因分析，并给出可验证的假设。',
  '对比线上与线下渠道的投资回报率差异，哪些因素可能导致线下渠道效率偏低？',
  '库存周转异常集中在哪些 SKU 与仓库？请梳理可能的供应链或需求预测问题。'
]

export const BUILDER_PROMPT_QUESTIONS: string[] = [
  '我想看客户销售额 Top10，同时准备 Bottom10',
  '帮我看各区域本月销售额对比，以及近 6 个月趋势',
  '列出还没回款的客户清单，并放到销售分析里'
]
