/**
 * 将后端 timestamptz / ISO 字符串格式化为列表展示用文案（浏览器本地时区）。
 * 例：2026-11-16T09:20:19.873188+00:00 → 2026-11-16 17:20:19（UTC+8）
 */

export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value.trim())
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
}

/** 对话消息时间：2026.09.10 11:22（本地时区，无秒） */
export function formatChatMessageTime(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value.trim())
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}.${pad(date.getMonth() + 1)}.${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}
