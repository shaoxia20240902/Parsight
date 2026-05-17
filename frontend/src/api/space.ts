import api from './index'

export interface Space {
  id: string
  seq_id?: number
  name: string
  code: string
  description: string
  is_active: boolean
  created_at: string
}

export const getSpaces = () => {
  return api.get('/spaces')
}

export const createSpace = (data: { name: string; code: string; description?: string }) => {
  return api.post('/spaces', data)
}

export const deleteSpace = (spaceId: string) => {
  return api.delete(`/spaces/${spaceId}`)
}

export const setActiveSpace = (spaceId: string) => {
  return api.put(`/spaces/${spaceId}/active`)
}

export const listFiles = (spaceId?: string) => {
  const params = spaceId ? `?space_id=${spaceId}` : ''
  return api.get(`/files${params}`)
}

export const getChatHistory = (spaceId?: string) => {
  const params = spaceId ? `?space_id=${spaceId}` : ''
  return api.get(`/chat/history${params}`)
}
