/** 部门接口：树（只读登录即可）+ 写操作需后端 dept:manage */
import { request } from '@/utils/request'

export interface DeptItem {
  id: string
  name: string
  parent_id: string | null
  created_at?: string
  updated_at?: string
}

export interface DeptTreeNode {
  id: string
  name: string
  parent_id: string | null
  children: DeptTreeNode[]
}

export interface DeptCreateBody {
  name: string
  parent_id: string | null
}

export interface DeptUpdateBody {
  name?: string
  parent_id?: string | null
}

// 实现：GET /api/v1/depts/tree（数据范围由后端裁剪）
export function fetchDeptTreeApi() {
  return request.get<unknown, DeptTreeNode[]>('/api/v1/depts/tree')
}

// 实现：POST /api/v1/depts
export function createDeptApi(body: DeptCreateBody) {
  return request.post<unknown, DeptItem>('/api/v1/depts', body)
}

// 实现：PUT /api/v1/depts/{id}
export function updateDeptApi(deptId: string, body: DeptUpdateBody) {
  return request.put<unknown, DeptItem>(`/api/v1/depts/${deptId}`, body)
}

// 实现：DELETE /api/v1/depts/{id}（软删除）
export function deleteDeptApi(deptId: string) {
  return request.delete<unknown, unknown>(`/api/v1/depts/${deptId}`)
}
