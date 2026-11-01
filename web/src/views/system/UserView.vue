<script setup lang="ts">
/**
 * 用户管理：路由 user:read；写按钮拆 create/update/delete/reset_password。
 * 列表支持按用户名模糊搜索；角色勾选依赖 role:read。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPagination,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'

import { fetchDeptTreeApi, type DeptTreeNode } from '@/api/system/dept'
import { fetchRolesApi, type RoleItem } from '@/api/system/role'
import {
  createUserApi,
  deleteUserApi,
  fetchUsersApi,
  resetUserPasswordApi,
  updateUserApi,
  type UserItem,
} from '@/api/system/user'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/datetime'
import { hasPermission } from '@/utils/permission'

const userStore = useUserStore()

const loading = ref(false)
const users = ref<UserItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

/** 搜索表单（点「查询」后写入 appliedUsername，避免输入时误触发） */
const filterUsername = ref('')
const appliedUsername = ref('')

const deptOptions = ref<{ id: string; label: string }[]>([])
const deptNameMap = ref<Record<string, string>>({})
const roles = ref<RoleItem[]>([])
const roleNameMap = computed(() => {
  const map: Record<string, string> = {}
  for (const r of roles.value) map[r.id] = r.name
  return map
})

/** 能否拉角色列表并在表单里改 role_ids（与后端 GET /roles → role:read 一致） */
const canAssignRoles = computed(() => hasPermission('role:read'))
const canCreate = computed(() => hasPermission('user:create'))
const canUpdate = computed(() => hasPermission('user:update'))
const canDelete = computed(() => hasPermission('user:delete'))
const canResetPassword = computed(() => hasPermission('user:reset_password'))

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const dialogLoading = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  username: '',
  password: '',
  dept_id: '',
  role_ids: [] as string[],
})

const pwdDialogVisible = ref(false)
const pwdLoading = ref(false)
const pwdUserId = ref<string | null>(null)
const pwdUserName = ref('')
const pwdFormRef = ref<FormInstance>()
const pwdForm = reactive({ password: '', confirm: '' })

const formRules = computed<FormRules>(() => ({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 1, max: 64, message: '长度 1–64', trigger: 'blur' },
  ],
  password:
    dialogMode.value === 'create'
      ? [
          { required: true, message: '请输入初始密码', trigger: 'blur' },
          { min: 6, max: 128, message: '密码至少 6 位', trigger: 'blur' },
        ]
      : [],
  dept_id: [{ required: true, message: '请选择部门', trigger: 'change' }],
}))

