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
    label: '洞察',
    shortLabel: '洞察',
    description: '基于当前数据的快速问答与解读',
    welcomeTitle: '有什么可以帮你洞察的？',
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
    description: '多步推理、根因追溯与对比分析',
    welcomeTitle: '开始一次深度分析',
    avatar: '/chat/mode-deep.png',
    icon: Cpu,
    switchTransition: true,
    accent: '#8B6B4A',
    accentSoft: 'rgba(139, 107, 74, 0.12)'
  },
  {
    id: 'builder',
    label: '构建者',
    shortLabel: '构建',
    description: '用销售语言创建你想看的报表',
    welcomeTitle: '想看哪类销售报表？',
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
