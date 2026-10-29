<script setup lang="ts">
/**
 * W2 占位：文档管理（路由需 doc:read）。
 * 上传/删除按钮在 W6 再拆 doc:upload / doc:delete。
 */
</script>

<template>
  <div class="placeholder">
    <h2>文档管理</h2>
    <p>占位页：上传、列表、下载与软删将在 <strong>W6</strong> 实现。</p>
  </div>
</template>

<style scoped>
.placeholder {
  background: var(--dt-bg-card);
  border: 1px solid var(--dt-border);
  border-radius: 8px;
  padding: 24px;
}

h2 {
  margin: 0 0 8px;
  font-size: 18px;
}

p {
  margin: 0;
  color: var(--dt-text-secondary);
  font-size: 14px;
}
</style>
