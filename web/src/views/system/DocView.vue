<script setup lang="ts">
/**
 * W6 文档管理：可见列表 + 上传/改元数据/下载/软删。
 * 路由 doc:read；上传与编辑按钮 doc:upload；删除按钮 doc:delete。
 * 数据范围与可见性不在前端计算；不展示解析状态（阶段 2）。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules, UploadFile, UploadRawFile } from 'element-plus'
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
  ElUpload,
} from 'element-plus'

import { fetchDeptTreeApi, type DeptTreeNode } from '@/api/system/dept'
import {
  deleteDocApi,
  downloadDocFileApi,
  fetchDocsApi,
  updateDocApi,
  uploadDocApi,
  type DocItem,
} from '@/api/system/doc'
import { hasPermission } from '@/utils/permission'

const loading = ref(false)
const docs = ref<DocItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const deptOptions = ref<{ id: string; label: string }[]>([])
const deptNameMap = ref<Record<string, string>>({})

const canUpload = computed(() => hasPermission('doc:upload'))
const canDelete = computed(() => hasPermission('doc:delete'))

const uploadVisible = ref(false)
const uploadLoading = ref(false)
const uploadFormRef = ref<FormInstance>()
const uploadForm = reactive({
  title: '',
  dept_id: '',
  file: null as File | null,
})
const fileList = ref<UploadFile[]>([])

const editVisible = ref(false)
const editLoading = ref(false)
const editingId = ref<string | null>(null)
const editFormRef = ref<FormInstance>()
const editForm = reactive({
  title: '',
  dept_id: '',
})

const uploadRules: FormRules<typeof uploadForm> = {
  title: [
    { required: true, message: '请输入标题', trigger: 'blur' },
    { min: 1, max: 256, message: '长度 1–256', trigger: 'blur' },
  ],
  dept_id: [{ required: true, message: '请选择归属部门', trigger: 'change' }],
  file: [
    {
      validator: (_r, _v, cb) => {
        if (!uploadForm.file) cb(new Error('请选择 pdf 或 md 文件'))
        else cb()
      },
      trigger: 'change',
    },
  ],
}

const editRules: FormRules<typeof editForm> = {
  title: [
    { required: true, message: '请输入标题', trigger: 'blur' },
    { min: 1, max: 256, message: '长度 1–256', trigger: 'blur' },
  ],
  dept_id: [{ required: true, message: '请选择归属部门', trigger: 'change' }],
}

// 实现：部门树展平为下拉（缩进表示层级）
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

// 实现：分页拉取可见文档
async function loadDocs() {
  loading.value = true
  try {
    const data = await fetchDocsApi(page.value, pageSize.value)
    docs.value = data.items
    total.value = data.total
    page.value = data.page
    pageSize.value = data.page_size
  } finally {
    loading.value = false
  }
}

function asDoc(row: unknown): DocItem {
  return row as DocItem
}

function deptLabel(row: unknown) {
  const d = asDoc(row)
  return deptNameMap.value[d.dept_id] || d.dept_id.slice(0, 8)
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function openUpload() {
  if (!canUpload.value) return
  uploadForm.title = ''
  uploadForm.dept_id = deptOptions.value[0]?.id ?? ''
  uploadForm.file = null
  fileList.value = []
  uploadVisible.value = true
}

function openEdit(row: unknown) {
  if (!canUpload.value) return
  const d = asDoc(row)
  editingId.value = d.id
  editForm.title = d.title
  editForm.dept_id = d.dept_id
  editVisible.value = true
}

/** 仅本地选文件，不走 ElUpload 自动上传 */
function onFileChange(uploadFile: UploadFile) {
  const raw = uploadFile.raw as UploadRawFile | undefined
  if (!raw) return
  const name = raw.name.toLowerCase()
  if (!name.endsWith('.pdf') && !name.endsWith('.md')) {
    ElMessage.warning('仅支持 pdf、md')
    fileList.value = []
    uploadForm.file = null
    return
  }
  uploadForm.file = raw
  fileList.value = [uploadFile]
  if (!uploadForm.title.trim()) {
    uploadForm.title = raw.name.replace(/\.(pdf|md)$/i, '')
  }
}

function onFileRemove() {
  uploadForm.file = null
  fileList.value = []
}

// 实现：multipart 上传
async function onUploadSubmit() {
  const valid = await uploadFormRef.value?.validate().catch(() => false)
  if (!valid || !uploadForm.file) return

  uploadLoading.value = true
  try {
    await uploadDocApi(uploadForm.title.trim(), uploadForm.dept_id, uploadForm.file)
    ElMessage.success('上传成功')
    uploadVisible.value = false
    page.value = 1
    await loadDocs()
  } catch {
    // 拦截器已提示
  } finally {
    uploadLoading.value = false
  }
}

