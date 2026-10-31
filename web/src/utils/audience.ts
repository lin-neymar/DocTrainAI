/**
 * 方案 B 可见组织：前端勾选能力与归属子树裁剪。
 * 与后端一致：有 data:scope:all 或 dept:create 才可自定义；不认角色 code。
 */
import type { DeptTreeNode } from '@/api/system/dept'

import { hasPermission } from '@/utils/permission'

// 实现：是否显示可见组织勾选（公司级发布能力）
export function canCustomizeAudience(): boolean {
  return hasPermission('data:scope:all') || hasPermission('dept:create')
}

// 实现：在部门树中定位节点
export function findDeptNode(
  nodes: DeptTreeNode[],
  deptId: string,
): DeptTreeNode | null {
  for (const n of nodes) {
    if (n.id === deptId) return n
    const found = findDeptNode(n.children, deptId)
    if (found) return found
  }
  return null
}

// 实现：取归属部门子树（作为勾选树根，单根数组）
export function audienceTreeForOwner(
  fullTree: DeptTreeNode[],
  ownerDeptId: string,
): DeptTreeNode[] {
  const node = findDeptNode(fullTree, ownerDeptId)
  return node ? [{ ...node }] : []
}

// 实现：收集子树内全部部门 id
export function collectSubtreeIds(node: DeptTreeNode): string[] {
  const ids = [node.id]
  for (const child of node.children) {
    ids.push(...collectSubtreeIds(child))
  }
  return ids
}
