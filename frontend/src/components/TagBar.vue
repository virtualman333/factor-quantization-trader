<template>
  <div class="tag-bar" @contextmenu.prevent>
    <!-- 左侧标签列表 -->
    <div class="tag-actions">
      <el-dropdown trigger="click" @command="onCommand" :show-timeout="0">
        <el-tooltip content="已打开页面" placement="bottom">
          <el-button text :icon="Grid" class="tag-more" />
        </el-tooltip>
        <template #dropdown>
          <el-dropdown-menu class="tabs-list-menu">
            <el-dropdown-item
              v-for="tab in tabsStore.tabList"
              :key="tab.path"
              :command="'go:' + tab.path"
              :class="{ 'tabs-active': isActive(tab) }"
            >
              <el-icon class="tabs-list-icon" :size="14">
                <component :is="iconOf(tab)" />
              </el-icon>
              <span class="tabs-list-title">{{ tab.title }}</span>
              <el-icon
                v-if="!tab.affix"
                class="tabs-list-close"
                :size="12"
                @click.stop="close(tab)"
              ><Close /></el-icon>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 左滚动按钮 -->
    <button
      v-if="showScrollLeft"
      class="tag-scroll-btn"
      @click="scrollBy(-1)"
    >
      <el-icon :size="12"><ArrowLeft /></el-icon>
    </button>

    <!-- 标签滚动区 -->
    <div ref="scrollRef" class="tag-scroll">
      <div class="tag-list">
        <div
          v-for="tab in tabsStore.tabList"
          :key="tab.path"
          class="tag-item"
          :class="{ active: isActive(tab) }"
          @click="go(tab)"
          @dblclick.self="dblClickTab(tab)"
          @contextmenu.prevent="openContext(tab, $event)"
        >
          <el-icon v-if="iconOf(tab)" class="tag-icon" :size="13">
            <component :is="iconOf(tab)" />
          </el-icon>
          <span class="tag-title">{{ tab.title }}</span>
          <span
            v-if="!tab.affix"
            class="tag-close"
            @click.stop="close(tab)"
          >
            <el-icon :size="12"><Close /></el-icon>
          </span>
          <span v-else class="tag-dot" />
        </div>
      </div>
    </div>

    <!-- 右滚动按钮 -->
    <button
      v-if="showScrollRight"
      class="tag-scroll-btn"
      @click="scrollBy(1)"
    >
      <el-icon :size="12"><ArrowRight /></el-icon>
    </button>

    <!-- 右侧操作区 -->
    <div class="tag-tools">
      <el-tooltip content="刷新当前页" placement="bottom">
        <el-button text :icon="Refresh" class="tag-tool-btn" @click="refreshActive" />
      </el-tooltip>
      <el-dropdown trigger="click" @command="onCommand" :show-timeout="0">
        <el-tooltip content="更多操作" placement="bottom">
          <el-button text :icon="ArrowDown" class="tag-tool-btn" />
        </el-tooltip>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="closeOthers">关闭其它</el-dropdown-item>
            <el-dropdown-item command="closeAll">关闭全部</el-dropdown-item>
            <el-dropdown-item command="closeLeft" divided>关闭左侧</el-dropdown-item>
            <el-dropdown-item command="closeRight">关闭右侧</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 右键菜单 -->
    <Teleport to="body">
      <div
        v-if="ctxMenu.visible"
        class="ctx-menu"
        :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
      >
        <div class="ctx-item" @click="ctxAction('refresh')">刷新页面</div>
        <div class="ctx-item" @click="ctxAction('close')">关闭标签</div>
        <div class="ctx-item" @click="ctxAction('closeLeft')">关闭左侧</div>
        <div class="ctx-item" @click="ctxAction('closeRight')">关闭右侧</div>
        <div class="ctx-item" @click="ctxAction('closeOthers')">关闭其它</div>
        <div class="ctx-item" @click="ctxAction('closeAll')">关闭全部</div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Close, ArrowDown, ArrowLeft, ArrowRight, Refresh, Grid,
} from '@element-plus/icons-vue'
import * as ElementPlusIcons from '@element-plus/icons-vue'
import { useTabsStore } from '@/stores/tabs'

