/**
 * 对话接口封装（阶段 3）：会话 CRUD 与流式发送。
 * 权限由后端校验 agent:chat；SSE 读取统一走 utils/sse.ts。
 */
import { request } from '@/utils/request'
import { openSse, type SseEvent } from '@/utils/sse'

/** 引用结构固定五字段（SERVER_SPEC 阶段 3） */
export interface Citation {
  doc_id: string
  doc_title: string
  chunk_id: string
  location: Record<string, unknown> | null
  snippet: string
}

export interface ChatSessionItem {
  id: string
  created_at: string
}

export interface ChatMessageItem {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  refused: boolean
  citations: Citation[] | null
  created_at: string
}

/** 统一分页结构（与后端 page_data 对齐） */
export interface PageData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// 实现：新建会话
export function createSessionApi() {
  return request.post<unknown, ChatSessionItem>('/api/v1/chat/sessions')
}

// 实现：会话列表（更新时间倒序分页）
export function listSessionsApi(page = 1, pageSize = 20) {
  return request.get<unknown, PageData<ChatSessionItem>>('/api/v1/chat/sessions', {
    params: { page, page_size: pageSize },
  })
}

// 实现：会话消息（时间正序，含引用）
export function listMessagesApi(sessionId: string) {
  return request.get<unknown, ChatMessageItem[]>(`/api/v1/chat/sessions/${sessionId}/messages`)
}

// 实现：发送消息（SSE 流式）；四种事件统一交给 onEvent 处理
export function sendMessageStreamApi(
  sessionId: string,
  content: string,
  onEvent: (event: SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return openSse({
    url: `/api/v1/chat/sessions/${sessionId}/messages`,
    init: { method: 'POST', body: JSON.stringify({ content }) },
    onEvent,
    signal,
  })
}
