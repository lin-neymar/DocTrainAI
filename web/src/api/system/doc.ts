/**
 * 文档接口：列表/下载 doc:read；上传 doc:create；改元数据 doc:update；软删 doc:delete。
 * 可见性由后端 get_visible_doc_ids 裁剪；阶段 1 不展示解析状态。
 */
import { request, type BlobDownload } from '@/utils/request'

import type { PageResult } from './types'

export interface DocItem {
  id: string
  title: string
  dept_id: string
  original_filename: string
  extension: string
  size_bytes: number
  sha256: string
  uploaded_by: string
  created_at?: string
  updated_at?: string
}

export interface DocUpdateBody {
  title?: string
  dept_id?: string
}

// 实现：GET /api/v1/docs 分页列表
export function fetchDocsApi(page: number, pageSize: number) {
  return request.get<unknown, PageResult<DocItem>>('/api/v1/docs', {
    params: { page, page_size: pageSize },
  })
}

// 实现：POST /api/v1/docs multipart 上传
export function uploadDocApi(title: string, deptId: string, file: File) {
  const form = new FormData()
  form.append('title', title)
  form.append('dept_id', deptId)
  form.append('file', file)
  return request.post<unknown, DocItem>('/api/v1/docs', form, {
    timeout: 120000,
  })
}

// 实现：PUT /api/v1/docs/{id} 仅改元数据
export function updateDocApi(docId: string, body: DocUpdateBody) {
  return request.put<unknown, DocItem>(`/api/v1/docs/${docId}`, body)
}

// 实现：DELETE /api/v1/docs/{id} 软删除（不删磁盘）
export function deleteDocApi(docId: string) {
  return request.delete<unknown, unknown>(`/api/v1/docs/${docId}`)
}

// 实现：GET /api/v1/docs/{id}/file 下载原文件（blob）
export function downloadDocFileApi(docId: string) {
  return request.get<unknown, BlobDownload>(`/api/v1/docs/${docId}/file`, {
    responseType: 'blob',
    timeout: 120000,
  })
}
