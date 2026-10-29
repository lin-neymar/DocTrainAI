<script setup lang="ts">
/**
 * W3 部门管理：树对已登录只读开放；增删改按钮用 hasPermission('dept:manage')。
 * 创建根部门另需 data:scope:all（与后端一致）；数据范围不在前端计算。
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
  ElSelect,
  ElTree,
} from 'element-plus'

import {
  createDeptApi,
  deleteDeptApi,
  fetchDeptTreeApi,
  updateDeptApi,
  type DeptTreeNode,
} from '@/api/system/dept'
import { hasPermission } from '@/utils/permission'

const treeData = ref<DeptTreeNode[]>([])
const loading = ref(false)
const selectedId = ref<string | null>(null)
const selectedName = ref('')

const canManage = computed(() => hasPermission('dept:manage'))
const canCreateRoot = computed(
  () => canManage.value && hasPermission('data:scope:all'),
)

const treeProps = { label: 'name', children: 'children' } as const

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const dialogLoading = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  /** 创建时：父级；编辑时：新父级（空字符串表示设为根，仅 scope:all） */
  parent_id: '' as string,
})

const rules: FormRules<typeof form> = {
  name: [
    { required: true, message: '请输入部门名称', trigger: 'blur' },
    { min: 1, max: 128, message: '长度 1–128', trigger: 'blur' },
  ],
}

/** 扁平化树，供编辑时选择父级（排除自身及子孙，避免成环） */
const parentOptions = computed(() => {
  const exclude = new Set<string>()
  if (dialogMode.value === 'edit' && selectedId.value) {
    exclude.add(selectedId.value)
    const walk = (nodes: DeptTreeNode[]) => {
      for (const n of nodes) {
        if (exclude.has(n.id)) {
          for (const c of n.children) exclude.add(c.id)
          walk(n.children)
        } else {
          walk(n.children)
        }
      }
    }
    walk(treeData.value)
  }

  const opts: { id: string; name: string; depth: number }[] = []
  const flatten = (nodes: DeptTreeNode[], depth: number) => {
    for (const n of nodes) {
      if (!exclude.has(n.id)) {
        opts.push({ id: n.id, name: n.name, depth })
      }
      flatten(n.children, depth + 1)
    }
  }
  flatten(treeData.value, 0)
  return opts
})

const dialogTitle = computed(() =>
  dialogMode.value === 'create' ? '新增部门' : '编辑部门',
)

// 实现：拉取可见部门树（范围由后端决定）
async function loadTree() {
  loading.value = true
  try {
    treeData.value = await fetchDeptTreeApi()
    if (selectedId.value) {
      const still = findNode(treeData.value, selectedId.value)
      if (!still) {
        selectedId.value = null
        selectedName.value = ''
      } else {
        selectedName.value = still.name
      }
    }
  } finally {
    loading.value = false
  }
}

function findNode(nodes: DeptTreeNode[], id: string): DeptTreeNode | null {
  for (const n of nodes) {
    if (n.id === id) return n
    const hit = findNode(n.children, id)
    if (hit) return hit
  }
  return null
}

// 实现：记录当前选中节点
function onNodeClick(data: DeptTreeNode) {
  selectedId.value = data.id
  selectedName.value = data.name
}

// 实现：打开新增对话框（parentId 为 null 表示根部门）
function openCreate(parentId: string | null) {
  if (!canManage.value) return
  if (parentId === null && !canCreateRoot.value) {
    ElMessage.warning('创建根部门需要 data:scope:all')
    return
  }
  dialogMode.value = 'create'
  form.name = ''
  form.parent_id = parentId ?? ''
  dialogVisible.value = true
}

// 实现：打开编辑对话框
function openEdit() {
  if (!canManage.value || !selectedId.value) return
  const node = findNode(treeData.value, selectedId.value)
  if (!node) return
  dialogMode.value = 'edit'
  form.name = node.name
  form.parent_id = node.parent_id ?? ''
  dialogVisible.value = true
}

