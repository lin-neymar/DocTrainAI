/** 认证接口：login / me / logout */
import { request } from '@/utils/request'

export interface LoginResult {
  access_token: string
  token_type: string
}

export interface MeResult {
  user: { id: string; username: string }
  dept: { id: string; name: string }
  role_names: string[]
  permission_codes: string[]
  theme_primary?: string | null
}

// 实现：PUT /api/v1/auth/me/theme
export function updateMyThemeApi(theme_primary: string | null) {
  return request.put<unknown, { theme_primary: string | null }>('/api/v1/auth/me/theme', {
    theme_primary,
  })
}

// 实现：POST /api/v1/auth/login
export function loginApi(username: string, password: string) {
  return request.post<unknown, LoginResult>('/api/v1/auth/login', {
    username,
    password,
  })
}

// 实现：GET /api/v1/auth/me
export function fetchMeApi() {
  return request.get<unknown, MeResult>('/api/v1/auth/me')
}

// 实现：POST /api/v1/auth/logout
export function logoutApi() {
  return request.post<unknown, unknown>('/api/v1/auth/logout')
}