// 实现：更新标题/部门（不换原文件）
async function onEditSubmit() {
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid || !editingId.value) return

  editLoading.value = true
  try {
    await updateDocApi(editingId.value, {
      title: editForm.title.trim(),
      dept_id: editForm.dept_id,
    })
    ElMessage.success('已更新')
    editVisible.value = false
    await loadDocs()
  } catch {
    // 拦截器已提示
  } finally {
    editLoading.value = false
  }
}

// 实现：触发浏览器下载原文件
async function onDownload(row: unknown) {
  const d = asDoc(row)
  try {
    const { blob, filename } = await downloadDocFileApi(d.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || d.original_filename || `${d.title}.${d.extension}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch {
    // 拦截器已提示
  }
}

// 实现：软删除文档
async function onDelete(row: unknown) {
  if (!canDelete.value) return
  const d = asDoc(row)
  try {
    await ElMessageBox.confirm(`确定删除文档「${d.title}」？`, '删除文档', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteDocApi(d.id)
    ElMessage.success('已删除')
    if (docs.value.length <= 1 && page.value > 1) {
      page.value -= 1
    }
    await loadDocs()
  } catch {
    // 拦截器已提示
  }
}

async function onPageChange(p: number) {
  page.value = p
  await loadDocs()
}

async function onSizeChange(size: number) {
  pageSize.value = size
  page.value = 1
  await loadDocs()
}

onMounted(async () => {
  loading.value = true
  try {
    await loadDepts()
    await loadDocs()
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="doc-page">
    <div class="toolbar">
      <span class="hint">仅展示当前可见文档；阶段 1 不解析正文、不显示解析状态</span>
      <div class="toolbar-right">
        <ElButton :loading="loading" @click="loadDocs">刷新</ElButton>
        <ElButton v-if="canUpload" type="primary" @click="openUpload">上传文档</ElButton>
      </div>
    </div>

    <div class="table-panel">
      <ElTable v-loading="loading" :data="docs" stripe empty-text="暂无文档">
        <ElTableColumn prop="title" label="标题" min-width="160" />
        <ElTableColumn label="部门" min-width="120">
          <template #default="{ row }">
            {{ deptLabel(row) }}
          </template>
        </ElTableColumn>
        <ElTableColumn prop="original_filename" label="原文件名" min-width="140" />
        <ElTableColumn prop="extension" label="类型" width="80" />
        <ElTableColumn label="大小" width="100">
          <template #default="{ row }">
            {{ formatSize(asDoc(row).size_bytes) }}
          </template>
        </ElTableColumn>
        <ElTableColumn prop="created_at" label="上传时间" min-width="170" />
        <ElTableColumn label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click="onDownload(row)">下载</ElButton>
            <ElButton v-if="canUpload" link type="primary" @click="openEdit(row)">编辑</ElButton>
            <ElButton v-if="canDelete" link type="danger" @click="onDelete(row)">删除</ElButton>
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
      v-model="uploadVisible"
      title="上传文档"
      width="480px"
      destroy-on-close
      @closed="uploadFormRef?.resetFields()"
    >
      <ElForm
        ref="uploadFormRef"
        :model="uploadForm"
        :rules="uploadRules"
        label-position="top"
      >
        <ElFormItem label="标题" prop="title">
          <ElInput v-model="uploadForm.title" maxlength="256" />
        </ElFormItem>
        <ElFormItem label="归属部门" prop="dept_id">
          <ElSelect v-model="uploadForm.dept_id" filterable style="width: 100%">
            <ElOption
              v-for="opt in deptOptions"
              :key="opt.id"
              :label="opt.label"
              :value="opt.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="文件（pdf / md）" prop="file">
          <ElUpload
            :auto-upload="false"
            :limit="1"
            :file-list="fileList"
            accept=".pdf,.md,application/pdf,text/markdown"
            @change="onFileChange"
            @remove="onFileRemove"
          >
            <ElButton>选择文件</ElButton>
          </ElUpload>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="uploadVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="uploadLoading" @click="onUploadSubmit">
          上传
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog
      v-model="editVisible"
      title="编辑文档"
      width="440px"
      destroy-on-close
      @closed="editFormRef?.resetFields()"
    >
      <ElForm ref="editFormRef" :model="editForm" :rules="editRules" label-position="top">
        <ElFormItem label="标题" prop="title">
          <ElInput v-model="editForm.title" maxlength="256" />
        </ElFormItem>
        <ElFormItem label="归属部门" prop="dept_id">
          <ElSelect v-model="editForm.dept_id" filterable style="width: 100%">
            <ElOption
              v-for="opt in deptOptions"
              :key="opt.id"
              :label="opt.label"
              :value="opt.id"
            />
          </ElSelect>
        </ElFormItem>
        <p class="field-tip">阶段 1 不支持覆盖原文件，仅改标题与部门。</p>
      </ElForm>
      <template #footer>
        <ElButton @click="editVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="editLoading" @click="onEditSubmit">确定</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.doc-page {
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

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.field-tip {
  margin: 0;
  font-size: 12px;
  color: var(--dt-text-secondary);
}
</style>
