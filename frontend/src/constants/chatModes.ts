import type { Component } from 'vue'
import { ChatDotRound, Cpu, SetUp } from '@element-plus/icons-vue'

export type ChatModeId = 'insight' | 'deep' | 'builder'

export interface ChatModeConfig {
  id: ChatModeId
  label: string
  shortLabel: string
  description: string
  welcomeTitle: string
  /** 右侧主区角色插画 */
  avatar: string
  /** 左侧列表用小图标 */
  icon: Component
  switchTransition: boolean
  accent: string
  accentSoft: string
}

export const CHAT_MODES: ChatModeConfig[] = [
  {
    id: 'insight',
    label: '快速问答',
    shortLabel: '快问',
    description: '先识别意图，再快速查询并给出结论',
    welcomeTitle: '超级问答智能体 · 快速问答',
    avatar: '/chat/mode-insight.png',
    icon: ChatDotRound,
    switchTransition: false,
    accent: '#D97757',
    accentSoft: 'rgba(217, 119, 87, 0.12)'
  },
  {
    id: 'deep',
    label: '深度洞察',
    shortLabel: '深度',
    description: '参考 ReAct 流程做澄清、拆解、查询和报告',
    welcomeTitle: '超级问答智能体 · 深度洞察',
    avatar: '/chat/mode-deep.png',
    icon: Cpu,
    switchTransition: true,
    accent: '#8B6B4A',
    accentSoft: 'rgba(139, 107, 74, 0.12)'
  },
  {
    id: 'builder',
    label: '生成 BI',
    shortLabel: 'BI',
    description: '把业务问题转成可确认、可写入的 BI 图表',
    welcomeTitle: '超级问答智能体 · 生成 BI',
    avatar: '/chat/mode-builder.png',
    icon: SetUp,
    switchTransition: true,
    accent: '#5C7A6B',
    accentSoft: 'rgba(92, 122, 107, 0.12)'
  }
]

export const CHAT_MODE_MAP = Object.fromEntries(
  CHAT_MODES.map((m) => [m.id, m])
) as Record<ChatModeId, ChatModeConfig>

export function getChatMode(id: ChatModeId): ChatModeConfig {
  return CHAT_MODE_MAP[id]
}
