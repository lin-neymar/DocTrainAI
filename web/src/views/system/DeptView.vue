<script setup lang="ts">
/**
 * W2 占位：部门管理。
 * 树只读对已登录开放；写操作（增删改）在 W3 再校验 dept:manage。
 */
</script>

<template>
  <div class="placeholder">
    <h2>部门管理</h2>
    <p>占位页：部门树与增删改将在 <strong>W3</strong> 实现。</p>
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
