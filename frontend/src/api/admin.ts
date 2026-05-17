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
