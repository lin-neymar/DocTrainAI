/**
 * 角色 / 权限接口（均需后端 role:manage）。
 * 业务分支只认 permission code，不认 role.code / 角色中文名。
 */
import { request } from '@/utils/request'

import type { PageResult } from './types'

export interface RoleItem {
  id: string
  code: string
  name: string
  permission_codes: string[]
  created_at?: string
  updated_at?: string
}

export interface PermissionItem {
  id: string
  code: string
  name: string
}

export interface RoleCreateBody {
  code: string
  name: string
}

export interface RoleUpdateBody {
  code?: string
  name?: string
}

// 实现：GET /api/v1/permissions（从 DB 读，不写死清单）
export function fetchPermissionsApi() {
  return request.get<unknown, PermissionItem[]>('/api/v1/permissions')
}

// 实现：GET /api/v1/roles 分页列表
export function fetchRolesApi(page = 1, pageSize = 20) {
  return request.get<unknown, PageResult<RoleItem>>('/api/v1/roles', {
    params: { page, page_size: pageSize },
  })
}

// 实现：POST /api/v1/roles
export function createRoleApi(body: RoleCreateBody) {
  return request.post<unknown, RoleItem>('/api/v1/roles', body)
}

// 实现：PUT /api/v1/roles/{id}
export function updateRoleApi(roleId: string, body: RoleUpdateBody) {
  return request.put<unknown, RoleItem>(`/api/v1/roles/${roleId}`, body)
}

// 实现：PUT /api/v1/roles/{id}/permissions（整体替换）
export function replaceRolePermissionsApi(roleId: string, permissionCodes: string[]) {
  return request.put<unknown, RoleItem>(`/api/v1/roles/${roleId}/permissions`, {
    permission_codes: permissionCodes,
  })
}

// 实现：DELETE /api/v1/roles/{id}（软删除；仍有用户绑定时 409）
export function deleteRoleApi(roleId: string) {
  return request.delete<unknown, unknown>(`/api/v1/roles/${roleId}`)
}
