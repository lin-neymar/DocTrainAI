/**
 * SSE 读取统一入口（阶段 3）：浏览器原生流式读取，不引入第三方 SSE 框架。
 * 组件只消费已解析好的 delta / citation / done / error 四种事件。
 */
import type { Citation } from '@/api/ai_ext/chat'
import { handleUnauthorized } from '@/utils/request'
import { getToken } from '@/utils/token'

/** 已解析的 SSE 事件联合类型（对应 SERVER_SPEC 阶段 3 四种事件） */
export type SseEvent =
  | { type: 'delta'; text: string }
  | { type: 'citation'; citation: Citation }
  | { type: 'done'; messageId: string; refused: boolean }
  | { type: 'error'; message: string }

export interface SseRequestOptions {
  /** 相对后端根路径（如 /api/v1/chat/sessions/xxx/messages） */
  url: string
  init?: RequestInit
  /** 每解析出一个完整事件回调一次 */
  onEvent: (event: SseEvent) => void
  signal?: AbortSignal
}

// 实现：解析一个 SSE 帧（event: / data: 两行）为事件对象；未知事件或坏帧返回 null
function parseFrame(eventName: string | undefined, data: string | undefined): SseEvent | null {
  if (!eventName || data === undefined) return null
  try {
    const payload = JSON.parse(data) as Record<string, unknown>
    switch (eventName) {
      case 'delta':
        return { type: 'delta', text: String(payload.text ?? '') }
      case 'citation':
        return { type: 'citation', citation: payload as unknown as Citation }
      case 'done':
        return {
          type: 'done',
          messageId: String(payload.message_id ?? ''),
          refused: Boolean(payload.refused),
        }
      case 'error':
        return { type: 'error', message: String(payload.message ?? '未知错误') }
      default:
        return null
    }
  } catch {
    return null
  }
}

// 实现：发起 SSE 请求并流式解析；HTTP 非 2xx 按统一 JSON 错误抛出（401 清会话）
export async function openSse(options: SseRequestOptions): Promise<void> {
  const { url, init, onEvent, signal } = options
  const baseURL = import.meta.env.VITE_API_BASE_URL || ''
  const token = getToken()
  const response = await fetch(`${baseURL}${url}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
    signal,
  })

  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`
    try {
      const body = (await response.json()) as { message?: string; code?: number }
      if (body.message) message = body.message
      if (body.code === 40100 || response.status === 401) {
        void handleUnauthorized()
      }
    } catch {
      // 非 JSON 响应保持默认文案
    }
    throw new Error(message)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('当前浏览器不支持流式读取')
  }
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // 按空行切帧；最后一段可能不完整，留待下一轮拼接
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''
      for (const frame of frames) {
        if (!frame.trim()) continue
        let eventName: string | undefined
        let dataLine: string | undefined
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim()
          else if (line.startsWith('data:')) dataLine = line.slice(5).trim()
        }
        const event = parseFrame(eventName, dataLine)
        if (event) onEvent(event)
      }
    }
  } finally {
    reader.releaseLock()
  }
}
