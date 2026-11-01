<script setup lang="ts">
/**
 * 管理台壳：浅色白底侧栏 + 顶栏；主区固定视口，内容页内部滚动。
 * 侧栏菜单来自静态子路由；显隐只用 hasPermission。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import {
  ElAside,
  ElButton,
  ElContainer,
  ElHeader,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElMessageBox,
} from 'element-plus'

import {
  brandLogoUrl,
  fetchPublicBrandApi,
} from '@/api/system/settings'
import { useUserStore } from '@/stores/user'
import { hasPermission } from '@/utils/permission'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const brandName = ref('DocTrainAI')
const brandHasLogo = ref(false)
const logoBust = ref(0)

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

const logoSrc = computed(() =>
  brandHasLogo.value ? `${brandLogoUrl()}?t=${logoBust.value}` : '',
)

// 实现：拉取公开品牌用于侧栏展示名/Logo
async function loadBrand() {
  try {
    const data = await fetchPublicBrandApi()
    brandName.value = data.site_name || 'DocTrainAI'
    brandHasLogo.value = data.has_logo
    logoBust.value = Date.now()
  } catch {
    // 品牌失败不阻断管理台
  }
}

// 实现：确认后退出并跳转登录
async function onLogout() {
  try {
    await ElMessageBox.confirm('确定退出当前账号？', '退出登录', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await userStore.logout()
  await router.replace('/login')
}

onMounted(() => {
  void loadBrand()
})
</script>

<template>
  <ElContainer class="admin-layout">
    <ElAside width="220px" class="aside">
      <div class="brand">
        <img v-if="logoSrc" class="brand-logo" :src="logoSrc" alt="" />
        <span>{{ brandName }}</span>
      </div>
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
  height: 100vh;
  overflow: hidden;
  background: var(--dt-bg-page);
}

.aside {
  height: 100%;
  background: var(--dt-bg-card);
  border-right: 1px solid var(--dt-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.brand {
  height: 56px;
  flex-shrink: 0;
  padding: 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 16px;
  color: var(--dt-color-primary);
  border-bottom: 1px solid var(--dt-border);
  box-sizing: border-box;
  overflow: hidden;
}

.brand-logo {
  width: 28px;
  height: 28px;
  object-fit: contain;
  flex-shrink: 0;
}

.menu {
  flex: 1;
  min-height: 0;
  overflow: auto;
  border-right: none;
  background: transparent;
}

.main-wrap {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  flex-shrink: 0;
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
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: 20px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

/* 子页面根节点撑满主区，由页面内部滚动列表 */
.main :deep(> *) {
  flex: 1;
  min-height: 0;
  min-width: 0;
}
</style>
