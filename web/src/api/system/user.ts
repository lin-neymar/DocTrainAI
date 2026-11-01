/** 用户接口：读 user:read；写拆 create/update/delete/reset_password */
import { request } from '@/utils/request'

import type { PageResult } from './types'

export interface UserItem {
  id: string
  username: string
  dept_id: string
  role_ids: string[]
  created_at?: string
  updated_at?: string
}

export interface UserCreateBody {
  username: string
  password: string
  dept_id: string
  role_ids: string[]
}

export interface UserUpdateBody {
  username?: string
  dept_id?: string
  role_ids?: string[]
}

export interface UserListQuery {
  page: number
  pageSize: number
  username?: string
}

// 实现：GET /api/v1/users 分页列表（可选用户名模糊筛选）
export function fetchUsersApi(query: UserListQuery) {
  const params: Record<string, string | number> = {
    page: query.page,
    page_size: query.pageSize,
  }
  const username = query.username?.trim()
  if (username) params.username = username
  return request.get<unknown, PageResult<UserItem>>('/api/v1/users', { params })
}

// 实现：POST /api/v1/users
export function createUserApi(body: UserCreateBody) {
  return request.post<unknown, UserItem>('/api/v1/users', body)
}

// 实现：PUT /api/v1/users/{id}
export function updateUserApi(userId: string, body: UserUpdateBody) {
  return request.put<unknown, UserItem>(`/api/v1/users/${userId}`, body)
}

// 实现：PUT /api/v1/users/{id}/password
export function resetUserPasswordApi(userId: string, password: string) {
  return request.put<unknown, unknown>(`/api/v1/users/${userId}/password`, {
    password,
  })
}

// 实现：DELETE /api/v1/users/{id}（软删除）
export function deleteUserApi(userId: string) {
  return request.delete<unknown, unknown>(`/api/v1/users/${userId}`)
}

export interface UserBatchDeleteResult {
  deleted_count: number
  skipped_self: boolean
}

// 实现：POST /api/v1/users/batch-delete
export function batchDeleteUsersApi(ids: string[]) {
  return request.post<unknown, UserBatchDeleteResult>('/api/v1/users/batch-delete', {
    ids,
  })
}
