import type { ChatModeId } from '../constants/chatModes'

export interface ChatSessionItem {
  id: string
  mode: ChatModeId
  title: string
  preview: string
  updatedAt: string
}

/** 对话会话 Mock（前端预览，后续对接 /chat/history） */
export const MOCK_CHAT_SESSIONS: ChatSessionItem[] = [
  {
    id: 's1',
    mode: 'insight',
    title: '各区域销售额对比',
    preview: '华东区域本月同比增长…',
    updatedAt: '2026-05-15T10:20:00'
  },
  {
    id: 's2',
    mode: 'insight',
    title: '订单状态分布',
    preview: '已完成订单占比 82%…',
    updatedAt: '2026-05-14T16:40:00'
  },
  {
    id: 's3',
    mode: 'deep',
    title: '渠道 ROI 根因分析',
    preview: '经三步推理，线下渠道…',
    updatedAt: '2026-05-13T09:15:00'
  },
  {
    id: 's4',
    mode: 'deep',
    title: '库存周转异常深挖',
    preview: '关联 SKU 与仓库维度…',
    updatedAt: '2026-05-12T14:30:00'
  },
  {
    id: 's5',
    mode: 'builder',
    title: '经营看板结构草案',
    preview: '建议 3 个分类 Tab…',
    updatedAt: '2026-05-11T11:00:00'
  },
  {
    id: 's6',
    mode: 'builder',
    title: '自动图表编排流程',
    preview: '先理解 Sheet，再生成…',
    updatedAt: '2026-05-10T18:22:00'
  }
]
