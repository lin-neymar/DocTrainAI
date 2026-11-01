<script setup lang="ts">
/**
 * 文档管理：路由 doc:read；上传 doc:create；编辑 doc:update；删除 doc:delete。
 * 可见组织：有 data:scope:all 或 dept:create 可勾选；部门官无勾选（后端固定本部门）。
 */
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules, UploadFile, UploadRawFile } from 'element-plus'
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElPagination,
  ElTable,
  ElTableColumn,
  ElTree,
  ElTreeSelect,
  ElUpload,
} from 'element-plus'

import { fetchDeptTreeApi, type DeptTreeNode } from '@/api/system/dept'
import {
  deleteDocApi,
  downloadDocFileApi,
  fetchDocsApi,
  previewDocFileApi,
  updateDocApi,
  uploadDocApi,
  type DocItem,
} from '@/api/system/doc'
import { audienceTreeForOwner, canCustomizeAudience, collectSubtreeIds } from '@/utils/audience'
import { formatDateTime } from '@/utils/datetime'
import { hasPermission } from '@/utils/permission'

type TreeExpose = {
  setCheckedKeys: (keys: string[]) => void
  getCheckedKeys: (leafOnly?: boolean) => (string | number)[]
}

const loading = ref(false)
const docs = ref<DocItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const deptTree = ref<DeptTreeNode[]>([])
const deptNameMap = ref<Record<string, string>>({})
const deptTreeSelectProps = {
  value: 'id',
  label: 'name',
  children: 'children',
} as const

const canCreate = computed(() => hasPermission('doc:create'))
const canUpdate = computed(() => hasPermission('doc:update'))
const canDelete = computed(() => hasPermission('doc:delete'))
const showAudiencePicker = computed(() => canCustomizeAudience())

const uploadVisible = ref(false)
const uploadLoading = ref(false)
const uploadFormRef = ref<FormInstance>()
const uploadAudienceTreeRef = ref<TreeExpose>()
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
const editAudienceTreeRef = ref<TreeExpose>()
const editForm = reactive({
  title: '',
  dept_id: '',
})
const pendingEditAudience = ref<string[]>([])

const uploadAudienceTree = computed(() => audienceTreeForOwner(deptTree.value, uploadForm.dept_id))
const editAudienceTree = computed(() => audienceTreeForOwner(deptTree.value, editForm.dept_id))

const treeProps = { label: 'name', children: 'children' }

const uploadRules: FormRules<typeof uploadForm> = {
  title: [
    { required: true, message: '请输入标题', trigger: 'blur' },
    { min: 1, max: 256, message: '长度 1–256', trigger: 'blur' },
  ],
  dept_id: [{ required: true, message: '请选择归属部门', trigger: 'change' }],
  file: [
    {
      validator: (_r, _v, cb) => {
        if (!uploadForm.file) cb(new Error('请选择 pdf / md / docx / xlsx / pptx 文件'))
        else cb()
      },
      trigger: 'change',
    },
  ],
}

/** 预览弹窗：pdf/office→iframe；md→纯文本；关闭时 revoke blob URL */
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewTitle = ref('')
const previewKind = ref<'pdf' | 'md' | null>(null)
const previewUrl = ref<string | null>(null)
const previewText = ref('')
const previewHint = ref('')

function revokePreviewUrl() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = null
  }
}

function resetPreviewState() {
  revokePreviewUrl()
  previewKind.value = null
  previewText.value = ''
  previewHint.value = ''
  previewTitle.value = ''
}

// 实现：拉取预览 blob；md 读文本，其余按 PDF 嵌入
async function openPreview(row: unknown) {
  const d = asDoc(row)
  resetPreviewState()
  previewTitle.value = d.title
  previewVisible.value = true
  previewLoading.value = true
  try {
    const { blob } = await previewDocFileApi(d.id)
    const ext = (d.extension || '').toLowerCase()
    if (ext === 'md') {
      previewText.value = await blob.text()
      previewKind.value = 'md'
    } else {
      // pdf 原件，或 office 转换后的 PDF
      previewUrl.value = URL.createObjectURL(blob)
      previewKind.value = 'pdf'
    }
  } catch {
    // 拦截器已提示（如无 LibreOffice 的 422）
    previewHint.value = '预览不可用，请下载原件查看'
    previewKind.value = null
  } finally {
    previewLoading.value = false
  }
}