const route = useRoute()
const router = useRouter()
const tabsStore = useTabsStore()

const scrollRef = ref(null)
const ctxMenu = ref({ visible: false, x: 0, y: 0, tab: null })
const showScrollLeft = ref(false)
const showScrollRight = ref(false)

// 图标名 → 组件（支持 Element Plus 图标字符串）
const iconCache = {}
const iconOf = (tab) => {
  const name = tab.icon || tab.metaIcon
  if (!name) return null
  if (iconCache[name]) return iconCache[name]
  iconCache[name] = ElementPlusIcons[name] || null
  return iconCache[name]
}

const isActive = (tab) => {
  return route.path === tab.path || (tab.affix && route.path === '/dashboard')
}

const go = (tab) => {
  if (route.path === tab.path) return
  router.push(tab.fullPath || tab.path)
}

// 双击关闭（固定标签除外）
const dblClickTab = (tab) => {
  if (tab.affix) return
  close(tab)
}

const close = (tab) => {
  const target = tabsStore.removeTab(tab.path)
  if (target && route.path === tab.path) {
    router.push(target)
  }
  nextTick(updateScrollButtons)
}

// ---------- 滚动控制 ----------
const updateScrollButtons = () => {
  const el = scrollRef.value
  if (!el) return
  showScrollLeft.value = el.scrollLeft > 5
  showScrollRight.value = el.scrollLeft < el.scrollWidth - el.clientWidth - 5
}

const scrollBy = (dir) => {
  const el = scrollRef.value
  if (!el) return
  el.scrollBy({ left: dir * 200, behavior: 'smooth' })
}

// 激活标签自动滚动到可视区域
const scrollToActive = () => {
  const el = scrollRef.value
  if (!el) return
  const active = el.querySelector('.tag-item.active')
  if (!active) return
  const elRect = el.getBoundingClientRect()
  const actRect = active.getBoundingClientRect()
  if (actRect.left < elRect.left) {
    el.scrollBy({ left: actRect.left - elRect.left - 8, behavior: 'smooth' })
  } else if (actRect.right > elRect.right) {
    el.scrollBy({ left: actRect.right - elRect.right + 8, behavior: 'smooth' })
  }
}

const refreshActive = () => {
  const cur = tabsStore.tabList.find((t) => isActive(t))
  if (cur) {
    tabsStore.refresh(cur.path)
  }
}

// ---------- 上下文菜单 ----------
const openContext = (tab, e) => {
  ctxMenu.value = { visible: true, x: e.clientX, y: e.clientY, tab }
  const closeMenu = () => {
    ctxMenu.value.visible = false
    document.removeEventListener('click', closeMenu)
  }
  document.addEventListener('click', closeMenu)
}

const ctxAction = (action) => {
  const tab = ctxMenu.value.tab
  ctxMenu.value.visible = false
  if (!tab) return
  if (action === 'refresh') {
    tabsStore.refresh(tab.path)
  } else if (action === 'close') {
    close(tab)
  } else if (action === 'closeLeft') {
    tabsStore.closeLeft(tab.path)
  } else if (action === 'closeRight') {
    tabsStore.closeRight(tab.path)
  } else if (action === 'closeOthers') {
    tabsStore.closeOthers(tab.path)
  } else if (action === 'closeAll') {
    const target = tabsStore.closeAll()
    router.push(target)
  }
}

