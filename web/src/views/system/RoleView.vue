<script setup lang="ts">
/**
 * W5 角色管理：分页列表 + 创建/编辑 + 整体替换权限码 + 软删。
 * 路由需 role:manage；权限清单来自 GET /permissions（DB），禁止写死 seed 常量。
 * 鉴权展示与勾选只认 permission code，不按角色名/code 写业务分支。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  ElButton,
  ElCheckbox,
  ElCheckboxGroup,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElPagination,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'

import {
  createRoleApi,
  deleteRoleApi,
  fetchPermissionsApi,
  fetchRolesApi,
  replaceRolePermissionsApi,
  updateRoleApi,
  type PermissionItem,
  type RoleItem,
} from '@/api/system/role'

const loading = ref(false)
const roles = ref<RoleItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const allPermissions = ref<PermissionItem[]>([])

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const dialogLoading = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  code: '',
  name: '',
  permission_codes: [] as string[],
})

const formRules: FormRules<typeof form> = {
  code: [
    { required: true, message: '请输入角色 code', trigger: 'blur' },
    { min: 1, max: 64, message: '长度 1–64', trigger: 'blur' },
  ],
  name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' },
    { min: 1, max: 128, message: '长度 1–128', trigger: 'blur' },
  ],
}

const dialogTitle = computed(() =>
  dialogMode.value === 'create' ? '新增角色' : '编辑角色',
)

// 实现：分页拉取角色列表
async function loadRoles() {
  loading.value = true
  try {
    const data = await fetchRolesApi(page.value, pageSize.value)
    roles.value = data.items
    total.value = data.total
    page.value = data.page
    pageSize.value = data.page_size
  } finally {
    loading.value = false
  }
}

// 实现：拉取 DB 中全部未删权限码
async function loadPermissions() {
  allPermissions.value = await fetchPermissionsApi()
}

function asRole(row: unknown): RoleItem {
  return row as RoleItem
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  form.code = ''
  form.name = ''
  form.permission_codes = []
  dialogVisible.value = true
}

function openEdit(row: unknown) {
  const r = asRole(row)
  dialogMode.value = 'edit'
  editingId.value = r.id
  form.code = r.code
  form.name = r.name
  form.permission_codes = [...r.permission_codes]
  dialogVisible.value = true
}

// 实现：创建或更新角色元数据，并整体替换权限码
async function onSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  dialogLoading.value = true
  try {
    const code = form.code.trim()
    const name = form.name.trim()
    let roleId = editingId.value

    if (dialogMode.value === 'create') {
      const created = await createRoleApi({ code, name })
      roleId = created.id
      ElMessage.success('创建成功')
    } else if (roleId) {
      await updateRoleApi(roleId, { code, name })
      ElMessage.success('更新成功')
    }

    if (roleId) {
      await replaceRolePermissionsApi(roleId, form.permission_codes)
    }

    dialogVisible.value = false
    await loadRoles()
  } catch {
    // 错误已由拦截器提示
  } finally {
    dialogLoading.value = false
  }
}

// 实现：软删除角色（仍有用户绑定时后端 409）
async function onDelete(row: unknown) {
  const r = asRole(row)
  try {
    await ElMessageBox.confirm(
      `确定删除角色「${r.name}」（${r.code}）？仍有用户绑定时将被拒绝。`,
      '删除角色',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteRoleApi(r.id)
    ElMessage.success('已删除')
    if (roles.value.length <= 1 && page.value > 1) {
      page.value -= 1
    }
    await loadRoles()
  } catch {
    // 拦截器已提示
  }
}

function permPreview(row: unknown) {
  return asRole(row).permission_codes
}

async function onPageChange(p: number) {
  page.value = p
  await loadRoles()
}

async function onSizeChange(size: number) {
  pageSize.value = size
  page.value = 1
  await loadRoles()
}

onMounted(async () => {
  loading.value = true
  try {
    await loadPermissions()
    await loadRoles()
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="role-page">
    <div class="toolbar">
      <span class="hint">权限码来自数据库；业务只认 code，不认角色名称</span>
      <div class="toolbar-right">
        <ElButton :loading="loading" @click="loadRoles">刷新</ElButton>
        <ElButton type="primary" @click="openCreate">新增角色</ElButton>
      </div>
    </div>

    <div class="table-panel">
      <ElTable v-loading="loading" :data="roles" stripe empty-text="暂无角色">
        <ElTableColumn prop="code" label="code" min-width="140" />
        <ElTableColumn prop="name" label="名称" min-width="120" />
        <ElTableColumn label="权限码" min-width="280">
          <template #default="{ row }">
            <template v-if="permPreview(row).length">
              <ElTag
                v-for="code in permPreview(row)"
                :key="code"
                class="perm-tag"
                size="small"
                type="info"
                effect="plain"
              >
                {{ code }}
              </ElTag>
            </template>
            <span v-else class="muted">未配置</span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="updated_at" label="更新时间" min-width="170" />
        <ElTableColumn label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openEdit(row)">编辑</ElButton>
            <ElButton link type="danger" @click="onDelete(row)">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>

      <div class="pager">
        <ElPagination
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :current-page="page"
          :page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </div>

    <ElDialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="560px"
      destroy-on-close
      @closed="formRef?.resetFields()"
    >
      <ElForm ref="formRef" :model="form" :rules="formRules" label-position="top">
        <ElFormItem label="角色 code" prop="code">
          <ElInput
            v-model="form.code"
            maxlength="64"
            placeholder="如 dept_admin（唯一标识，非鉴权依据）"
          />
        </ElFormItem>
        <ElFormItem label="显示名称" prop="name">
          <ElInput v-model="form.name" maxlength="128" placeholder="如 部门管理员" />
        </ElFormItem>
        <ElFormItem label="权限码">
          <ElCheckboxGroup v-model="form.permission_codes" class="perm-group">
            <ElCheckbox v-for="p in allPermissions" :key="p.code" :value="p.code">
              <span class="perm-code">{{ p.code }}</span>
              <span class="perm-name">{{ p.name }}</span>
            </ElCheckbox>
          </ElCheckboxGroup>
          <p v-if="!allPermissions.length" class="field-tip">暂无可用权限码</p>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="dialogLoading" @click="onSubmit">确定</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.role-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: var(--dt-bg-card);
  border: 1px solid var(--dt-border);
  border-radius: 8px;
}

.toolbar-right {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hint {
  font-size: 13px;
  color: var(--dt-text-secondary);
}

.table-panel {
  padding: 16px;
  background: var(--dt-bg-card);
  border: 1px solid var(--dt-border);
  border-radius: 8px;
}

.perm-tag {
  margin: 0 6px 4px 0;
}

.muted {
  color: var(--dt-text-secondary);
  font-size: 13px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.perm-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 280px;
  overflow: auto;
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--dt-border);
  border-radius: 6px;
  box-sizing: border-box;
}

.perm-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
}

.perm-name {
  margin-left: 8px;
  color: var(--dt-text-secondary);
  font-size: 12px;
}

.field-tip {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--dt-text-secondary);
}
</style>
