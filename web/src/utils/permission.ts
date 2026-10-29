/**
 * 功能显隐唯一入口：只查 user store 里的 permission_codes。
 * 禁止按角色名 / role.code 判断。
 */
import { useUserStore } from '@/stores/user'

// 实现：当前用户是否持有指定权限码
export function hasPermission(permCode: string): boolean {
  return useUserStore().hasPermission(permCode)
}
