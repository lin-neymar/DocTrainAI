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

/** 下载接口成功时拦截器返回此结构（非统一 JSON data） */
export interface BlobDownload {
  blob: Blob
  filename: string | null
}

// 实现：从 Content-Disposition 解析文件名
function filenameFromDisposition(header: string | undefined): string | null {
  if (!header) return null
  const utf8 = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header)
  if (utf8?.[1]) {
    try {
      return decodeURIComponent(utf8[1].trim().replace(/^"|"$/g, ''))
    } catch {
      return utf8[1].trim()
    }
  }
  const plain = /filename\s*=\s*("?)([^";]+)\1/i.exec(header)
  return plain?.[2]?.trim() || null
}

// 实现：统一 JSON 业务错误提示
function rejectApiBody(body: ApiResponse): Promise<never> {
  const msg = body.message || 'request failed'
  if (body.code === 40100) {
    void handleUnauthorized()
  } else if ([40300, 40900, 50000].includes(body.code) || body.code >= 40000) {
    ElMessage.error(msg)
  }
  return Promise.reject(new Error(msg))
}

// 实现：业务 code≠0 当失败；blob 下载单独解包；HTTP 错误按规约提示
request.interceptors.response.use(
  async (response) => {
    // 下载原文件：后端直接返回 FileResponse，不是 {code,message,data}
    if (response.config.responseType === 'blob') {
      const blob = response.data as Blob
      const ct = String(response.headers['content-type'] || '')
      if (ct.includes('application/json')) {
        try {
          const body = JSON.parse(await blob.text()) as ApiResponse
          if (typeof body.code === 'number' && body.code !== 0) {
            return rejectApiBody(body)
          }
        } catch {
          return Promise.reject(new Error('下载失败'))
        }
        return Promise.reject(new Error('下载失败'))
      }
      const download: BlobDownload = {
        blob,
        filename: filenameFromDisposition(
          response.headers['content-disposition'] as string | undefined,
        ),
      }
      return download as never
    }

    const body = response.data as ApiResponse
    if (body && typeof body.code === 'number' && body.code !== 0) {
      return rejectApiBody(body)
    }
    return body?.data as never
  },
  async (error: AxiosError<ApiResponse | Blob>) => {
    const status = error.response?.status
    let msg = error.message || '网络错误，请稍后重试'
    const data = error.response?.data
    if (data instanceof Blob) {
      try {
        const body = JSON.parse(await data.text()) as ApiResponse
        if (body.message) msg = body.message
      } catch {
        // 保持默认 msg
      }
    } else if (data && typeof data === 'object' && 'message' in data && data.message) {
      msg = data.message
    }

    if (status === 401) {
      void handleUnauthorized()
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
