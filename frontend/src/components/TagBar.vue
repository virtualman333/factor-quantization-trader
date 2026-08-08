<template>
  <div class="tag-bar" @contextmenu.prevent>
    <!-- 左侧切换菜单 -->
    <div class="tag-actions">
      <el-dropdown trigger="click" @command="onCommand" :show-timeout="0">
        <el-button text :icon="ArrowDown" class="tag-more" />
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="closeOthers">关闭其它</el-dropdown-item>
            <el-dropdown-item command="closeAll">关闭全部</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 标签滚动区 -->
    <div ref="scrollRef" class="tag-scroll">
      <div class="tag-list">
        <div
          v-for="tab in tabsStore.tabList"
          :key="tab.path"
          class="tag-item"
          :class="{ active: isActive(tab) }"
          @click="go(tab)"
          @contextmenu.prevent="openContext(tab, $event)"
        >
          <span class="tag-dot" v-if="tab.affix" />
          <span class="tag-title">{{ tab.title }}</span>
          <el-icon v-if="!tab.affix" class="tag-close" @click.stop="close(tab)">
            <Close />
          </el-icon>
        </div>
      </div>
    </div>

    <!-- 右键菜单 -->
    <Teleport to="body">
      <div
        v-if="ctxMenu.visible"
        class="ctx-menu"
        :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
        @mouseleave="ctxMenu.visible = false"
      >
        <div class="ctx-item" @click="ctxAction('refresh')">刷新页面</div>
        <div class="ctx-item" @click="ctxAction('close')">关闭标签</div>
        <div class="ctx-item" @click="ctxAction('closeOthers')">关闭其它</div>
        <div class="ctx-item" @click="ctxAction('closeAll')">关闭全部</div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Close, ArrowDown } from '@element-plus/icons-vue'
import { useTabsStore } from '@/stores/tabs'

const route = useRoute()
const router = useRouter()
const tabsStore = useTabsStore()

const scrollRef = ref(null)
const ctxMenu = ref({ visible: false, x: 0, y: 0, tab: null })

const isActive = (tab) => {
  return route.path === tab.path || (tab.affix && route.path === '/dashboard')
}

const go = (tab) => {
  if (route.path === tab.path) return
  router.push(tab.fullPath || tab.path)
}

const close = (tab) => {
  const target = tabsStore.removeTab(tab.path)
  if (target && route.path === tab.path) {
    router.push(target)
  }
}

const openContext = (tab, e) => {
  ctxMenu.value = { visible: true, x: e.clientX, y: e.clientY, tab }
}

const ctxAction = (action) => {
  const tab = ctxMenu.value.tab
  ctxMenu.value.visible = false
  if (!tab) return
  if (action === 'refresh') {
    // 刷新：MainLayout 监听 refresh 标记，将组件从 keep-alive 缓存中移除重建
    tabsStore.refresh(tab.path)
  } else if (action === 'close') {
    close(tab)
  } else if (action === 'closeOthers') {
    tabsStore.closeOthers(tab.path)
  } else if (action === 'closeAll') {
    const target = tabsStore.closeAll()
    router.push(target)
  }
}

const onCommand = (cmd) => {
  if (cmd === 'closeOthers') {
    const cur = tabsStore.tabList.find((t) => isActive(t))
    if (cur) tabsStore.closeOthers(cur.path)
  } else if (cmd === 'closeAll') {
    const target = tabsStore.closeAll()
    router.push(target)
  }
}

// 监听路由变化，自动添加标签
let unwatch = null
onMounted(() => {
  unwatch = route
  // 初始添加当前路由
  tabsStore.addTab(route)
})

onBeforeUnmount(() => {
  if (unwatch) unwatch = null
})
</script>

<style scoped>
.tag-bar {
  display: flex;
  align-items: center;
  height: 36px;
  background: var(--app-header-bg);
  border-bottom: 1px solid var(--app-header-border);
  padding: 0 8px;
  overflow: hidden;
}
.tag-actions {
  flex-shrink: 0;
  margin-right: 4px;
}
.tag-more {
  font-size: 14px;
  color: #606266;
  padding: 4px;
}
.tag-scroll {
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  display: flex;
  align-items: center;
  scrollbar-width: none;
}
.tag-scroll::-webkit-scrollbar { display: none; }
.tag-list {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  padding: 4px 0;
}
.tag-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 8px;
  border-radius: 4px;
  border: 1px solid var(--app-header-border);
  background: transparent;
  color: #606266;
  font-size: 12px;
  cursor: pointer;
  transition: all .2s;
  user-select: none;
}
.tag-item:hover {
  border-color: #409eff;
  color: #409eff;
}
.tag-item.active {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
}
.tag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  opacity: .7;
}
.tag-title { max-width: 140px; overflow: hidden; text-overflow: ellipsis; }
.tag-close {
  font-size: 12px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  transition: background .2s;
}
.tag-close:hover {
  background: rgba(255,255,255,.3);
}
.ctx-menu {
  position: fixed;
  z-index: 3000;
  min-width: 110px;
  background: var(--app-header-bg);
  border: 1px solid var(--app-header-border);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0,0,0,.12);
  padding: 4px 0;
  font-size: 13px;
  color: #606266;
}
.ctx-item {
  padding: 7px 14px;
  cursor: pointer;
  transition: background .15s;
}
.ctx-item:hover { background: #ecf5ff; color: #409eff; }
</style>
