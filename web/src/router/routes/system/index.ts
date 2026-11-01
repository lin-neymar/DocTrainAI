import type { RouteRecordRaw } from 'vue-router'

/**
 * 阶段 1 系统路由。
 * meta.public：无需登录；meta.permission：侧栏与守卫共用（只认权限码）。
 * 无 permission：仅要求已登录（工作台）。
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
    name: 'admin-layout',
    component: () => import('@/components/system/AdminLayout.vue'),
    children: [
      {
        path: '',
        name: 'home',
        component: () => import('@/views/system/HomeView.vue'),
        meta: { title: '工作台' },
      },
      {
        path: 'depts',
        name: 'depts',
        component: () => import('@/views/system/DeptView.vue'),
        meta: { title: '部门管理', permission: 'dept:read' },
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/views/system/UserView.vue'),
        meta: { title: '用户管理', permission: 'user:read' },
      },
      {
        path: 'roles',
        name: 'roles',
        component: () => import('@/views/system/RoleView.vue'),
        // 角色维护与配权入口；仅超管种子含此码
        meta: { title: '角色管理', permission: 'role:assign_perm' },
      },
      {
        path: 'docs',
        name: 'docs',
        component: () => import('@/views/system/DocView.vue'),
        meta: { title: '文档管理', permission: 'doc:read' },
      },
      {
        path: 'courses',
        name: 'courses',
        component: () => import('@/views/system/CourseView.vue'),
        meta: { title: '课程管理', permission: 'course:read' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/views/system/SettingsView.vue'),
        // 已登录即可：个人主题 T1；品牌区块仍按 system:read / system:update 显隐
        meta: { title: '系统设置' },
      },
    ],
  },
]
