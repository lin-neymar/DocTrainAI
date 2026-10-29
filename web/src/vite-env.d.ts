/// <reference types="vite/client" />

// 让 TS / Volar 识别 `import xxx from '*.vue'`（含 `@/views/...vue`）
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

interface ImportMetaEnv {
  /** 后端 API 根；留空则走 Vite 代理相对路径 /api */
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
