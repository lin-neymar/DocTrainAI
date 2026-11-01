/**
 * 文档接口：列表/下载 doc:read；上传 doc:create；改元数据与 audience doc:update；软删 doc:delete。
 * 可见性由后端 get_visible_doc_ids 裁剪；阶段 1 不展示解析状态。
 */
import { request, type BlobDownload } from '@/utils/request'

import type { PageResult } from './types'

export interface DocItem {
  id: string
  title: string
  dept_id: string
  /** 可见组织节点；选中节点子树内人员可读 */
  audience_dept_ids?: string[]
  original_filename: string
  extension: string
  size_bytes: number
  sha256: string
  uploaded_by: string
  /** pdf/md 恒为 true；office 在预览 PDF 已生成时为 true */
  preview_ready?: boolean
  created_at?: string
  updated_at?: string
}

export interface DocUpdateBody {
  title?: string
  dept_id?: string
  audience_dept_ids?: string[]
}

export interface DocListQuery {
  page: number
  pageSize: number
  /** 标题模糊筛选（可选） */
  title?: string
}

// 实现：GET /api/v1/docs 分页列表（可选 title）
export function fetchDocsApi(query: DocListQuery) {
  const params: Record<string, string | number> = {
    page: query.page,
    page_size: query.pageSize,
  }
  const title = query.title?.trim()
  if (title) params.title = title
  return request.get<unknown, PageResult<DocItem>>('/api/v1/docs', { params })
}

// 实现：POST /api/v1/docs multipart 上传（可选 audience JSON）
export function uploadDocApi(
  title: string,
  deptId: string,
  file: File,
  audienceDeptIds?: string[],
) {
  const form = new FormData()
  form.append('title', title)
  form.append('dept_id', deptId)
  form.append('file', file)
  if (audienceDeptIds !== undefined) {
    form.append('audience_dept_ids', JSON.stringify(audienceDeptIds))
  }
  return request.post<unknown, DocItem>('/api/v1/docs', form, {
    timeout: 120000,
  })
}

// 实现：PUT /api/v1/docs/{id} 改元数据与 audience
export function updateDocApi(docId: string, body: DocUpdateBody) {
  return request.put<unknown, DocItem>(`/api/v1/docs/${docId}`, body)
}

// 实现：DELETE /api/v1/docs/{id} 软删除（不删磁盘）
export function deleteDocApi(docId: string) {
  return request.delete<unknown, unknown>(`/api/v1/docs/${docId}`)
}

export interface DocBatchDeleteResult {
  deleted_count: number
}

// 实现：POST /api/v1/docs/batch-delete
export function batchDeleteDocsApi(ids: string[]) {
  return request.post<unknown, DocBatchDeleteResult>('/api/v1/docs/batch-delete', {
    ids,
  })
}

// 实现：GET /api/v1/docs/{id}/file 下载原文件（blob）
export function downloadDocFileApi(docId: string) {
  return request.get<unknown, BlobDownload>(`/api/v1/docs/${docId}/file`, {
    responseType: 'blob',
    timeout: 120000,
  })
}

// 实现：GET /api/v1/docs/{id}/preview 预览流（pdf/md 原件；office 为 PDF；blob）
export function previewDocFileApi(docId: string) {
  return request.get<unknown, BlobDownload>(`/api/v1/docs/${docId}/preview`, {
    responseType: 'blob',
    // office 首次转换可能较慢
    timeout: 180000,
  })
}
