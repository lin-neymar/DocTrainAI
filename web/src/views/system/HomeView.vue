<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElButton, ElCard, ElTag } from 'element-plus'

import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

// 实现：退出并回到登录页
async function onLogout() {
  await userStore.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="home">
    <ElCard class="panel">
      <template #header>
        <div class="header">
          <div>
            <strong>DocTrainAI</strong>
            <span class="sub">已登录工作台（W1；完整布局见 W2）</span>
          </div>
          <ElButton @click="onLogout">退出登录</ElButton>
        </div>
      </template>

      <p>
        当前用户：<strong>{{ userStore.username }}</strong>
        · 部门：{{ userStore.deptName }}
      </p>
      <p class="label">角色（仅展示，鉴权不看角色名）</p>
      <div class="tags">
        <ElTag v-for="name in userStore.roleNames" :key="name" class="tag">{{ name }}</ElTag>
      </div>
      <p class="label">权限码</p>
      <div class="tags">
        <ElTag
          v-for="code in userStore.permissionCodes"
          :key="code"
          type="info"
          class="tag"
          effect="plain"
        >
          {{ code }}
        </ElTag>
      </div>
    </ElCard>
  </div>
</template>

<style scoped>
.home {
  min-height: 100vh;
  padding: 32px 20px;
  background: var(--dt-bg-page);
}

.panel {
  max-width: 880px;
  margin: 0 auto;
  border-radius: 12px;
}

.header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.sub {
  margin-left: 12px;
  color: var(--dt-text-secondary);
  font-size: 13px;
  font-weight: 400;
}

.label {
  margin: 20px 0 8px;
  color: var(--dt-text-secondary);
  font-size: 13px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  margin: 0;
}
</style>
