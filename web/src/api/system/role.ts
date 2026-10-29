/**
 * 角色接口封装（W4 表单拉角色列表；完整 CRUD 在 W5）。
 * 列表需后端 role:manage——无此码时不要调用，避免 403 弹窗。
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

// 实现：GET /api/v1/roles 分页列表
export function fetchRolesApi(page = 1, pageSize = 100) {
  return request.get<unknown, PageResult<RoleItem>>('/api/v1/roles', {
    params: { page, page_size: pageSize },
  })
}
