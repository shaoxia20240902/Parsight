/** 认证相关工具函数 */

const TOKEN_KEY = 'xlsx-bi-token'

/** 获取当前登录 token */
export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

/** 设置登录 token */
export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

/** 清除登录 token */
export function clearAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

/** 获取带认证头的请求头对象 */
export function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** 处理 401 未授权：清理 token 并跳转登录页 */
export function handleUnauthorized(): void {
  clearAuthToken()
  window.location.href = '/login'
}
