import type { RouteRecordRaw } from 'vue-router'

/**
 * 阶段 1 系统路由。
 * meta.public：无需登录；meta.permission：业务页权限码（W2+ 菜单页使用）。
 * 已登录但无 permission 的壳页面（如首页）仅要求登录。
 */
export const systemRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/system/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/system/HomeView.vue'),
    meta: { title: '工作台' },
  },
]
