/**
 * 当前用户与权限码的唯一存放处（WEB_SPEC）。
 * localStorage 只存 token + 可选个人主题色；刷新后用 /auth/me 恢复。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { fetchMeApi, loginApi, logoutApi, updateMyThemeApi } from '@/api/system/auth'
import { applyThemePrimary, DEFAULT_THEME_PRIMARY, writeStoredThemePrimary } from '@/utils/theme'
import { clearToken, getToken, setToken } from '@/utils/token'

export const useUserStore = defineStore('user', () => {
  const userId = ref<string | null>(null)
  const username = ref<string | null>(null)
  const deptId = ref<string | null>(null)
  const deptName = ref<string | null>(null)
  const roleNames = ref<string[]>([])
  const permissionCodes = ref<string[]>([])
  const themePrimary = ref<string | null>(null)
  /** 是否已用 /me 或登录结果填充过会话（有 token 但未 restore 时为 false） */
  const ready = ref(false)

  const isLoggedIn = computed(() => Boolean(getToken()) && ready.value)

  // 实现：清空内存中的用户态（不负责跳转）
  function resetSession() {
    userId.value = null
    username.value = null
    deptId.value = null
    deptName.value = null
    roleNames.value = []
    permissionCodes.value = []
    themePrimary.value = null
    ready.value = false
    applyThemePrimary(DEFAULT_THEME_PRIMARY)
    writeStoredThemePrimary(null)
  }

  // 实现：用 /me 结果写入 store 并应用主题
  function applyMe(data: Awaited<ReturnType<typeof fetchMeApi>>) {
    userId.value = data.user.id
    username.value = data.user.username
    deptId.value = data.dept.id
    deptName.value = data.dept.name
    roleNames.value = data.role_names
    permissionCodes.value = data.permission_codes
    themePrimary.value = data.theme_primary ?? null
    applyThemePrimary(themePrimary.value)
    writeStoredThemePrimary(themePrimary.value)
    ready.value = true
  }

  // 实现：登录 → 存 token → /me 拉权限码
  async function login(name: string, password: string) {
    const result = await loginApi(name, password)
    setToken(result.access_token)
    const me = await fetchMeApi()
    applyMe(me)
  }

  // 实现：有 token 时调用 /me 恢复；失败则清 token
  async function restoreSession() {
    const token = getToken()
    if (!token) {
      resetSession()
      return false
    }
    try {
      const me = await fetchMeApi()
      applyMe(me)
      return true
    } catch {
      clearToken()
      resetSession()
      return false
    }
  }

  // 实现：调用后端 logout（忽略失败）并丢弃本地会话
  async function logout() {
    try {
      if (getToken()) {
        await logoutApi()
      }
    } catch {
      // 无状态 JWT：即使服务端失败也要清本地
    } finally {
      clearToken()
      resetSession()
    }
  }

  // 实现：更新个人主题色并立刻生效
  async function setThemePrimary(color: string | null) {
    const data = await updateMyThemeApi(color)
    themePrimary.value = data.theme_primary
    applyThemePrimary(themePrimary.value)
    writeStoredThemePrimary(themePrimary.value)
  }

  // 实现：是否持有某权限码（只认 code）
  function hasPermission(permCode: string) {
    return permissionCodes.value.includes(permCode)
  }

  return {
    userId,
    username,
    deptId,
    deptName,
    roleNames,
    permissionCodes,
    themePrimary,
    ready,
    isLoggedIn,
    resetSession,
    login,
    restoreSession,
    logout,
    setThemePrimary,
    hasPermission,
  }
})