function onPreviewClosed() {
  resetPreviewState()
}

const editRules: FormRules<typeof editForm> = {
  title: [
    { required: true, message: '请输入标题', trigger: 'blur' },
    { min: 1, max: 256, message: '长度 1–256', trigger: 'blur' },
  ],
  dept_id: [{ required: true, message: '请选择归属部门', trigger: 'change' }],
}

// 实现：遍历部门树，收集 id→名称（列表展示用）
function collectDeptNames(nodes: DeptTreeNode[]): Record<string, string> {
  const names: Record<string, string> = {}
  const walk = (list: DeptTreeNode[]) => {
    for (const n of list) {
      names[n.id] = n.name
      if (n.children?.length) walk(n.children)
    }
  }
  walk(nodes)
  return names
}

// 实现：取树中第一个节点 id（上传默认归属）
function firstDeptId(nodes: DeptTreeNode[]): string {
  return nodes[0]?.id ?? ''
}

// 实现：加载可见部门树（表单 TreeSelect，列表用名称映射）
async function loadDepts() {
  const tree = await fetchDeptTreeApi()
  deptTree.value = tree
  deptNameMap.value = collectDeptNames(tree)
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

function audienceLabel(row: unknown) {
  const ids = asDoc(row).audience_dept_ids ?? []
  if (!ids.length) return '—'
  return ids.map((id) => deptNameMap.value[id] || id.slice(0, 8)).join('、')
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// 实现：读取勾选的可见组织；无勾选能力时不传
function readAudienceKeys(treeRef: TreeExpose | undefined): string[] | undefined {
  if (!showAudiencePicker.value) return undefined
  return (treeRef?.getCheckedKeys(false) ?? []).map(String)
}

async function setAudienceKeys(treeRef: TreeExpose | undefined, keys: string[]) {
  await nextTick()
  treeRef?.setCheckedKeys(keys)
}

function openUpload() {
  if (!canCreate.value) return
  uploadForm.title = ''
  uploadForm.dept_id = firstDeptId(deptTree.value)
  uploadForm.file = null
  fileList.value = []
  uploadVisible.value = true
}

function openEdit(row: unknown) {
  if (!canUpdate.value) return
  const d = asDoc(row)
  editingId.value = d.id
  editForm.title = d.title
  editForm.dept_id = d.dept_id
  const ownerNode = audienceTreeForOwner(deptTree.value, editForm.dept_id)[0]
  const allowed = new Set(ownerNode ? collectSubtreeIds(ownerNode) : [d.dept_id])
  const fromServer = d.audience_dept_ids ?? [d.dept_id]
  pendingEditAudience.value = fromServer.filter((id) => allowed.has(id))
  if (!pendingEditAudience.value.length && editForm.dept_id) {
    pendingEditAudience.value = [editForm.dept_id]
  }
  editVisible.value = true
}

watch(uploadVisible, (open) => {
  if (!open || !showAudiencePicker.value) return
  void setAudienceKeys(uploadAudienceTreeRef.value, uploadForm.dept_id ? [uploadForm.dept_id] : [])
})

watch(editVisible, (open) => {
  if (!open || !showAudiencePicker.value) return
  void setAudienceKeys(editAudienceTreeRef.value, pendingEditAudience.value)
})

watch(
  () => uploadForm.dept_id,
  (id) => {
    if (!uploadVisible.value || !showAudiencePicker.value) return
    void setAudienceKeys(uploadAudienceTreeRef.value, id ? [id] : [])
  },
)

watch(
  () => editForm.dept_id,
  (id) => {
    if (!editVisible.value || !showAudiencePicker.value) return
    pendingEditAudience.value = id ? [id] : []
    void setAudienceKeys(editAudienceTreeRef.value, pendingEditAudience.value)
  },
)

/** 仅本地选文件，不走 ElUpload 自动上传 */
function onFileChange(uploadFile: UploadFile) {
  const raw = uploadFile.raw as UploadRawFile | undefined
  if (!raw) return
  const name = raw.name.toLowerCase()
  const okExt = /\.(pdf|md|docx|xlsx|pptx)$/i.test(name)
  if (!okExt) {
    ElMessage.warning('仅支持 pdf、md、docx、xlsx、pptx')
    fileList.value = []
    uploadForm.file = null
    return
  }
  uploadForm.file = raw
  fileList.value = [uploadFile]
  if (!uploadForm.title.trim()) {
    uploadForm.title = raw.name.replace(/\.(pdf|md|docx|xlsx|pptx)$/i, '')
  }
}

function onFileRemove() {
  uploadForm.file = null
  fileList.value = []
}

// 实现：multipart 上传（可带 audience）
async function onUploadSubmit() {
  const valid = await uploadFormRef.value?.validate().catch(() => false)
  if (!valid || !uploadForm.file) return

  const audience = readAudienceKeys(uploadAudienceTreeRef.value)
  if (showAudiencePicker.value && (!audience || audience.length === 0)) {
    ElMessage.warning('请至少勾选一个可见组织')
    return
  }

  uploadLoading.value = true
  try {
    await uploadDocApi(uploadForm.title.trim(), uploadForm.dept_id, uploadForm.file, audience)
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

// 实现：更新标题/部门/audience
async function onEditSubmit() {
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid || !editingId.value) return

  const audience = readAudienceKeys(editAudienceTreeRef.value)
  if (showAudiencePicker.value && (!audience || audience.length === 0)) {
    ElMessage.warning('请至少勾选一个可见组织')
    return
  }

  editLoading.value = true
  try {
    const body: {
      title: string
      dept_id: string
      audience_dept_ids?: string[]
    } = {
      title: editForm.title.trim(),
      dept_id: editForm.dept_id,
    }
    if (audience !== undefined) {
      body.audience_dept_ids = audience
    }
    await updateDocApi(editingId.value, body)
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

onUnmounted(() => {
  revokePreviewUrl()
})
</script>

<template>
  <div class="doc-page">
    <div class="toolbar">
      <span class="hint">
        仅展示当前可见文档；勾选组织节点表示该节点子树可读（含日后新建下级）
      </span>
      <div class="toolbar-right">
        <ElButton :loading="loading" @click="loadDocs">刷新</ElButton>
        <ElButton v-if="canCreate" type="primary" @click="openUpload">上传文档</ElButton>
      </div>
    </div>

    <div class="table-panel">
      <div class="table-scroll">
        <ElTable v-loading="loading" height="100%" :data="docs" stripe empty-text="暂无文档">
          <ElTableColumn prop="title" label="标题" min-width="160" />
          <ElTableColumn label="归属" min-width="110">
            <template #default="{ row }">
              {{ deptLabel(row) }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="可见组织" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              {{ audienceLabel(row) }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="original_filename" label="原文件名" min-width="140" />
          <ElTableColumn prop="extension" label="类型" width="80" />
          <ElTableColumn label="大小" width="100">
            <template #default="{ row }">
              {{ formatSize(asDoc(row).size_bytes) }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="上传时间" min-width="170">
            <template #default="{ row }">
              {{ formatDateTime(asDoc(row).created_at) }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <ElButton link type="primary" @click="openPreview(row)">查看</ElButton>
              <ElButton link type="primary" @click="onDownload(row)">下载</ElButton>
              <ElButton v-if="canUpdate" link type="primary" @click="openEdit(row)">编辑</ElButton>
              <ElButton v-if="canDelete" link type="danger" @click="onDelete(row)">删除</ElButton>
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
      v-model="uploadVisible"
      title="上传文档"
      width="520px"
      destroy-on-close
      @closed="uploadFormRef?.resetFields()"
    >
      <ElForm ref="uploadFormRef" :model="uploadForm" :rules="uploadRules" label-position="top">
        <ElFormItem label="标题" prop="title">
          <ElInput v-model="uploadForm.title" maxlength="256" />
        </ElFormItem>
        <ElFormItem label="归属部门" prop="dept_id">
          <ElTreeSelect
            v-model="uploadForm.dept_id"
            :data="deptTree"
            :props="deptTreeSelectProps"
            check-strictly
            filterable
            default-expand-all
            placeholder="请选择归属部门"
            style="width: 100%"
          />
        </ElFormItem>
        <ElFormItem v-if="showAudiencePicker" label="可见组织">
          <p class="field-tip">勾选节点后，该节点及下级部门人员可读；不级联勾选子节点。</p>
          <div class="audience-tree">
            <ElTree
              v-if="uploadAudienceTree.length"
              ref="uploadAudienceTreeRef"
              :data="uploadAudienceTree"
              :props="treeProps"
              show-checkbox
              check-strictly
              node-key="id"
              default-expand-all
            />
            <p v-else class="field-tip">请先选择归属部门</p>
          </div>
        </ElFormItem>
        <p v-else class="field-tip">可见范围固定为您所在部门（由服务端写入）。</p>
        <ElFormItem label="文件（pdf / md / docx / xlsx / pptx）" prop="file">
          <ElUpload
            :auto-upload="false"
            :limit="1"
            :file-list="fileList"
            accept=".pdf,.md,.docx,.xlsx,.pptx,application/pdf,text/markdown"
            @change="onFileChange"
            @remove="onFileRemove"
          >
            <ElButton>选择文件</ElButton>
          </ElUpload>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="uploadVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="uploadLoading" @click="onUploadSubmit"> 上传 </ElButton>
      </template>
    </ElDialog>

    <ElDialog
      v-model="previewVisible"
      :title="previewTitle || '文档预览'"
      width="1045px"
      top="5vh"
      destroy-on-close
      @closed="onPreviewClosed"
    >
      <div v-loading="previewLoading" class="preview-body">
        <p v-if="previewHint" class="preview-hint">{{ previewHint }}</p>
        <iframe
          v-if="previewKind === 'pdf' && previewUrl"
          class="preview-frame"
          :src="previewUrl"
          title="文档预览"
        />
        <pre v-else-if="previewKind === 'md'" class="preview-md">{{ previewText }}</pre>
        <p v-else-if="!previewLoading" class="preview-empty">暂无预览内容</p>
      </div>
    </ElDialog>

    <ElDialog
      v-model="editVisible"
      title="编辑文档"
      width="520px"
      destroy-on-close
      @closed="editFormRef?.resetFields()"
    >
      <ElForm ref="editFormRef" :model="editForm" :rules="editRules" label-position="top">
        <ElFormItem label="标题" prop="title">
          <ElInput v-model="editForm.title" maxlength="256" />
        </ElFormItem>
        <ElFormItem label="归属部门" prop="dept_id">
          <ElTreeSelect
            v-model="editForm.dept_id"
            :data="deptTree"
            :props="deptTreeSelectProps"
            check-strictly
            filterable
            default-expand-all
            placeholder="请选择归属部门"
            style="width: 100%"
          />
        </ElFormItem>
        <ElFormItem v-if="showAudiencePicker" label="可见组织">
          <div class="audience-tree">
            <ElTree
              v-if="editAudienceTree.length"
              ref="editAudienceTreeRef"
              :data="editAudienceTree"
              :props="treeProps"
              show-checkbox
              check-strictly
              node-key="id"
              default-expand-all
            />
          </div>
        </ElFormItem>
        <p v-else class="field-tip">可见范围固定为您所在部门（由服务端写入）。</p>
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

.pager {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.field-tip {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--dt-text-secondary);
  line-height: 1.5;
}

.audience-tree {
  max-height: 220px;
  overflow: auto;
  width: 100%;
  padding: 8px;
  border: 1px solid var(--dt-border);
  border-radius: 6px;
}

.preview-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: min(82vh, 825px);
  min-height: 410px;
}

.preview-hint {
  margin: 0;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--dt-text-secondary);
}

.preview-frame {
  flex: 1;
  width: 100%;
  min-height: 0;
  border: 1px solid var(--dt-border);
  border-radius: 6px;
  background: #fff;
}

.preview-md {
  flex: 1;
  min-height: 0;
  margin: 0;
  padding: 16px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  background: var(--dt-bg-card);
  border: 1px solid var(--dt-border);
  border-radius: 6px;
}

.preview-empty {
  margin: 24px 0 0;
  text-align: center;
  color: var(--dt-text-secondary);
}
</style>
