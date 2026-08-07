<template>
  <!-- 页面级骨架屏：首次进入页面/路由切换时的占位 -->
  <div class="page-skeleton" role="status" aria-live="polite" aria-label="内容加载中">
    <div class="sk-header">
      <el-skeleton-item variant="text" style="width: 160px; height: 28px" />
      <el-skeleton-item variant="text" style="width: 90px; height: 32px" />
    </div>
    <div class="sk-filter">
      <el-skeleton-item variant="text" style="width: 100px" />
      <el-skeleton-item variant="text" style="width: 120px" />
      <el-skeleton-item variant="text" style="width: 100px" />
      <el-skeleton-item variant="text" style="width: 80px; height: 32px" />
    </div>
    <div class="sk-table">
      <div v-for="i in rows" :key="i" class="sk-row">
        <el-skeleton-item variant="text" style="width: 18%" />
        <el-skeleton-item variant="text" style="width: 12%" />
        <el-skeleton-item variant="text" style="width: 14%" />
        <el-skeleton-item variant="text" style="width: 16%" />
        <el-skeleton-item variant="text" style="width: 12%" />
        <el-skeleton-item variant="text" style="width: 18%" />
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  rows: { type: Number, default: 6 },
})
</script>

<style scoped>
.page-skeleton {
  padding: 4px 0;
}

.sk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.sk-filter {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 16px;
  background: var(--el-bg-color, #fff);
  border-radius: 4px;
  border: 1px solid var(--el-border-color-light, #ebeef5);
  margin-bottom: 16px;
}

.sk-table {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  background: var(--el-bg-color, #fff);
  border-radius: 4px;
  border: 1px solid var(--el-border-color-light, #ebeef5);
}

.sk-row {
  display: flex;
  gap: 16px;
  align-items: center;
}
</style>
