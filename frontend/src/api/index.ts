import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('xlsx-bi-token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('xlsx-bi-token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const login = (username: string, password: string) => {
  return api.post('/auth/login', { username, password })
}

export const quickQA = (
  fileId: string,
  question: string,
  options?: {
    space_id?: string | null
    session_id?: string | null
    conversation_history?: Array<Record<string, any>>
  }
) => {
  return api.post(
    '/chat/quick-qa',
    {
      file_id: fileId,
      question,
      space_id: options?.space_id || null,
      session_id: options?.session_id || null,
      conversation_history: options?.conversation_history || [],
    },
    { timeout: 120000 }
  )
}

export const deepResearchUrl = '/api/chat/deep-research'

export const biBuilderChat = (payload: {
  file_id: string
  message?: string
  session_id?: string | null
  space_id?: string | null
  event?: Record<string, any>
}) => {
  return api.post('/chat/bi-builder', {
    file_id: payload.file_id,
    message: payload.message || '',
    session_id: payload.session_id || null,
    space_id: payload.space_id || null,
    event: payload.event || { type: 'user_message', payload: {} },
  })
}

export const healthCheck = () => {
  return api.get('/health')
}

export type BIProgressEvent = {
  step: string
  status?: string
  message?: string
  charts_count?: number
  categories_count?: number
  sheet_count?: number
  category_id?: string
  category_name?: string
  chart_id?: string
  chart_type?: string
  title?: string
  done_count?: number
  failed_count?: number
  questions_count?: number
  table_name?: string
  type_counts?: Record<string, number>
  generation_started_at?: string
  generation_finished_at?: string
  server_time?: string
  categories?: Array<Record<string, any>>
  global_filters?: Array<Record<string, any>>
  chart_plan?: Array<Record<string, any>>
  chart?: Record<string, any>
  data?: unknown
  // SSE 流式 thinking entry
  entry?: BIThinkingEntry
  // 表理解内容
  sheet_name?: string
  understanding_preview?: string
  understanding_length?: number
}

export const generateBIConfig = async (
  fileId: string,
  onEvent?: (event: BIProgressEvent) => void
) => {
  const token = localStorage.getItem('xlsx-bi-token')
  const response = await fetch(`/api/bi/generate/${fileId}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  })
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('xlsx-bi-token')
      window.location.href = '/login'
      throw new Error('登录已过期，请重新登录')
    }
    let detail = 'BI 配置生成失败'
    try {
      const err = await response.json()
      detail = err.detail || detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('当前浏览器不支持流式生成')

  const decoder = new TextDecoder()
  let buffer = ''
  let finalData: unknown = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const event = JSON.parse(line.slice(6)) as BIProgressEvent
      onEvent?.(event)
      if (event.step === 'error') {
        throw new Error(event.message || 'BI 配置生成失败')
      }
      if (event.step === 'bi_completed') {
        finalData = event.data
      }
    }
  }

  if (!finalData) throw new Error('BI 配置生成未返回结果')
  return { data: { code: 200, data: finalData } }
}

export type BIStatus = 'completed' | 'generating' | 'failed' | 'none' | 'blocked'

export type BIThinkingEntry = {
  id: string
  ts: string
  step: string
  level: string
  text: string
  run_id?: string
  category_id?: string
  category_name?: string
  sheet_name?: string
  table_name?: string
  role_name?: string
  scenario_name?: string
}

export const getBIThinking = (fileId: string, q?: string) => {
  return api.get<{
    code: number
    data: { entries: BIThinkingEntry[]; total: number }
  }>(`/bi/thinking/${fileId}`, { params: q ? { q } : {} })
}

export const getBIStatus = (fileId: string) => {
  return api.get<{
    code: number
    data: {
      status: BIStatus
      categories_count?: number
      charts_count?: number
      pending_tables?: string[]
      action?: string
      generation_started_at?: string
      generation_finished_at?: string
      server_time?: string
    }
  }>(`/bi/status/${fileId}`)
}

export const getBIConfig = (fileId: string) => {
  return api.get(`/bi/config/${fileId}`)
}

export const getBIChartData = (
  fileId: string,
  chartId: string,
  filters?: Record<string, any>,
  chartFilters?: Record<string, any>,
  page: number = 1,
  pageSize: number = 20
) => {
  return api.post('/bi/chart-data', {
    file_id: fileId,
    chart_id: chartId,
    filters: filters || null,
    chart_filters: chartFilters || null,
    page,
    page_size: pageSize,
  })
}

export const getBIFilterOptions = (fileId: string) => {
  return api.get(`/bi/filter-options/${fileId}`)
}

export const createBICategory = (fileId: string, name: string) => {
  return api.post('/bi/categories', {
    file_id: fileId,
    name,
  })
}

export const updateBICategory = (fileId: string, categoryId: string, name: string) => {
  return api.patch(`/bi/categories/${categoryId}`, {
    file_id: fileId,
    name,
  })
}

export const deleteBICategory = (fileId: string, categoryId: string) => {
  return api.delete(`/bi/categories/${categoryId}`, {
    params: { file_id: fileId },
  })
}

export const updateBIChart = (
  fileId: string,
  chartId: string,
  payload: {
    title: string
    description: string
    category_id: string
    items?: Array<Record<string, any>>
    encoding?: Record<string, any>
    layout?: Record<string, any>
  }
) => {
  return api.patch(`/bi/charts/${chartId}`, {
    file_id: fileId,
    title: payload.title,
    description: payload.description,
    category_id: payload.category_id,
    items: payload.items,
    encoding: payload.encoding,
    layout: payload.layout,
  })
}

export const regenerateChart = (
  fileId: string,
  chartId: string,
  userRequirement: string
) => {
  return api.post('/bi/regenerate-chart', {
    file_id: fileId,
    chart_id: chartId,
    user_requirement: userRequirement,
  })
}

export const getChatRecommendations = (fileId: string) => {
  return api.get<{
    code: number
    data: {
      questions: {
        insight_groups?: Array<{ title: string; questions: string[] }>
        deep_questions?: string[]
        builder_questions?: string[]
      } | null
      status: string
    }
  }>(`/chat/recommendations`, { params: { file_id: fileId } })
}

export default api
