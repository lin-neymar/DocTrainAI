import type { RouteRecordRaw } from 'vue-router'

/** 阶段 1 系统路由；登录守卫与 meta.permission 在 W1/W2 补齐 */
export const systemRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'bootstrap',
    component: () => import('@/views/system/BootstrapView.vue'),
    meta: { title: '脚手架探活' },
  },
]