const pwdRules: FormRules<typeof pwdForm> = {
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 128, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_r, v, cb) => {
        if (v !== pwdForm.password) cb(new Error('两次密码不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

const dialogTitle = computed(() =>
  dialogMode.value === 'create' ? '新增用户' : '编辑用户',
)

// 实现：部门树展平为下拉选项（缩进表示层级）
function flattenDepts(nodes: DeptTreeNode[], depth = 0) {
  const opts: { id: string; label: string }[] = []
  const names: Record<string, string> = {}
  const walk = (list: DeptTreeNode[], d: number) => {
    for (const n of list) {
      const prefix = d > 0 ? `${'—'.repeat(d)} ` : ''
      opts.push({ id: n.id, label: `${prefix}${n.name}` })
      names[n.id] = n.name
      walk(n.children, d + 1)
    }
  }
  walk(nodes, depth)
  return { opts, names }
}

// 实现：加载可见部门树（供表单选部门、列表显示名）
async function loadDepts() {
  const tree = await fetchDeptTreeApi()
  const { opts, names } = flattenDepts(tree)
  deptOptions.value = opts
  deptNameMap.value = names
}

// 实现：有 role:read 时拉取角色供多选；否则跳过
async function loadRolesIfAllowed() {
  if (!canAssignRoles.value) {
    roles.value = []
    return
  }
  const data = await fetchRolesApi(1, 100)
  roles.value = data.items
}

// 实现：分页拉取用户列表（带已应用的用户名条件）
async function loadUsers() {
  loading.value = true
  try {
    const data = await fetchUsersApi({
      page: page.value,
      pageSize: pageSize.value,
      username: appliedUsername.value || undefined,
    })
    users.value = data.items
    total.value = data.total
    page.value = data.page
    pageSize.value = data.page_size
  } finally {
    loading.value = false
  }
}

// 实现：按用户名查询并回到第 1 页
async function onSearch() {
  appliedUsername.value = filterUsername.value.trim()
  page.value = 1
  await loadUsers()
}

// 实现：清空用户名搜索
async function onResetFilters() {
  filterUsername.value = ''
  appliedUsername.value = ''
  page.value = 1
  await loadUsers()
}

function roleLabels(roleIds: string[]) {
  if (!roleIds.length) return []
  return roleIds.map((id) => roleNameMap.value[id] || id.slice(0, 8))
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  form.username = ''
  form.password = ''
  form.dept_id = deptOptions.value[0]?.id ?? ''
  form.role_ids = []
  dialogVisible.value = true
}

function asUser(row: unknown): UserItem {
  return row as UserItem
}

function openEdit(row: unknown) {
  const u = asUser(row)
  dialogMode.value = 'edit'
  editingId.value = u.id
  form.username = u.username
  form.password = ''
  form.dept_id = u.dept_id
  form.role_ids = [...u.role_ids]
  dialogVisible.value = true
}

function openResetPwd(row: unknown) {
  const u = asUser(row)
  pwdUserId.value = u.id
  pwdUserName.value = u.username
  pwdForm.password = ''
  pwdForm.confirm = ''
  pwdDialogVisible.value = true
}

// 实现：提交创建或更新（无 role:read 时更新不传 role_ids）
async function onSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  dialogLoading.value = true
  try {
    if (dialogMode.value === 'create') {
      if (!canCreate.value) return
      await createUserApi({
        username: form.username.trim(),
        password: form.password,
        dept_id: form.dept_id,
        role_ids: canAssignRoles.value ? form.role_ids : [],
      })
      ElMessage.success('创建成功')
    } else if (editingId.value) {
      if (!canUpdate.value) return
      const body: {
        username: string
        dept_id: string
        role_ids?: string[]
      } = {
        username: form.username.trim(),
        dept_id: form.dept_id,
      }
      if (canAssignRoles.value) {
        body.role_ids = form.role_ids
      }
      await updateUserApi(editingId.value, body)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    await loadUsers()
  } catch {
    // 错误已由拦截器提示
  } finally {
    dialogLoading.value = false
  }
}

// 实现：管理员重置密码
async function onResetPwd() {
  const valid = await pwdFormRef.value?.validate().catch(() => false)
  if (!valid || !pwdUserId.value || !canResetPassword.value) return

  pwdLoading.value = true
  try {
    await resetUserPasswordApi(pwdUserId.value, pwdForm.password)
    ElMessage.success('密码已重置')
    pwdDialogVisible.value = false
  } catch {
    // 拦截器已提示
  } finally {
    pwdLoading.value = false
  }
}

// 实现：软删除用户（禁止删自己）
async function onDelete(row: unknown) {
  if (!canDelete.value) return
  const u = asUser(row)
  if (u.id === userStore.userId) {
    ElMessage.warning('不能删除当前登录账号')
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除用户「${u.username}」？`, '删除用户', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteUserApi(u.id)
    ElMessage.success('已删除')
    if (users.value.length <= 1 && page.value > 1) {
      page.value -= 1
    }
    await loadUsers()
  } catch {
    // 拦截器已提示
  }
}

function deptLabel(row: unknown) {
  const u = asUser(row)
  return deptNameMap.value[u.dept_id] || u.dept_id.slice(0, 8)
}

function rowRoleLabels(row: unknown) {
  return roleLabels(asUser(row).role_ids)
}

function isSelf(row: unknown) {
  return asUser(row).id === userStore.userId
}

async function onPageChange(p: number) {
  page.value = p
  await loadUsers()
}

async function onSizeChange(size: number) {
  pageSize.value = size
  page.value = 1
  await loadUsers()
}

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([loadDepts(), loadRolesIfAllowed()])
    await loadUsers()
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="user-page">
    <div class="toolbar">
      <div class="filters">
        <ElInput
          v-model="filterUsername"
          clearable
          placeholder="用户名"
          class="filter-username"
          @keyup.enter="onSearch"
        />
        <ElButton type="primary" :loading="loading" @click="onSearch">查询</ElButton>
        <ElButton :disabled="loading" @click="onResetFilters">重置</ElButton>
      </div>
      <div class="toolbar-right">
        <ElButton :loading="loading" @click="loadUsers">刷新</ElButton>
        <ElButton v-if="canCreate" type="primary" @click="openCreate">新增用户</ElButton>
      </div>
    </div>

    <div class="table-panel">
      <div class="table-scroll">
        <ElTable
          v-loading="loading"
          height="100%"
          :data="users"
          stripe
          empty-text="暂无用户"
        >
          <ElTableColumn prop="username" label="用户名" min-width="120" />
          <ElTableColumn label="部门" min-width="140">
            <template #default="{ row }">
              {{ deptLabel(row) }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="角色" min-width="180">
            <template #default="{ row }">
              <template v-if="rowRoleLabels(row).length">
                <ElTag
                  v-for="name in rowRoleLabels(row)"
                  :key="name"
                  class="role-tag"
                  size="small"
                  effect="plain"
                >
                  {{ name }}
                </ElTag>
              </template>
              <span v-else class="muted">未分配</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="创建时间" min-width="170">
            <template #default="{ row }">
              {{ formatDateTime(asUser(row).created_at) }}
            </template>
          </ElTableColumn>
          <ElTableColumn
            v-if="canUpdate || canResetPassword || canDelete"
            label="操作"
            width="240"
            fixed="right"
          >
            <template #default="{ row }">
              <ElButton v-if="canUpdate" link type="primary" @click="openEdit(row)">
                编辑
              </ElButton>
              <ElButton
                v-if="canResetPassword"
                link
                type="primary"
                @click="openResetPwd(row)"
              >
                重置密码
              </ElButton>
              <ElButton
                v-if="canDelete"
                link
                type="danger"
                :disabled="isSelf(row)"
                @click="onDelete(row)"
              >
                删除
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>

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
      width="460px"
      destroy-on-close
      @closed="formRef?.resetFields()"
    >
      <ElForm ref="formRef" :model="form" :rules="formRules" label-position="top">
        <ElFormItem label="用户名" prop="username">
          <ElInput v-model="form.username" maxlength="64" autocomplete="off" />
        </ElFormItem>
        <ElFormItem v-if="dialogMode === 'create'" label="初始密码" prop="password">
          <ElInput
            v-model="form.password"
            type="password"
            show-password
            maxlength="128"
            autocomplete="new-password"
          />
        </ElFormItem>
        <ElFormItem label="所属部门" prop="dept_id">
          <ElSelect v-model="form.dept_id" filterable style="width: 100%">
            <ElOption
              v-for="opt in deptOptions"
              :key="opt.id"
              :label="opt.label"
              :value="opt.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem v-if="canAssignRoles" label="角色">
          <ElSelect
            v-model="form.role_ids"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="可多选"
            style="width: 100%"
          >
            <ElOption
              v-for="r in roles"
              :key="r.id"
              :label="r.name"
              :value="r.id"
            />
          </ElSelect>
        </ElFormItem>
        <p v-else class="field-tip">
          当前账号无 role:read，无法拉取/勾选角色；创建时角色为空，编辑时不改动原角色。
        </p>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="dialogLoading" @click="onSubmit">确定</ElButton>
      </template>
    </ElDialog>

    <ElDialog
      v-model="pwdDialogVisible"
      :title="`重置密码 · ${pwdUserName}`"
      width="400px"
      destroy-on-close
      @closed="pwdFormRef?.resetFields()"
    >
      <ElForm ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-position="top">
        <ElFormItem label="新密码" prop="password">
          <ElInput
            v-model="pwdForm.password"
            type="password"
            show-password
            maxlength="128"
            autocomplete="new-password"
          />
        </ElFormItem>
        <ElFormItem label="确认密码" prop="confirm">
          <ElInput
            v-model="pwdForm.confirm"
            type="password"
            show-password
            maxlength="128"
            autocomplete="new-password"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="pwdDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="pwdLoading" @click="onResetPwd">确定</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.user-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.toolbar {
  flex-shrink: 0;
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

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

/* 取消 Element Plus 相邻按钮默认左边距，与筛选项间距统一由 gap 控制 */
.filters :deep(.el-button + .el-button) {
  margin-left: 0;
}

.filter-username {
  width: 180px;
}

.toolbar-right {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.table-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 16px;
  background: var(--dt-bg-card);
  border: 1px solid var(--dt-border);
  border-radius: 8px;
  overflow: hidden;
}

.table-scroll {
  flex: 1;
  min-height: 0;
}

.role-tag {
  margin: 0 6px 4px 0;
}

.muted {
  color: var(--dt-text-secondary);
  font-size: 13px;
}

.pager {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.field-tip {
  margin: 0;
  font-size: 12px;
  color: var(--dt-text-secondary);
  line-height: 1.5;
}
</style>