const onCommand = (cmd) => {
  if (cmd.startsWith('go:')) {
    const path = cmd.slice(3)
    const tab = tabsStore.tabList.find((t) => t.path === path)
    if (tab) go(tab)
    return
  }
  const cur = tabsStore.tabList.find((t) => isActive(t))
  if (cmd === 'closeOthers' && cur) {
    tabsStore.closeOthers(cur.path)
  } else if (cmd === 'closeAll') {
    const target = tabsStore.closeAll()
    router.push(target)
  } else if (cmd === 'closeLeft' && cur) {
    tabsStore.closeLeft(cur.path)
  } else if (cmd === 'closeRight' && cur) {
    tabsStore.closeRight(cur.path)
  }
  nextTick(updateScrollButtons)
}

onMounted(() => {
  tabsStore.addTab(route)
  nextTick(() => {
    updateScrollButtons()
    scrollToActive()
  })
})

// 监听路由变化：更新滚动按钮、自动滚动激活标签
watch(
  () => route.fullPath,
  () => {
    nextTick(() => {
      updateScrollButtons()
      scrollToActive()
    })
  }
)
</script>

<style scoped>
.tag-bar {
  display: flex;
  align-items: center;
  height: 36px;
  background: var(--app-header-bg);
  border-bottom: 1px solid var(--app-header-border);
  padding: 0 6px;
  overflow: hidden;
  gap: 2px;
}
.tag-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}
.tag-more {
  font-size: 14px;
  color: #606266;
  padding: 4px;
}
.tag-scroll-btn {
  flex-shrink: 0;
  width: 20px;
  height: 24px;
  border: 1px solid var(--app-header-border);
  background: transparent;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #606266;
  transition: all .2s;
  padding: 0;
}
.tag-scroll-btn:hover {
  color: #409eff;
  border-color: #409eff;
  background: #ecf5ff;
}
.tag-scroll {
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  display: flex;
  align-items: center;
  scrollbar-width: none;
  min-width: 0;
}
.tag-scroll::-webkit-scrollbar { display: none; }
.tag-list {
  display: flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
  padding: 4px 2px;
}
.tag-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 26px;
  padding: 0 6px 0 10px;
  border-radius: 5px;
  border: 1px solid var(--app-header-border);
  background: transparent;
  color: #606266;
  font-size: 12px;
  cursor: pointer;
  transition: all .2s;
  user-select: none;
  position: relative;
}
.tag-item:hover {
  border-color: #409eff;
  color: #409eff;
  background: #f5f7fa;
}
.tag-item.active {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
  box-shadow: 0 2px 6px rgba(64, 158, 255, .3);
}
.tag-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  border-radius: 5px 0 0 5px;
  background: #ffd04b;
}
.tag-icon {
  flex-shrink: 0;
}
.tag-title { max-width: 110px; overflow: hidden; text-overflow: ellipsis; }
.tag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ffd04b;
  margin-left: 2px;
}
.tag-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  transition: all .2s;
  opacity: 0;
  flex-shrink: 0;
}
.tag-item:hover .tag-close,
.tag-item.active .tag-close {
  opacity: 1;
}
.tag-close:hover {
  background: rgba(255, 255, 255, .35);
  color: #f56c6c;
}
.tag-tools {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 2px;
  border-left: 1px solid var(--app-header-border);
  padding-left: 4px;
  margin-left: 2px;
}
.tag-tool-btn {
  font-size: 13px;
  color: #606266;
  padding: 4px;
}
.tag-tool-btn:hover {
  color: #409eff;
}
.ctx-menu {
  position: fixed;
  z-index: 3000;
  min-width: 120px;
  background: var(--app-header-bg);
  border: 1px solid var(--app-header-border);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, .12);
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
.tabs-list-menu {
  max-height: 60vh;
  overflow-y: auto;
}
.tabs-active {
  background: #ecf5ff !important;
  color: #409eff;
}
.tabs-list-icon {
  margin-right: 6px;
}
.tabs-list-title {
  flex: 1;
}
.tabs-list-close {
  margin-left: 10px;
  border-radius: 50%;
  transition: background .2s;
}
.tabs-list-close:hover {
  background: #f56c6c;
  color: #fff;
}
</style>
