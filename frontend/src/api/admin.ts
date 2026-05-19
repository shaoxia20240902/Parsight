import api from './index'

export interface AdminUser {
  id: string
  username: string
  display_name: string
  is_admin: boolean
  created_at: string
}

export interface AdminLogSource {
  key: string
  name: string
  description: string
  enabled: boolean
}

export interface BILogRun {
  run_id: string
  file_id: string
  started_at: string
  updated_at: string
  status: 'completed' | 'failed' | 'running_or_interrupted'
  entry_count: number
  step_count: number
  error_count: number
  warn_count: number
  chart_count?: string | number | null
  dropped_count?: string | number | null
  last_step: string
  last_message: string
}

export interface BILogEntry {
  time: string
  level: string
  step: string
  run_id: string
  file_id: string
  message: string
  location: Record<string, any>
  extra: Record<string, any>
  exception?: string
}

export const listUsers = () => api.get<{ data: AdminUser[] }>('/admin/users')

export const listAdminLogSources = () =>
  api.get<{ data: AdminLogSource[] }>('/admin/logs/sources')

export const listBILogRuns = (limit = 50) =>
  api.get<{ data: BILogRun[] }>('/admin/logs/bi/runs', { params: { limit } })

export const getBILogRun = (runId: string) =>
  api.get<{ data: { summary: BILogRun; entries: BILogEntry[] } }>(
    `/admin/logs/bi/runs/${encodeURIComponent(runId)}`
  )

export const createUser = (payload: {
  username: string
  password: string
  display_name?: string
}) => api.post('/admin/users', payload)

export const deleteUser = (userId: string) =>
  api.delete(`/admin/users/${encodeURIComponent(userId)}`)

export interface LLMConfigItem {
  id: string
  name: string
  api_base: string
  api_key: string
  primary_model: string
  alt_model: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export const listLLMConfigs = () =>
  api.get<{ data: LLMConfigItem[] }>('/admin/llm-configs')

export const createLLMConfig = (payload: Omit<LLMConfigItem, 'id' | 'created_at' | 'updated_at'>) =>
  api.post<{ data: LLMConfigItem }>('/admin/llm-configs', payload)

export const updateLLMConfig = (id: string, payload: Partial<Omit<LLMConfigItem, 'id' | 'created_at' | 'updated_at'>>) =>
  api.put<{ data: LLMConfigItem }>(`/admin/llm-configs/${encodeURIComponent(id)}`, payload)

export const deleteLLMConfig = (id: string) =>
  api.delete(`/admin/llm-configs/${encodeURIComponent(id)}`)

export const activateLLMConfig = (id: string) =>
  api.post<{ data: LLMConfigItem }>(`/admin/llm-configs/${encodeURIComponent(id)}/activate`)

export const testLLMConfig = (payload: { api_base: string; api_key: string; primary_model: string }) =>
  api.post<{ data: { success: boolean; model?: string; error?: string } }>('/admin/llm-configs/test', payload)

export interface AdminSpace {
  id: string
  name: string
  code: string
  description: string
  owner_id: string
  owner_name: string
  is_active: boolean
  created_at: string
}

export const listSpaces = () =>
  api.get<{ data: AdminSpace[] }>('/admin/spaces')

export const createSpace = (payload: { name: string; owner_id: string; code?: string; description?: string }) =>
  api.post('/admin/spaces', payload)

export const updateSpace = (id: string, payload: { name?: string; description?: string }) =>
  api.put(`/admin/spaces/${encodeURIComponent(id)}`, payload)

export const deleteSpace = (id: string) =>
  api.delete(`/admin/spaces/${encodeURIComponent(id)}`)
