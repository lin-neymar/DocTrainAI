import type { RouteRecordRaw } from 'vue-router'

/**
 * 阶段 3 对话路由（挂在管理台壳 admin-layout 下的子路由）。
 * meta.permission: 'agent:chat'——守卫与侧栏菜单共用，只认权限码。
 */
export const aiExtChildRoutes: RouteRecordRaw[] = [
  {
    path: 'chat',
    name: 'chat',
    component: () => import('@/views/ai_ext/ChatView.vue'),
    meta: { title: '智能对话', permission: 'agent:chat' },
  },
]
