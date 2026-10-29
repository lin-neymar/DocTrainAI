/// <reference types="vite/client" />

import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** 无需登录（登录页等） */
    public?: boolean
    /** 业务页所需权限码；无此字段则仅要求已登录 */
    permission?: string
    title?: string
  }
}

interface ImportMetaEnv {
  /** 后端 API 根；留空则走 Vite 代理相对路径 /api */
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
