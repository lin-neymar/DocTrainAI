/**
 * Axios 实例（W0：只接 baseURL 与统一解包；登录态 / 401 跳转留给 W1）。
 */
import axios from 'axios'

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

// 实现：成功时只把业务 data 交给调用方；非 0 code 抛错（W1 再接 ElMessage）
request.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse
    if (body && typeof body.code === 'number' && body.code !== 0) {
      return Promise.reject(new Error(body.message || 'request failed'))
    }
    return body?.data as never
  },
  (error) => Promise.reject(error),
)
