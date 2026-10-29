<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElButton, ElCard, ElTag } from 'element-plus'

import { fetchHealth } from '@/api/system/health'

const loading = ref(false)
const ok = ref<boolean | null>(null)
const detail = ref('')

// 实现：调用后端健康检查，验证代理 / CORS / 统一响应解包
async function checkHealth() {
  loading.value = true
  ok.value = null
  detail.value = ''
  try {
    const data = await fetchHealth()
    ok.value = true
    detail.value = JSON.stringify(data)
  } catch (err) {
    ok.value = false
    detail.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void checkHealth()
})
</script>

<template>
  <div class="page">
    <ElCard class="card">
      <template #header>
        <div class="header">
          <strong>DocTrainAI</strong>
          <span>W0 脚手架探活</span>
        </div>
      </template>

      <p class="hint">确认 Vite 已启动，并能请求后端 <code>/api/v1/health</code>。</p>

      <div class="row">
        <span>后端连通：</span>
        <ElTag v-if="ok === true" type="success">成功</ElTag>
        <ElTag v-else-if="ok === false" type="danger">失败</ElTag>
        <ElTag v-else type="info">检查中</ElTag>
      </div>

      <pre v-if="detail" class="detail">{{ detail }}</pre>

      <ElButton type="primary" :loading="loading" @click="checkHealth">重新检查</ElButton>
    </ElCard>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: linear-gradient(160deg, #f3f6fb 0%, #e8eef7 50%, #f7f4ef 100%);
}

.card {
  width: min(520px, 100%);
}

.header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
}

.hint {
  margin: 0 0 16px;
  color: #606266;
  line-height: 1.6;
}

.row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.detail {
  margin: 0 0 16px;
  padding: 12px;
  border-radius: 8px;
  background: #f5f7fa;
  font-size: 13px;
  overflow: auto;
}
</style>
