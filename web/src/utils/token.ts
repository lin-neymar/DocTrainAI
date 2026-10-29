/** Access Token 仅存 localStorage；用户/权限码禁止持久化（WEB_SPEC）。 */

const TOKEN_KEY = 'doctrain_access_token'

// 实现：读取本地 token
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

// 实现：写入 token
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

// 实现：清除 token
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}
