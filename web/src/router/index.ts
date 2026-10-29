import { createRouter, createWebHistory } from 'vue-router'

import { useUserStore } from '@/stores/user'
import { hasPermission } from '@/utils/permission'
import { getToken } from '@/utils/token'

import { systemRoutes } from './routes/system'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    ...systemRoutes,
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

// 实现：路由守卫——恢复会话、拦截未登录与缺权限码
router.beforeEach(async (to) => {
  const isPublic = Boolean(to.meta.public)
  const token = getToken()
  const userStore = useUserStore()

  if (!isPublic) {
    if (!token) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
    if (!userStore.ready) {
      const ok = await userStore.restoreSession()
      if (!ok) {
        return { path: '/login', query: { redirect: to.fullPath } }
      }
    }
    const perm = to.meta.permission
    if (typeof perm === 'string' && perm && !hasPermission(perm)) {
      // 已登录但无码：回首页（W2 侧栏会隐藏入口；直链时不暴露业务页）
      return { path: '/' }
    }
  } else if (to.path === '/login' && token) {
    if (!userStore.ready) {
      await userStore.restoreSession()
    }
    if (userStore.ready) {
      return { path: '/' }
    }
  }

  return true
})

export default router
