import type { RouteRecordRaw } from 'vue-router'

/**
 * 阶段 1 系统路由（W2：业务页挂到 AdminLayout 子路由）。
 * meta.public：无需登录；meta.permission：侧栏与守卫共用（只认权限码）。
 * 无 permission：仅要求已登录（工作台、部门树只读入口）。
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
        // 部门树只读对已登录开放；写操作在 W3 页内再要 dept:manage
        meta: { title: '部门管理' },
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/views/system/UserView.vue'),
        meta: { title: '用户管理', permission: 'user:manage' },
      },
      {
        path: 'roles',
        name: 'roles',
        component: () => import('@/views/system/RoleView.vue'),
        meta: { title: '角色管理', permission: 'role:manage' },
      },
      {
        path: 'docs',
        name: 'docs',
        component: () => import('@/views/system/DocView.vue'),
        // 上传/删除按钮留给 W6 再拆 doc:upload / doc:delete
        meta: { title: '文档管理', permission: 'doc:read' },
      },
      {
        path: 'courses',
        name: 'courses',
        component: () => import('@/views/system/CourseView.vue'),
        // 写操作留给 W7 再要 course:manage
        meta: { title: '课程管理', permission: 'course:read' },
      },
    ],
  },
]
