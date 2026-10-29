/**
 * 权限码判断入口（W0 占位；W1 接上 user store 后实现）。
 * 规约：只认 permission code，禁止按角色名 / role.code 分支。
 */
export function hasPermission(permCode: string): boolean {
  void permCode
  // W1：改为读取 user store 的 permission_codes
  return false
}
