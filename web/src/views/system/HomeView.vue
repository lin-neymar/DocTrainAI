<script setup lang="ts">
/**
 * 工作台：已登录即可进入（无 meta.permission）。
 * 退出已挪到 AdminLayout 顶栏。
 */
import { ElCard, ElTag } from 'element-plus'

import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
</script>

<template>
  <ElCard class="panel" shadow="never">
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
</template>

<style scoped>
.panel {
  border-radius: 8px;
  border: 1px solid var(--dt-border);
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