// 实现：提交新增或更新
async function onSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  dialogLoading.value = true
  try {
    const name = form.name.trim()
    if (dialogMode.value === 'create') {
      await createDeptApi({
        name,
        parent_id: form.parent_id || null,
      })
      ElMessage.success('创建成功')
    } else if (selectedId.value) {
      const body: { name: string; parent_id: string | null } = {
        name,
        parent_id: form.parent_id || null,
      }
      await updateDeptApi(selectedId.value, body)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    await loadTree()
  } catch {
    // 错误已由 request 拦截器提示
  } finally {
    dialogLoading.value = false
  }
}

// 实现：确认后软删除选中部门
async function onDelete() {
  if (!canManage.value || !selectedId.value) return
  try {
    await ElMessageBox.confirm(
      `确定删除部门「${selectedName.value}」？有下级或用户时将被拒绝。`,
      '删除部门',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteDeptApi(selectedId.value)
    ElMessage.success('已删除')
    selectedId.value = null
    selectedName.value = ''
    await loadTree()
  } catch {
    // 409 等已由拦截器提示
  }
}

onMounted(() => {
  void loadTree()
})
</script>

<template>
  <div class="dept-page">
    <div class="toolbar">
      <div class="toolbar-left">
        <span v-if="selectedName" class="hint">当前选中：{{ selectedName }}</span>
        <span v-else class="hint">点击树节点选中部门</span>
      </div>
      <div class="toolbar-right">
        <ElButton :loading="loading" @click="loadTree">刷新</ElButton>
        <template v-if="canManage">
          <ElButton
            v-if="canCreateRoot"
            type="primary"
            plain
            @click="openCreate(null)"
          >
            新增根部门
          </ElButton>
          <ElButton
            type="primary"
            :disabled="!selectedId"
            @click="openCreate(selectedId)"
          >
            新增子部门
          </ElButton>
          <ElButton :disabled="!selectedId" @click="openEdit">编辑</ElButton>
          <ElButton type="danger" plain :disabled="!selectedId" @click="onDelete">
            删除
          </ElButton>
        </template>
      </div>
    </div>

    <div v-loading="loading" class="tree-panel">
      <ElTree
        v-if="treeData.length"
        :data="treeData"
        :props="treeProps"
        node-key="id"
        highlight-current
        default-expand-all
        :expand-on-click-node="false"
        :current-node-key="selectedId ?? undefined"
        @node-click="onNodeClick"
      />
      <p v-else-if="!loading" class="empty">暂无可见部门</p>
    </div>

    <ElDialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="420px"
      destroy-on-close
      @closed="formRef?.resetFields()"
    >
      <ElForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <ElFormItem label="部门名称" prop="name">
          <ElInput v-model="form.name" maxlength="128" placeholder="请输入名称" />
        </ElFormItem>
        <ElFormItem v-if="dialogMode === 'create'" label="上级部门">
          <ElInput
            :model-value="form.parent_id ? selectedName || form.parent_id : '（根部门）'"
            disabled
          />
        </ElFormItem>
        <ElFormItem v-else label="上级部门">
          <ElSelect
            v-model="form.parent_id"
            clearable
            filterable
            placeholder="留空表示设为根部门"
            style="width: 100%"
          >
            <ElOption
              v-for="opt in parentOptions"
              :key="opt.id"
              :label="`${'—'.repeat(opt.depth)} ${opt.name}`"
              :value="opt.id"
            />
          </ElSelect>
          <p v-if="!canCreateRoot" class="field-tip">无 data:scope:all 时请勿清空上级</p>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="dialogLoading" @click="onSubmit">
          确定
        </ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.dept-page {
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

.tree-panel {
  min-height: 320px;
  padding: 16px;
  background: var(--dt-bg-card);
  border: 1px solid var(--dt-border);
  border-radius: 8px;
}

.empty {
  margin: 40px 0;
  text-align: center;
  color: var(--dt-text-secondary);
  font-size: 14px;
}

.field-tip {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--dt-text-secondary);
}
</style>
