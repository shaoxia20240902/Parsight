import { getAuthToken, handleUnauthorized } from '../utils/auth'

export interface SSEMessage<T = any> {
  /** 解析后的 JSON 数据 */
  data: T
  /** 原始 SSE 行内容（包含 data: 前缀） */
  raw: string
}

export interface SSEStreamOptions {
  /** 请求方法 */
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  /** 请求体（仅 POST/PUT 有效） */
  body?: BodyInit | null
  /** 额外的请求头 */
  headers?: Record<string, string>
  /** 自定义错误提示前缀 */
  errorPrefix?: string
}

/**
 * 创建 SSE 流并返回异步生成器。
 *
 * 使用示例：
 * ```ts
 * for await (const { data } of createSSEStream('/api/events')) {
 *   console.log(data)
 * }
 * ```
 */
export async function* createSSEStream<T = any>(
  url: string,
  options: SSEStreamOptions = {}
): AsyncGenerator<SSEMessage<T>, void> {
  const { method = 'POST', body = null, headers = {}, errorPrefix = '流式请求失败' } = options
  const token = getAuthToken()

  const response = await fetch(url, {
    method,
    body,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  })

  if (!response.ok) {
    if (response.status === 401) {
      handleUnauthorized()
      throw new Error('登录已过期，请重新登录')
    }
    let detail = errorPrefix
    try {
      const err = await response.json()
      detail = err.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('当前浏览器不支持流式响应')
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
      const raw = line.slice(6)
      try {
        const data = JSON.parse(raw) as T
        yield { data, raw: line }
      } catch {
        // 跳过解析失败的行
      }
    }
  }
}

/**
 * 将 SSE 流消费为 Promise，适用于只需要最终结果的简单场景。
 */
export async function consumeSSEStream<T = any>(
  url: string,
  options: SSEStreamOptions = {},
  onEvent?: (data: T) => void
): Promise<T | undefined> {
  let finalData: T | undefined
  for await (const { data } of createSSEStream<T>(url, options)) {
    onEvent?.(data)
    finalData = data
  }
  return finalData
}
