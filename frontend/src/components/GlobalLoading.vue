<template>
  <!-- 全局路由切换 Loading 蒙层 -->
  <transition name="fade">
    <div v-if="visible" class="global-loading-mask" role="status" aria-live="polite">
      <div class="global-loading-spinner">
        <el-icon class="is-loading" :size="36"><Loading /></el-icon>
        <span class="global-loading-text">{{ text }}</span>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref } from 'vue'
import { Loading } from '@element-plus/icons-vue'

defineProps({
  text: { type: String, default: '加载中...' },
})

const visible = ref(false)
let timer = null

/** 显示全局加载（延迟 200ms 显示，避免快速响应时闪烁） */
function show(text) {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    visible.value = true
  }, 200)
}

/** 隐藏全局加载 */
function hide() {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
  visible.value = false
}

defineExpose({ show, hide })
</script>

<style scoped>
.global-loading-mask {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-loading-bg, rgba(255, 255, 255, 0.7));
  backdrop-filter: blur(2px);
}

.global-loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--el-color-primary, #409eff);
}

.global-loading-text {
  font-size: 14px;
  color: var(--el-text-color-regular, #606266);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

html.dark .global-loading-mask {
  background: rgba(20, 22, 30, 0.7);
}
</style>
