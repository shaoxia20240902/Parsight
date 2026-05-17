import api from './index'

export interface AdminUser {
  id: string
  username: string
  display_name: string
  is_admin: boolean
  created_at: string
}

export const listUsers = () => api.get<{ data: AdminUser[] }>('/admin/users')

export const createUser = (payload: {
  username: string
  password: string
  display_name?: string
}) => api.post('/admin/users', payload)

export const deleteUser = (userId: string) =>
  api.delete(`/admin/users/${encodeURIComponent(userId)}`)
