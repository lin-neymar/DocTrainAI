/**
 * Axios 实例：自动带 token；统一解包 {code,message,data}；
 * 401 清登录态并跳转登录；403/409/500 用 message 提示。
 */
import axios, { type AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

import router from '@/router'
import { clearToken, getToken } from '@/utils/token'

/** 后端统一响应：{ code, message, data } */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

const baseURL = import.meta.env.VITE_API_BASE_URL || ''

export const request = axios.create({
  baseURL,
  timeout: 15000,
})

// 实现：请求头自动附加 Bearer token
request.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 实现：业务 code≠0 当失败；HTTP 错误按规约提示并处理 401
request.interceptors.response.use(
  (response) => {
    // 文件下载等非 JSON 场景后续再分支；阶段 1 业务接口均为统一 JSON
    const body = response.data as ApiResponse
    if (body && typeof body.code === 'number' && body.code !== 0) {
      const msg = body.message || 'request failed'
      if (body.code === 40100) {
        void handleUnauthorized()
      } else if ([40300, 40900, 50000].includes(body.code) || body.code >= 40000) {
        ElMessage.error(msg)
      }
      return Promise.reject(new Error(msg))
    }
    return body?.data as never
  },
  (error: AxiosError<ApiResponse>) => {
    const status = error.response?.status
    const msg =
      error.response?.data?.message || error.message || '网络错误，请稍后重试'

    if (status === 401) {
      void handleUnauthorized()
    } else if (status === 403 || status === 409 || (status !== undefined && status >= 500)) {
      ElMessage.error(msg)
    } else if (status !== undefined) {
      ElMessage.error(msg)
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  },
)

// 实现：401 清 token + 重置 user store，并跳转登录（避免循环依赖用动态 import）
async function handleUnauthorized(): Promise<void> {
  clearToken()
  const { useUserStore } = await import('@/stores/user')
  useUserStore().resetSession()

  const current = router.currentRoute.value
  if (current.path !== '/login') {
    await router.replace({
      path: '/login',
      query: { redirect: current.fullPath },
    })
  }
}
