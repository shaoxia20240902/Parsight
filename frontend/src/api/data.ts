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
    timeout: 120000
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
  return new Promise((resolve, reject) => {
    const token = localStorage.getItem('xlsx-bi-token')
    const formData = new FormData()
    formData.append('file', file)
    formData.append('space_id', spaceId)
    formData.append('mode', mode)

    fetch('/api/upload/reimport/stream', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData
    }).then(async (response) => {
      if (!response.ok) {
        let detail = '更新失败'
        try {
          const err = await response.json()
          detail = err.detail || detail
        } catch { /* ignore */ }
        reject(new Error(detail))
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        reject(new Error('不支持流式响应'))
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            onProgress(data)
            if (data.step === 'done') resolve(data.data)
            if (data.step === 'error') reject(new Error(data.message || '更新失败'))
          } catch { /* skip */ }
        }
      }
    }).catch(reject)
  })
}

/** 导出空间数据为 XLSX */
export const exportSpaceData = async (spaceId: string, filename?: string) => {
  const token = localStorage.getItem('xlsx-bi-token')
  const response = await fetch(`/api/data/export?space_id=${encodeURIComponent(spaceId)}`, {
    headers: { Authorization: `Bearer ${token}` }
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

/** SSE 流式上传文件 */
export const uploadFileStream = (file: File, spaceId: string, onProgress: (event: any) => void): Promise<any> => {
  return new Promise((resolve, reject) => {
    const token = localStorage.getItem('xlsx-bi-token')
    const formData = new FormData()
    formData.append('file', file)
    if (spaceId) {
      formData.append('space_id', spaceId)
    }

    fetch('/api/upload/stream', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`
      },
      body: formData
    }).then(async (response) => {
      if (!response.ok) {
        const err = await response.json()
        reject(new Error(err.detail || '上传失败'))
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        reject(new Error('不支持流式响应'))
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              onProgress(data)
              if (data.step === 'done') {
                resolve(data.data)
              }
              if (data.step === 'error') {
                reject(new Error(data.message))
              }
            } catch (e) {
              // 跳过解析失败的行
            }
          }
        }
      }
    }).catch(reject)
  })
}

export default api
