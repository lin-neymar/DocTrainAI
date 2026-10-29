/** W0 探活：确认前端能打到后端 /api/v1/health */
import { request } from '@/utils/request'

export interface HealthData {
  status: 'up' | string
}

// 实现：GET /api/v1/health
export function fetchHealth() {
  return request.get<unknown, HealthData>('/api/v1/health')
}
