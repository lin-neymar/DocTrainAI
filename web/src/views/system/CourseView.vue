<script setup lang="ts">
/**
 * W7 课程管理：范围内列表 + 创建/编辑/软删 + 整体替换挂接文档。
 * 路由 course:read；写操作按钮用 course:manage。
 * 挂接文档选项来自可见文档列表；不在前端计算数据范围。
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

import {
  createCourseApi,
  deleteCourseApi,
  fetchCoursesApi,
  replaceCourseDocsApi,
  updateCourseApi,
  type CourseItem,
} from '@/api/system/course'
import { fetchDeptTreeApi, type DeptTreeNode } from '@/api/system/dept'
import { fetchDocsApi, type DocItem } from '@/api/system/doc'
import { hasPermission } from '@/utils/permission'

const loading = ref(false)
const courses = ref<CourseItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const deptOptions = ref<{ id: string; label: string }[]>([])
const deptNameMap = ref<Record<string, string>>({})
const visibleDocs = ref<DocItem[]>([])
const docTitleMap = computed(() => {
  const map: Record<string, string> = {}
  for (const d of visibleDocs.value) map[d.id] = d.title
  return map
})

const canManage = computed(() => hasPermission('course:manage'))
const canReadDocs = computed(() => hasPermission('doc:read'))

const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const formLoading = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  title: '',
  description: '',
  dept_id: '',
})

const docsVisible = ref(false)
const docsLoading = ref(false)
const docsCourseId = ref<string | null>(null)
const docsCourseTitle = ref('')
const selectedDocIds = ref<string[]>([])

const formRules: FormRules<typeof form> = {
  title: [
    { required: true, message: '请输入课程标题', trigger: 'blur' },
    { min: 1, max: 256, message: '长度 1–256', trigger: 'blur' },
  ],
  dept_id: [{ required: true, message: '请选择归属部门', trigger: 'change' }],
}

const formTitle = computed(() =>
  formMode.value === 'create' ? '新增课程' : '编辑课程',
)

// 实现：部门树展平为下拉
function flattenDepts(nodes: DeptTreeNode[]) {
  const opts: { id: string; label: string }[] = []
  const names: Record<string, string> = {}
  const walk = (list: DeptTreeNode[], depth: number) => {
    for (const n of list) {
      const prefix = depth > 0 ? `${'—'.repeat(depth)} ` : ''
      opts.push({ id: n.id, label: `${prefix}${n.name}` })
      names[n.id] = n.name
      walk(n.children, depth + 1)
    }
  }
  walk(nodes, 0)
  return { opts, names }
}

async function loadDepts() {
  const tree = await fetchDeptTreeApi()
  const { opts, names } = flattenDepts(tree)
  deptOptions.value = opts
  deptNameMap.value = names
}

// 实现：拉取可见文档（挂接多选与标题展示；无 doc:read 则跳过）
async function loadVisibleDocs() {
  if (!canReadDocs.value) {
    visibleDocs.value = []
    return
  }
  const data = await fetchDocsApi(1, 100)
  visibleDocs.value = data.items
}

// 实现：分页拉取课程列表
async function loadCourses() {
  loading.value = true
  try {
    const data = await fetchCoursesApi(page.value, pageSize.value)
    courses.value = data.items
    total.value = data.total
    page.value = data.page
    pageSize.value = data.page_size
  } finally {
    loading.value = false
  }
}

function asCourse(row: unknown): CourseItem {
  return row as CourseItem
}

function deptLabel(row: unknown) {
  const c = asCourse(row)
  return deptNameMap.value[c.dept_id] || c.dept_id.slice(0, 8)
}

function docLabels(row: unknown) {
  const ids = asCourse(row).doc_ids
  if (!ids.length) return [] as string[]
  return ids.map((id) => docTitleMap.value[id] || id.slice(0, 8))
}

function openCreate() {
  if (!canManage.value) return
  formMode.value = 'create'
  editingId.value = null
  form.title = ''
  form.description = ''
  form.dept_id = deptOptions.value[0]?.id ?? ''
  formVisible.value = true
}

function openEdit(row: unknown) {
  if (!canManage.value) return
  const c = asCourse(row)
  formMode.value = 'edit'
  editingId.value = c.id
  form.title = c.title
  form.description = c.description ?? ''
  form.dept_id = c.dept_id
  formVisible.value = true
}

async function openAttachDocs(row: unknown) {
  if (!canManage.value) return
  const c = asCourse(row)
  docsCourseId.value = c.id
  docsCourseTitle.value = c.title
  selectedDocIds.value = [...c.doc_ids]
  try {
    await loadVisibleDocs()
  } catch {
    // 拦截器已提示
  }
  docsVisible.value = true
}

// 实现：创建或更新课程元数据
async function onSubmitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  formLoading.value = true
  try {
    const title = form.title.trim()
    const description = form.description.trim() || null
    if (formMode.value === 'create') {
      await createCourseApi({
        title,
        description,
        dept_id: form.dept_id,
      })
      ElMessage.success('创建成功')
    } else if (editingId.value) {
      await updateCourseApi(editingId.value, {
        title,
        description,
        dept_id: form.dept_id,
      })
      ElMessage.success('更新成功')
    }
    formVisible.value = false
    await loadCourses()
  } catch {
    // 拦截器已提示
  } finally {
    formLoading.value = false
  }
}

// 实现：整体替换课程挂接文档
async function onSubmitDocs() {
  if (!docsCourseId.value) return
  docsLoading.value = true
  try {
    await replaceCourseDocsApi(docsCourseId.value, selectedDocIds.value)
    ElMessage.success('挂接已更新')
    docsVisible.value = false
    await loadCourses()
  } catch {
    // 拦截器已提示
  } finally {
    docsLoading.value = false
  }
}

// 实现：软删除课程（不删已挂接文档）
async function onDelete(row: unknown) {
  if (!canManage.value) return
  const c = asCourse(row)
  try {
    await ElMessageBox.confirm(
      `确定删除课程「${c.title}」？已挂接文档不会被删除。`,
      '删除课程',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteCourseApi(c.id)
    ElMessage.success('已删除')
    if (courses.value.length <= 1 && page.value > 1) {
      page.value -= 1
    }
    await loadCourses()
  } catch {
    // 拦截器已提示
  }
}

async function onPageChange(p: number) {
  page.value = p
  await loadCourses()
}

async function onSizeChange(size: number) {
  pageSize.value = size
  page.value = 1
  await loadCourses()
}

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([loadDepts(), loadVisibleDocs()])
    await loadCourses()
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="course-page">
    <div class="toolbar">
      <span class="hint">挂接文档不放大文档权限；删课程不删文档</span>
      <div class="toolbar-right">
        <ElButton :loading="loading" @click="loadCourses">刷新</ElButton>
        <ElButton v-if="canManage" type="primary" @click="openCreate">新增课程</ElButton>
      </div>
    </div>

    <div class="table-panel">
      <ElTable v-loading="loading" :data="courses" stripe empty-text="暂无课程">
        <ElTableColumn prop="title" label="标题" min-width="160" />
        <ElTableColumn label="部门" min-width="120">
          <template #default="{ row }">
            {{ deptLabel(row) }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="简介" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ asCourse(row).description || '—' }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="挂接文档" min-width="220">
          <template #default="{ row }">
            <template v-if="docLabels(row).length">
              <ElTag
                v-for="name in docLabels(row)"
                :key="name"
                class="doc-tag"
                size="small"
                effect="plain"
              >
                {{ name }}
              </ElTag>
            </template>
            <span v-else class="muted">未挂接</span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="updated_at" label="更新时间" min-width="170" />
        <ElTableColumn v-if="canManage" label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openEdit(row)">编辑</ElButton>
            <ElButton link type="primary" @click="openAttachDocs(row)">挂接文档</ElButton>
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
      v-model="formVisible"
      :title="formTitle"
      width="480px"
      destroy-on-close
      @closed="formRef?.resetFields()"
    >
      <ElForm ref="formRef" :model="form" :rules="formRules" label-position="top">
        <ElFormItem label="标题" prop="title">
          <ElInput v-model="form.title" maxlength="256" />
        </ElFormItem>
        <ElFormItem label="简介">
          <ElInput
            v-model="form.description"
            type="textarea"
            :rows="3"
            maxlength="2000"
            show-word-limit
            placeholder="可选"
          />
        </ElFormItem>
        <ElFormItem label="归属部门" prop="dept_id">
          <ElSelect v-model="form.dept_id" filterable style="width: 100%">
            <ElOption
              v-for="opt in deptOptions"
              :key="opt.id"
              :label="opt.label"
              :value="opt.id"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="formVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="formLoading" @click="onSubmitForm">确定</ElButton>
      </template>
    </ElDialog>

    <ElDialog
      v-model="docsVisible"
      :title="`挂接文档 · ${docsCourseTitle}`"
      width="520px"
      destroy-on-close
    >
      <p class="field-tip">
        仅列出当前可见文档；整体替换后以本次勾选为准（可清空）。
      </p>
      <ElSelect
        v-model="selectedDocIds"
        multiple
        filterable
        collapse-tags
        collapse-tags-tooltip
        placeholder="选择要挂接的文档"
        style="width: 100%"
      >
        <ElOption
          v-for="d in visibleDocs"
          :key="d.id"
          :label="`${d.title}（${d.original_filename}）`"
          :value="d.id"
        />
      </ElSelect>
      <p v-if="!visibleDocs.length" class="field-tip">暂无可见文档，请先在文档管理上传。</p>
      <template #footer>
        <ElButton @click="docsVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="docsLoading" @click="onSubmitDocs">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.course-page {
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

.doc-tag {
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

.field-tip {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--dt-text-secondary);
  line-height: 1.5;
}
</style>
