<script setup lang="ts">
/**
 * W2 管理台壳：浅色白底侧栏 + 顶栏。
 * 侧栏菜单来自静态子路由；显隐只用 hasPermission（无 permission 的项对已登录可见）。
 */
import { computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import {
  ElAside,
  ElButton,
  ElContainer,
  ElHeader,
  ElMain,
  ElMenu,
  ElMenuItem,
} from 'element-plus'

import { useUserStore } from '@/stores/user'
import { hasPermission } from '@/utils/permission'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 实现：子路由 path 转成侧栏可跳转的绝对路径
function toMenuPath(childPath: string) {
  if (!childPath) return '/'
  return childPath.startsWith('/') ? childPath : `/${childPath}`
}

/** 侧栏项：有 title 的子路由；无 permission 或持有该码才显示 */
const menuItems = computed(() => {
  const layout = router.getRoutes().find((r) => r.name === 'admin-layout')
  const children = layout?.children ?? []
  return children
    .filter((r) => typeof r.meta?.title === 'string' && r.meta.title)
    .filter((r) => {
      const perm = r.meta?.permission
      if (typeof perm !== 'string' || !perm) return true
      return hasPermission(perm)
    })
    .map((r) => ({
      path: toMenuPath(String(r.path)),
      title: String(r.meta!.title),
    }))
})

const activeMenu = computed(() => route.path)

// 实现：顶栏退出并跳转登录
async function onLogout() {
  await userStore.logout()
  await router.replace('/login')
}
</script>

<template>
  <ElContainer class="admin-layout">
    <ElAside width="220px" class="aside">
      <div class="brand">DocTrainAI</div>
      <ElMenu :default-active="activeMenu" router class="menu">
        <ElMenuItem v-for="item in menuItems" :key="item.path" :index="item.path">
          {{ item.title }}
        </ElMenuItem>
      </ElMenu>
    </ElAside>

    <ElContainer class="main-wrap">
      <ElHeader class="header" height="56px">
        <div class="header-left">{{ route.meta.title || '工作台' }}</div>
        <div class="header-right">
          <span class="user-line">
            {{ userStore.username }}
            <span v-if="userStore.deptName" class="dept">· {{ userStore.deptName }}</span>
          </span>
          <ElButton link type="primary" @click="onLogout">退出</ElButton>
        </div>
      </ElHeader>
      <ElMain class="main">
        <RouterView />
      </ElMain>
    </ElContainer>
  </ElContainer>
</template>

<style scoped>
.admin-layout {
  min-height: 100vh;
  background: var(--dt-bg-page);
}

.aside {
  background: var(--dt-bg-card);
  border-right: 1px solid var(--dt-border);
  display: flex;
  flex-direction: column;
}

.brand {
  height: 56px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  font-weight: 700;
  font-size: 16px;
  color: var(--dt-color-primary);
  border-bottom: 1px solid var(--dt-border);
  box-sizing: border-box;
}

.menu {
  border-right: none;
  background: transparent;
}

.main-wrap {
  min-width: 0;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--dt-bg-card);
  border-bottom: 1px solid var(--dt-border);
  padding: 0 20px;
  box-sizing: border-box;
}

.header-left {
  font-size: 15px;
  font-weight: 600;
  color: var(--dt-text);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-line {
  font-size: 13px;
  color: var(--dt-text-secondary);
}

.dept {
  color: var(--dt-text-secondary);
}

.main {
  padding: 20px;
}
</style>
