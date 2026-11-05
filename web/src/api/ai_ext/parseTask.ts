/**
 * 解析任务接口：查询某文档最新解析任务（阶段 2 解析状态列）。
 * 权限由后端校验 doc:read；该文档从未解析过时 data 为 null。
 */
import { request } from '@/utils/request'

export type ParseTaskStatus = 'pending' | 'running' | 'succeeded' | 'failed'

export interface ParseTask {
  id: string
  doc_id: string
  status: ParseTaskStatus
  /** 失败原因摘要；成功时恒为 null */
  error_summary: string | null
  created_at: string
  updated_at: string
}

// 实现：GET /api/v1/parse-tasks/by-doc/{docId}/latest 返回最新任务或 null
export function fetchLatestParseTaskApi(docId: string) {
  return request.get<unknown, ParseTask | null>(`/api/v1/parse-tasks/by-doc/${docId}/latest`)
}
