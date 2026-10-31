/**
 * T1 个人主题：把主色写到 CSS 变量（含 Element Plus）。
 * localStorage 仅缓存色值，便于首屏；真相仍以 /me 为准。
 */

export const DEFAULT_THEME_PRIMARY = '#1F4B7A'
const STORAGE_KEY = 'dt_theme_primary'

// 实现：根据主色推算 hover / soft（简化，足够管理台使用）
function deriveHover(hex: string): string {
  const n = hex.replace('#', '')
  if (n.length !== 6) return DEFAULT_THEME_PRIMARY
  const r = Math.max(0, parseInt(n.slice(0, 2), 16) - 24)
  const g = Math.max(0, parseInt(n.slice(2, 4), 16) - 24)
  const b = Math.max(0, parseInt(n.slice(4, 6), 16) - 24)
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

function deriveSoft(hex: string): string {
  const n = hex.replace('#', '')
  if (n.length !== 6) return '#e8eef5'
  const r = Math.round((parseInt(n.slice(0, 2), 16) + 230 * 2) / 3)
  const g = Math.round((parseInt(n.slice(2, 4), 16) + 238 * 2) / 3)
  const b = Math.round((parseInt(n.slice(4, 6), 16) + 245 * 2) / 3)
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

// 实现：规范化 #RRGGBB；非法则返回默认色
export function normalizeThemePrimary(input: string | null | undefined): string {
  if (!input) return DEFAULT_THEME_PRIMARY
  const v = input.trim()
  if (/^#[0-9A-Fa-f]{6}$/.test(v)) return v.toUpperCase()
  return DEFAULT_THEME_PRIMARY
}

// 实现：应用到 document 根节点 CSS 变量
export function applyThemePrimary(input: string | null | undefined) {
  const primary = normalizeThemePrimary(input)
  const root = document.documentElement
  root.style.setProperty('--dt-color-primary', primary)
  root.style.setProperty('--dt-color-primary-hover', deriveHover(primary))
  root.style.setProperty('--dt-color-primary-soft', deriveSoft(primary))
  root.style.setProperty('--el-color-primary', primary)
  root.style.setProperty('--el-color-primary-dark-2', deriveHover(primary))
  root.style.setProperty('--el-color-primary-light-9', deriveSoft(primary))
}

export function readStoredThemePrimary(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function writeStoredThemePrimary(value: string | null) {
  try {
    if (!value) localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, normalizeThemePrimary(value))
  } catch {
    // ignore
  }
}
