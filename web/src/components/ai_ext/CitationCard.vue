<script setup lang="ts">
/**
 * 引用卡片（阶段 3）：展示文档标题、位置可读文案与片段。
 * 流式期间 citation 事件先于 delta，卡片独立渲染不阻塞正文。
 */
import { computed } from 'vue'

import type { Citation } from '@/api/ai_ext/chat'

const props = defineProps<{
  citation: Citation
}>()

// 实现：location 元信息转可读文案（与后端 loaders 的构造一一对应）
function locationText(location: Record<string, unknown> | null): string {
  if (!location) return '—'
  const ext = String(location.ext ?? '')
  if (ext === 'md') {
    return location.heading ? `标题：${String(location.heading)}` : 'Markdown'
  }
  if (ext === 'pdf') {
    return location.page ? `第 ${String(location.page)} 页` : 'PDF'
  }
  if (ext === 'xlsx') {
    return location.sheet ? `工作表：${String(location.sheet)}` : '表格'
  }
  if (ext === 'pptx') {
    return location.slide ? `第 ${String(location.slide)} 页` : '演示文稿'
  }
  if (ext === 'docx') return 'Word 文档'
  return ext
}

const location = computed(() => locationText(props.citation.location))
</script>

<template>
  <div class="citation-card">
    <div class="head">
      <span class="title">{{ citation.doc_title }}</span>
      <span class="loc">{{ location }}</span>
    </div>
    <div class="snippet">{{ citation.snippet }}</div>
  </div>
</template>

<style scoped>
.citation-card {
  margin-top: 8px;
  padding: 8px 12px;
  border-left: 3px solid var(--dt-color-primary);
  background: var(--dt-bg-page);
  border-radius: 0 6px 6px 0;
  font-size: 13px;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.title {
  font-weight: 600;
  color: var(--dt-text);
}

.loc {
  color: var(--dt-text-secondary);
  font-size: 12px;
  white-space: nowrap;
}

.snippet {
  margin-top: 4px;
  color: var(--dt-text-secondary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
