<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElButton, ElCard, ElForm, ElFormItem, ElInput, ElMessage } from 'element-plus'

import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules<typeof form> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

// 实现：校验表单后登录，成功跳转 redirect 或首页
async function onSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.login(form.username.trim(), form.password)
    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect || '/')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <ElCard class="login-card" shadow="hover">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true" />
        <h1>DocTrainAI</h1>
        <p>文档培训智能平台</p>
      </div>

      <ElForm
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="onSubmit"
      >
        <ElFormItem label="用户名" prop="username">
          <ElInput v-model="form.username" autocomplete="username" placeholder="请输入用户名" />
        </ElFormItem>
        <ElFormItem label="密码" prop="password">
          <ElInput
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="请输入密码"
            @keyup.enter="onSubmit"
          />
        </ElFormItem>
        <ElButton type="primary" class="submit" :loading="loading" native-type="submit">
          登录
        </ElButton>
      </ElForm>
    </ElCard>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(circle at top left, var(--dt-color-primary-soft), transparent 42%),
    var(--dt-bg-page);
}

.login-card {
  width: min(400px, 100%);
  border: 1px solid var(--dt-border);
  border-radius: 12px;
}

.brand {
  text-align: center;
  margin-bottom: 28px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  margin: 0 auto 12px;
  border-radius: 10px;
  background: linear-gradient(145deg, var(--dt-color-primary), var(--dt-color-primary-hover));
}

.brand h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--dt-color-primary);
}

.brand p {
  margin: 8px 0 0;
  color: var(--dt-text-secondary);
  font-size: 14px;
}

.submit {
  width: 100%;
  margin-top: 8px;
}
</style>
