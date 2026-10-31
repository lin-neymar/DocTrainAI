<script setup lang="ts">
/**
 * 系统设置：T2 显示名、T3 登录副文案、T4 Logo。
 * 路由 system:read；保存与上传需 system:update。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules, UploadFile, UploadRawFile } from 'element-plus'
import {
  ElButton,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElUpload,
} from 'element-plus'

import {
  brandLogoUrl,
  fetchSettingsApi,
  updateSettingsApi,
  uploadLogoApi,
} from '@/api/system/settings'
import { hasPermission } from '@/utils/permission'

const canUpdate = computed(() => hasPermission('system:update'))

const loading = ref(false)
const saving = ref(false)
const logoUploading = ref(false)
const hasLogo = ref(false)
const logoBust = ref(0)
const formRef = ref<FormInstance>()
const form = reactive({
  site_name: '',
  login_subtitle: '',
})

const rules: FormRules<typeof form> = {
  site_name: [
    { required: true, message: '请输入系统显示名', trigger: 'blur' },
    { max: 128, message: '最多 128 字', trigger: 'blur' },
  ],
  login_subtitle: [
    { required: true, message: '请输入登录页副文案', trigger: 'blur' },
    { max: 256, message: '最多 256 字', trigger: 'blur' },
  ],
}

const logoSrc = computed(() =>
  hasLogo.value ? `${brandLogoUrl()}?t=${logoBust.value}` : '',
)

// 实现：加载品牌设置
async function load() {
  loading.value = true
  try {
    const data = await fetchSettingsApi()
    form.site_name = data.site_name
    form.login_subtitle = data.login_subtitle
    hasLogo.value = data.has_logo
  } finally {
    loading.value = false
  }
}

// 实现：保存 T2/T3
async function onSave() {
  if (!canUpdate.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const data = await updateSettingsApi({
      site_name: form.site_name.trim(),
      login_subtitle: form.login_subtitle.trim(),
    })
    form.site_name = data.site_name
    form.login_subtitle = data.login_subtitle
    ElMessage.success('已保存')
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

// 实现：本地选图后立刻上传 Logo
async function onLogoChange(uploadFile: UploadFile) {
  if (!canUpdate.value) return
  const raw = uploadFile.raw as UploadRawFile | undefined
  if (!raw) return
  const name = raw.name.toLowerCase()
  if (!/\.(png|jpe?g|webp)$/.test(name)) {
    ElMessage.warning('仅支持 png、jpg、webp')
    return
  }
  logoUploading.value = true
  try {
    const data = await uploadLogoApi(raw)
    hasLogo.value = data.has_logo
    logoBust.value = Date.now()
    ElMessage.success('Logo 已更新')
  } catch {
    // 拦截器已提示
  } finally {
    logoUploading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div v-loading="loading" class="settings-page">
    <p class="hint">
      此处仅维护全局品牌（显示名、登录副文案、Logo）。个人主题色请在顶栏修改。
    </p>

    <ElForm
      ref="formRef"
      class="form"
      :model="form"
      :rules="rules"
      label-position="top"
      :disabled="!canUpdate"
    >
      <ElFormItem label="系统显示名" prop="site_name">
        <ElInput v-model="form.site_name" maxlength="128" />
      </ElFormItem>
      <ElFormItem label="登录页副文案" prop="login_subtitle">
        <ElInput v-model="form.login_subtitle" maxlength="256" />
      </ElFormItem>
      <ElFormItem label="Logo">
        <div class="logo-row">
          <img v-if="logoSrc" class="logo-preview" :src="logoSrc" alt="Logo" />
          <span v-else class="muted">尚未上传</span>
          <ElUpload
            v-if="canUpdate"
            :auto-upload="false"
            :show-file-list="false"
            accept=".png,.jpg,.jpeg,.webp"
            :disabled="logoUploading"
            @change="onLogoChange"
          >
            <ElButton :loading="logoUploading">上传 Logo</ElButton>
          </ElUpload>
        </div>
      </ElFormItem>
      <ElButton
        v-if="canUpdate"
        type="primary"
        :loading="saving"
        @click="onSave"
      >
        保存文案
      </ElButton>
      <p v-else class="field-tip">当前账号无 system:update，无法修改品牌</p>
    </ElForm>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 520px;
}

.hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--dt-text-secondary);
}

.form {
  background: var(--dt-bg-card);
  border: 1px solid var(--dt-border);
  border-radius: 8px;
  padding: 20px;
}

.logo-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.logo-preview {
  width: 48px;
  height: 48px;
  object-fit: contain;
  border: 1px solid var(--dt-border);
  border-radius: 6px;
  background: #fff;
}

.muted {
  color: var(--dt-text-secondary);
  font-size: 13px;
}

.field-tip {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--dt-text-secondary);
}
</style>
