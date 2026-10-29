/** 与后端统一分页结构对齐：page 从 1 起 */
export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
