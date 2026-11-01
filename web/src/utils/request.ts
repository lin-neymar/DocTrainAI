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

// 实现：统一 JSON 业务错误提示（拒绝值为中文 Error，供页面 catch 展示）
function rejectApiBody(body: ApiResponse): Promise<never> {
  const msg = body.message || '请求失败'
  if (body.code === 40100) {
    void handleUnauthorized()
  } else if ([40300, 40900, 50000].includes(body.code) || body.code >= 40000) {
    ElMessage.error(msg)
  }
  return Promise.reject(new Error(msg))
}

// 实现：HTTP 错误时优先用后端 message，否则给中文兜底（避免 Axios 英文 status 文案）
function resolveErrorMessage(
  status: number | undefined,
  bodyMessage: string | undefined,
  axiosMessage: string | undefined,
): string {
  if (bodyMessage) return bodyMessage
  if (status === 401) return '用户名或密码错误'
  if (status === 403) return '没有权限执行此操作'
  if (status === 404) return '资源不存在'
  if (status === 409) return '操作冲突'
  if (status === 422) return '请求参数无效'
  if (status !== undefined && status >= 500) return '服务异常，请稍后重试'
  if (axiosMessage && !/status code/i.test(axiosMessage)) return axiosMessage
  return '网络错误，请稍后重试'
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
    const data = error.response?.data
    let bodyMessage: string | undefined
    if (data instanceof Blob) {
      try {
        const body = JSON.parse(await data.text()) as ApiResponse
        if (body.message) bodyMessage = body.message
      } catch {
        // ignore
      }
    } else if (data && typeof data === 'object' && 'message' in data && data.message) {
      bodyMessage = data.message
    }
    const msg = resolveErrorMessage(status, bodyMessage, error.message)

    if (status === 401) {
      // 登录失败等：不在拦截器弹窗（由页面 catch 展示），只清会话
      void handleUnauthorized()
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(new Error(msg))
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
