/** 系统品牌 T2/T3/T4 + 公开品牌接口 */
import { request } from '@/utils/request'

export interface BrandInfo {
  site_name: string
  login_subtitle: string
  has_logo: boolean
}

// 实现：公开品牌（登录页，可不带 token）
export function fetchPublicBrandApi() {
  return request.get<unknown, BrandInfo>('/api/v1/system/brand')
}

export function fetchSettingsApi() {
  return request.get<unknown, BrandInfo>('/api/v1/system/settings')
}

export function updateSettingsApi(body: {
  site_name: string
  login_subtitle: string
}) {
  return request.put<unknown, BrandInfo>('/api/v1/system/settings', body)
}

export function uploadLogoApi(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request.post<unknown, BrandInfo>('/api/v1/system/settings/logo', form)
}

/** Logo 直链（公开） */
export function brandLogoUrl() {
  const base = import.meta.env.VITE_API_BASE_URL || ''
  return `${base}/api/v1/system/brand/logo`
}
