<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElButton, ElCard, ElForm, ElFormItem, ElInput, ElMessage } from 'element-plus'

import { brandLogoUrl, fetchPublicBrandApi } from '@/api/system/settings'
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

const siteName = ref('DocTrainAI')
const subtitle = ref('企业内部规章培训与知识助手')
const hasLogo = ref(false)
const logoBust = ref(0)

const logoSrc = () => (hasLogo.value ? `${brandLogoUrl()}?t=${logoBust.value}` : '')

const rules: FormRules<typeof form> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

// 实现：拉取公开品牌（T2/T3/T4）
async function loadBrand() {
  try {
    const data = await fetchPublicBrandApi()
    siteName.value = data.site_name || siteName.value
    subtitle.value = data.login_subtitle || subtitle.value
    hasLogo.value = data.has_logo
    logoBust.value = Date.now()
  } catch {
    // 公开接口失败时保留默认文案
  }
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

onMounted(() => {
  void loadBrand()
})
</script>

<template>
  <div class="login-page">
    <ElCard class="login-card" shadow="hover">
      <div class="brand">
        <img v-if="logoSrc()" class="brand-logo" :src="logoSrc()" alt="" />
        <div v-else class="brand-mark" aria-hidden="true" />
        <h1>{{ siteName }}</h1>
        <p>{{ subtitle }}</p>
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
      <div class="version">v1.1</div>
    </ElCard>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  box-sizing: border-box;
  background:
    radial-gradient(circle at top left, var(--dt-color-primary-soft), transparent 42%),
    var(--dt-bg-page);
}

.login-card {
  width: 100%;
  max-width: 400px;
  border-radius: 12px;
}

.brand {
  text-align: center;
  margin-bottom: 24px;
}

.brand-mark {
  width: 48px;
  height: 48px;
  margin: 0 auto 12px;
  border-radius: 12px;
  background: linear-gradient(145deg, var(--dt-color-primary), var(--dt-color-primary-hover));
}

.brand-logo {
  width: 56px;
  height: 56px;
  margin: 0 auto 12px;
  object-fit: contain;
  display: block;
}

.brand h1 {
  margin: 0 0 8px;
  font-size: 24px;
  color: var(--dt-color-primary);
}

.brand p {
  margin: 0;
  font-size: 13px;
  color: var(--dt-text-secondary);
}

.submit {
  width: 100%;
  margin-top: 8px;
}

.version {
  margin-top: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--dt-text-secondary);
}
</style>
