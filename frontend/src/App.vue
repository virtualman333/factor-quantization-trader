<template>
  <router-view v-slot="{ Component }">
    <transition name="fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
  <!-- 全局 Loading 蒙层 -->
  <GlobalLoading ref="globalLoadingRef" />
  <!-- 快捷键帮助面板 -->
  <ShortcutHelp ref="shortcutHelpRef" />
</template>

<script setup>
import { ref, provide } from 'vue'
import GlobalLoading from '@/components/GlobalLoading.vue'
import ShortcutHelp from '@/components/ShortcutHelp.vue'

const globalLoadingRef = ref(null)
const shortcutHelpRef = ref(null)

// 提供给全局使用的加载控制（通过 inject 在任意子组件调用）
provide('globalLoading', {
  show: (text) => globalLoadingRef.value?.show(text),
  hide: () => globalLoadingRef.value?.hide(),
})

provide('shortcutHelp', {
  open: () => shortcutHelpRef.value?.open(),
})
</script>
