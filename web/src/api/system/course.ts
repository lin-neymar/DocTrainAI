/**
 * 课程接口：读 course:read；写 create/update/delete；挂文档 course:attach_doc。
 * 挂接不放大文档权限：doc 须落在操作者可见集合（后端校验）。
 */
import { request } from '@/utils/request'

import type { PageResult } from './types'

export interface CourseItem {
  id: string
  title: string
  description: string | null
  dept_id: string
  doc_ids: string[]
  created_at?: string
  updated_at?: string
}

export interface CourseCreateBody {
  title: string
  description?: string | null
  dept_id: string
}

export interface CourseUpdateBody {
  title?: string
  description?: string | null
  dept_id?: string
}

// 实现：GET /api/v1/courses 分页列表
export function fetchCoursesApi(page: number, pageSize: number) {
  return request.get<unknown, PageResult<CourseItem>>('/api/v1/courses', {
    params: { page, page_size: pageSize },
  })
}

// 实现：POST /api/v1/courses
export function createCourseApi(body: CourseCreateBody) {
  return request.post<unknown, CourseItem>('/api/v1/courses', body)
}

// 实现：PUT /api/v1/courses/{id}
export function updateCourseApi(courseId: string, body: CourseUpdateBody) {
  return request.put<unknown, CourseItem>(`/api/v1/courses/${courseId}`, body)
}

// 实现：PUT /api/v1/courses/{id}/docs 整体替换挂接文档
export function replaceCourseDocsApi(courseId: string, docIds: string[]) {
  return request.put<unknown, CourseItem>(`/api/v1/courses/${courseId}/docs`, {
    doc_ids: docIds,
  })
}

// 实现：DELETE /api/v1/courses/{id}（软删课程，不删文档）
export function deleteCourseApi(courseId: string) {
  return request.delete<unknown, unknown>(`/api/v1/courses/${courseId}`)
}
