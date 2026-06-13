import axios from 'axios'
import { getAuthHeaders } from '../utils/auth'
import { createSSEStream } from './sse'

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

// ========== 数据管理 ==========

/** 获取空间下所有动态表 */
export const getTables = (spaceId: string) => {
  return api.get('/data/tables', { params: { space_id: spaceId } })
}

/** 获取表的列信息 */
export const getTableColumns = (tableName: string) => {
  return api.get(`/data/table/${encodeURIComponent(tableName)}/columns`)
}

/** 分页查询表数据 + 模糊搜索 */
export const getTableRows = (
  tableName: string,
  page: number = 1,
  pageSize: number = 20,
  search: string = '',
  searchField: string = ''
) => {
  return api.get(`/data/table/${encodeURIComponent(tableName)}/rows`, {
    params: {
      page,
      page_size: pageSize,
      search,
      search_field: searchField
    }
  })
}

/** 获取表的 AI 六维理解（Markdown） */
export const getTableUnderstanding = (tableName: string, regenerate = false) => {
  return api.get(`/data/table/${encodeURIComponent(tableName)}/understanding`, {
    params: { regenerate },
    timeout: 1800000
  })
}

/** 保存用户编辑后的理解内容 */
export const saveTableUnderstanding = (tableName: string, content: string) => {
  return api.put(`/data/table/${encodeURIComponent(tableName)}/understanding`, { content })
}

/** 获取空间 Sheet 关联分析（Markdown） */
export const getRelations = (spaceId: string, regenerate = false) => {
  return api.get('/data/relations', {
    params: { space_id: spaceId, regenerate },
    timeout: 180000
  })
}

export interface ReimportValidationIssue {
  sheet_name: string
  type: string
  message: string
  detail?: string
  expected_columns?: string[]
  actual_columns?: string[]
  removed?: string[]
  added?: string[]
}

export interface ReimportValidationResult {
  valid: boolean
  issues: ReimportValidationIssue[]
  warnings: ReimportValidationIssue[]
  filename?: string
  sheet_count?: number
}

/** 校验更新文件字段是否与当前空间一致 */
export const validateReimport = (file: File, spaceId: string) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('space_id', spaceId)
  return api.post<{ data: ReimportValidationResult }>('/upload/validate-reimport', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  })
}

/** SSE 流式更新导入 */
export const reimportFileStream = (
  file: File,
  spaceId: string,
  mode: 'overwrite' | 'insert',
  onProgress: (event: any) => void
): Promise<any> => {
  return new Promise(async (resolve, reject) => {
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('space_id', spaceId)
      formData.append('mode', mode)

      for await (const { data } of createSSEStream('/api/upload/reimport/stream', {
        body: formData,
      })) {
        onProgress(data)
        if (data.step === 'done') {
          resolve(data.data)
          return
        }
        if (data.step === 'error') {
          reject(new Error(data.message || '更新失败'))
          return
        }
      }
    } catch (e) {
      reject(e)
    }
  })
}

/** 导出空间数据为 XLSX */
export const exportSpaceData = async (spaceId: string, filename?: string) => {
  const response = await fetch(`/api/data/export?space_id=${encodeURIComponent(spaceId)}`, {
    headers: getAuthHeaders(),
  })
  if (!response.ok) {
    let detail = '导出失败'
    try {
      const err = await response.json()
      detail = err.detail || detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'export.xlsx'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/** SSE 流式生成表理解 */
export const generateTableUnderstandingStream = (
  tableName: string,
  regenerate = false,
  onChunk: (chunk: string) => void,
  onDone?: (data: { content: string; verification_status: string; updated_at?: string }) => void,
  onError?: (message: string) => void
): Promise<void> => {
  return new Promise(async (resolve, reject) => {
    try {
      const url = `/api/data/table/${encodeURIComponent(tableName)}/understanding/stream?regenerate=${regenerate}`
      let fullContent = ''

      for await (const { data } of createSSEStream(url)) {
        if (data.chunk) {
          fullContent += data.chunk
          onChunk(data.chunk)
        }
        if (data.phase && data.data) {
          onDone?.(data.data)
        }
        if (data.done) {
          onDone?.(data.data || { content: fullContent, verification_status: 'verifying' })
          resolve()
          return
        }
        if (data.error) {
          onError?.(data.error)
          reject(new Error(data.error))
          return
        }
        if (data.status === 'generating') {
          reject(new Error('GENERATING_IN_BACKGROUND'))
          return
        }
      }
      resolve()
    } catch (e) {
      reject(e)
    }
  })
}

/** SSE 流式生成空间关联总结 */
export const generateRelationsStream = (
  spaceId: string,
  regenerate = false,
  onChunk: (chunk: string) => void,
  onDone?: (data: { content: string; content_initial?: string; verification_status: string; updated_at?: string }) => void,
  onError?: (message: string) => void
): Promise<void> => {
  return new Promise(async (resolve, reject) => {
    try {
      const url = `/api/data/relations/stream?space_id=${encodeURIComponent(spaceId)}&regenerate=${regenerate}`
      let fullContent = ''

      for await (const { data } of createSSEStream(url)) {
        if (data.chunk) {
          fullContent += data.chunk
          onChunk(data.chunk)
        }
        if (data.phase && data.data) {
          onDone?.(data.data)
        }
        if (data.done) {
          onDone?.(data.data || { content: fullContent, verification_status: 'completed' })
          resolve()
          return
        }
        if (data.error) {
          onError?.(data.error)
          reject(new Error(data.error))
          return
        }
      }
      resolve()
    } catch (e) {
      reject(e)
    }
  })
}

/** SSE 流式上传文件 */
export const uploadFileStream = (file: File, spaceId: string, onProgress: (event: any) => void): Promise<any> => {
  return new Promise(async (resolve, reject) => {
    try {
      const formData = new FormData()
      formData.append('file', file)
      if (spaceId) {
        formData.append('space_id', spaceId)
      }

      for await (const { data } of createSSEStream('/api/upload/stream', {
        body: formData,
      })) {
        onProgress(data)
        if (data.step === 'done') {
          resolve(data.data)
          return
        }
        if (data.step === 'error') {
          reject(new Error(data.message || '上传失败'))
          return
        }
      }
    } catch (e) {
      reject(e)
    }
  })
}

export default api
