/**
 * 将后端 timestamptz / ISO 字符串格式化为列表展示用文案。
 * 例：2026-10-31T09:20:19.873188+00:00 → 2026-10-31 09:20:19
 */

// 实现：统一时间展示格式 YYYY-MM-DD HH:mm:ss
export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const matched = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/.exec(value.trim())
  if (matched) {
    return `${matched[1]} ${matched[2]}`
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
}
