<script setup lang="ts">
/**
 * 系统设置：T1 个人主题（任意登录用户）+ T2/T3/T4 全局品牌（system:read 可见，system:update 可改）。
 * 路由：已登录即可。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
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
import { useUserStore } from '@/stores/user'
import { hasPermission } from '@/utils/permission'
import { DEFAULT_THEME_PRIMARY } from '@/utils/theme'

const userStore = useUserStore()
const canReadBrand = computed(() => hasPermission('system:read'))
const canUpdateBrand = computed(() => hasPermission('system:update'))

const loading = ref(false)
const saving = ref(false)
const logoUploading = ref(false)
const themeSaving = ref(false)
const hasLogo = ref(false)
const logoBust = ref(0)
const formRef = ref<FormInstance>()
const form = reactive({
  site_name: '',
  login_subtitle: '',
})
const themeDraft = ref(userStore.themePrimary || DEFAULT_THEME_PRIMARY)

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

watch(
  () => userStore.themePrimary,
  (v) => {
    themeDraft.value = v || DEFAULT_THEME_PRIMARY
  },
)

// 实现：加载品牌设置（无 system:read 则跳过）
async function loadBrand() {
  if (!canReadBrand.value) return
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

// 实现：保存个人主题色
async function onThemeChange(ev: Event) {
  const input = ev.target as HTMLInputElement
  const color = input.value
  themeDraft.value = color
  themeSaving.value = true
  try {
    await userStore.setThemePrimary(color)
    ElMessage.success('主题色已更新')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '主题更新失败')
  } finally {
    themeSaving.value = false
  }
}

// 实现：恢复默认主题色
async function onResetTheme() {
  themeSaving.value = true
  try {
    await userStore.setThemePrimary(null)
    themeDraft.value = DEFAULT_THEME_PRIMARY
    ElMessage.success('已恢复默认主题色')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '主题更新失败')
  } finally {
    themeSaving.value = false
  }
}

// 实现：保存 T2/T3
async function onSave() {
  if (!canUpdateBrand.value) return
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
  if (!canUpdateBrand.value) return
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
  themeDraft.value = userStore.themePrimary || DEFAULT_THEME_PRIMARY
  void loadBrand()
})
</script>

<template>
  <div class="settings-page">
    <section class="panel">
      <h2 class="panel-title">个人外观</h2>
      <p class="hint">主题主色仅影响当前账号的管理台配色，任意登录用户可改。</p>
      <div class="theme-row">
        <label class="theme-picker">
          <span>主题色</span>
          <input
            type="color"
            :value="themeDraft"
            :disabled="themeSaving"
            @change="onThemeChange"
          />
          <code class="theme-hex">{{ themeDraft }}</code>
        </label>
        <ElButton :disabled="themeSaving" @click="onResetTheme">恢复默认</ElButton>
      </div>
    </section>

    <section v-loading="loading" class="panel">
      <h2 class="panel-title">全局品牌</h2>
      <template v-if="canReadBrand">
        <p class="hint">显示名、登录副文案与 Logo 对全员生效；需 system:update 才能修改。</p>
        <ElForm
          ref="formRef"
          class="brand-form"
          :model="form"
          :rules="rules"
          label-position="top"
          :disabled="!canUpdateBrand"
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
                v-if="canUpdateBrand"
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
            v-if="canUpdateBrand"
            type="primary"
            :loading="saving"
            @click="onSave"
          >
            保存文案
          </ElButton>
          <p v-else class="field-tip">当前账号无 system:update，无法修改品牌</p>
        </ElForm>
      </template>
      <p v-else class="hint">当前账号无 system:read，不展示全局品牌配置。</p>
    </section>
  </div>
</template>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-height: 0;
  overflow: auto;
}

.panel {
  background: var(--dt-bg-card);
  border: 1px solid var(--dt-border);
  border-radius: 8px;
  padding: 20px 24px;
}

.panel-title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--dt-text);
}

.hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--dt-text-secondary);
  line-height: 1.5;
}

.theme-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
}

.theme-picker {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--dt-text);
  cursor: pointer;
}

.theme-picker input {
  width: 40px;
  height: 40px;
  padding: 0;
  border: 1px solid var(--dt-border);
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
}

.theme-hex {
  font-size: 13px;
  color: var(--dt-text-secondary);
}

.brand-form {
  max-width: 640px;
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
