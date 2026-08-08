<template>
  <el-container class="layout">
    <!-- 移动端遮罩层 -->
    <transition name="fade">
      <div v-if="isMobile && !isCollapse" class="aside-mask" @click="isCollapse = true" />
    </transition>

    <el-aside
      :width="isCollapse ? '64px' : '220px'"
      class="aside"
      :class="{ 'aside-mobile-drawer': isMobile, 'aside-mobile-hidden': isMobile && isCollapse }"
    >
      <div class="logo" @click="$router.push('/dashboard'); isMobile && (isCollapse = true)">
        <el-icon :size="24"><TrendCharts /></el-icon>
        <span v-show="!isCollapse" class="logo-text">量化交易系统</span>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="isCollapse"
        router
        background-color="#1d1e2c"
        text-color="#a6a9b6"
        active-text-color="#409eff"
        @select="onMenuSelect"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>

        <el-sub-menu index="market">
          <template #title>
            <el-icon><Coin /></el-icon>
            <span>行情数据</span>
          </template>
          <el-menu-item index="/market/instruments">交易品种</el-menu-item>
          <el-menu-item index="/market/klines">K线数据</el-menu-item>
          <el-menu-item index="/market/tickers">实时行情</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="account">
          <template #title>
            <el-icon><Wallet /></el-icon>
            <span>账户管理</span>
          </template>
          <el-menu-item index="/account/balances">账户余额</el-menu-item>
          <el-menu-item index="/account/positions">持仓管理</el-menu-item>
          <el-menu-item index="/account/netvalue">净值曲线</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="strategy">
          <template #title>
            <el-icon><SetUp /></el-icon>
            <span>策略引擎</span>
          </template>
          <el-menu-item index="/strategy/list">策略管理</el-menu-item>
          <el-menu-item index="/strategy/factors">因子定义</el-menu-item>
          <el-menu-item index="/strategy/signals">交易信号</el-menu-item>
          <el-menu-item index="/strategy/backtests">回测结果</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="orders">
          <template #title>
            <el-icon><List /></el-icon>
            <span>订单管理</span>
          </template>
          <el-menu-item index="/orders/list">订单列表</el-menu-item>
          <el-menu-item index="/orders/create">创建订单</el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
        <el-menu-item index="/profile">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </el-menu-item>
        <el-menu-item v-if="authStore.isAdmin" index="/admin">
          <el-icon><Setting /></el-icon>
          <span>系统管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <el-button
          :icon="isMobile ? Expand : Fold"
          text
          @click="isCollapse = !isCollapse"
          class="collapse-btn"
        />
        <span class="title">{{ route.meta.title || '' }}</span>
        <div class="header-right">
          <!-- 消息铃铛 -->
          <el-tooltip content="消息中心（Ctrl+N）" placement="bottom">
            <el-badge :value="notifyStore.totalUnread || undefined" :hidden="!notifyStore.totalUnread" class="bell-badge">
              <el-button size="small" circle @click="drawerVisible = !drawerVisible">
                <el-icon><Bell /></el-icon>
              </el-button>
            </el-badge>
          </el-tooltip>

          <el-tooltip :content="theme.isDark ? '切换到浅色模式' : '切换到深色模式'" placement="bottom">
            <el-button :icon="theme.isDark ? Sunny : Moon" circle @click="theme.toggle" />
          </el-tooltip>
          <el-dropdown @command="handleEnvCommand" :disabled="connectionStore.loading">
            <el-button size="small" :type="connectionStore.environment === 'live' ? 'danger' : 'primary'">
              {{ connectionStore.envLabel }}
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="demo" :disabled="connectionStore.environment === 'demo'">
                  模拟盘
                </el-dropdown-item>
                <el-dropdown-item command="live" :disabled="connectionStore.environment === 'live'">
                  实盘
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-tooltip :content="realtimeStore.error || '实时行情通道（点击重连）'" placement="bottom">
            <el-tag
              size="small"
              :type="realtimeStore.statusType"
              class="status-tag desktop-only"
              @click="realtimeStore.reconnect"
              :style="{ cursor: 'pointer' }"
            >
              <el-icon :size="12" :class="{ 'is-loading': realtimeStore.status === 'connecting' }">
                <Connection />
              </el-icon>
              {{ realtimeStore.statusText }}
            </el-tag>
          </el-tooltip>

          <el-tooltip :content="connectionStore.lastError || '点击检测连接'" placement="bottom">
            <el-tag
              size="small"
              :type="connectionStore.statusType"
              class="status-tag desktop-only"
              @click="refreshConnection"
              :style="{ cursor: 'pointer' }"
            >
              <el-icon v-if="connectionStore.loading" class="is-loading"><Loading /></el-icon>
              <el-icon v-else-if="connectionStore.connected" :size="12"><CircleCheck /></el-icon>
              <el-icon v-else :size="12"><CircleClose /></el-icon>
              {{ connectionStore.statusText }}
            </el-tag>
          </el-tooltip>

          <!-- 深色模式切换 -->
          <el-tooltip :content="theme.isDark.value ? '切换到浅色模式' : '切换到深色模式'" placement="bottom">
            <el-button size="small" circle @click="theme.toggle">
              <el-icon><Sunny v-if="theme.isDark.value" /><Moon v-else /></el-icon>
            </el-button>
          </el-tooltip>

          <!-- 快捷键帮助 -->
          <el-tooltip content="使用帮助与快捷键（?）" placement="bottom">
            <el-button size="small" circle @click="shortcutHelp?.open()">
              <el-icon><QuestionFilled /></el-icon>
            </el-button>
          </el-tooltip>

          <el-dropdown @command="handleUserCommand">
            <el-button size="small" type="default" circle>
              <el-icon><User /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  <span class="user-name">{{ authStore.user?.username || '--' }}</span>
                </el-dropdown-item>
                <el-dropdown-item v-if="authStore.isAdmin" command="admin" divided>
                  <el-icon><Setting /></el-icon>
                  切换管理端
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
  <NotificationCenter v-model="drawerVisible" />
</template>

<script setup>
import { ref, onMounted, onUnmounted, inject, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Fold, Expand, ArrowDown, Loading, CircleCheck, CircleClose,
  Connection, User, Sunny, Moon, QuestionFilled, Bell,
} from '@element-plus/icons-vue'
import { useConnectionStore } from '@/stores/connection.js'
import { useRealtimeStore } from '@/stores/realtime.js'
import { useAuthStore } from '@/stores/auth.js'
import { useNotificationStore } from '@/stores/notifications.js'
import NotificationCenter from '@/components/NotificationCenter.vue'
import { useTheme } from '@/composables/useTheme.js'
import { useKeyboard } from '@/composables/useKeyboard.js'
import { useConfirm } from '@/composables/useConfirm.js'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const connectionStore = useConnectionStore()
const realtimeStore = useRealtimeStore()
const authStore = useAuthStore()
const notifyStore = useNotificationStore()
const theme = useTheme()
const { confirm } = useConfirm()
const { registerShortcut } = useKeyboard()

const drawerVisible = ref(false)

// 响应式断点
const isMobile = ref(window.innerWidth <= 768)
const isCollapse = ref(isMobile.value)

const shortcutHelp = inject('shortcutHelp', null)

let pollTimer = null
let resizeHandler = null

function onResize() {
  const wasMobile = isMobile.value
  isMobile.value = window.innerWidth <= 768
  // 从移动端切到桌面端：自动展开侧边栏
  if (!isMobile.value && wasMobile) isCollapse.value = false
  // 从桌面端切到移动端：自动折叠
  if (isMobile.value && !wasMobile) isCollapse.value = true
}

async function handleEnvCommand(env) {
  // 切换到实盘需二次确认
  if (env === 'live' && connectionStore.environment !== 'live') {
    const ok = await confirm.switchLive()
    if (!ok) return
  }
  await connectionStore.switchEnv(env)
}

async function refreshConnection() {
  await connectionStore.checkConnection().catch(() => {})
}

function handleUserCommand(command) {
  if (command === 'admin') {
    router.push('/admin')
  } else if (command === 'logout') {
    authStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}

// 移动端选择菜单后自动收起侧边栏
function onMenuSelect() {
  if (isMobile.value) isCollapse.value = true
}

// ===== 全局快捷键 =====
registerShortcut({
  key: 'b', ctrl: true, description: '折叠/展开侧边栏',
  handler: () => { isCollapse.value = !isCollapse.value },
})
registerShortcut({
  key: 'd', ctrl: true, description: '切换深色/浅色模式',
  handler: () => theme.toggle(),
})
registerShortcut({
  key: '/', description: '快捷键说明',
  handler: () => shortcutHelp?.open(),
})
// 兼容 ? 键（Shift+/）
registerShortcut({
  key: '?', shift: true, description: '快捷键说明',
  handler: () => shortcutHelp?.open(),
})
registerShortcut({
  key: 'n', ctrl: true, description: '打开消息中心',
  handler: () => { drawerVisible.value = !drawerVisible.value },
})

// 路由切换时，移动端自动收起侧边栏
watch(() => route.path, () => {
  if (isMobile.value) isCollapse.value = true
})

onMounted(async () => {
  window.addEventListener('resize', onResize)
  resizeHandler = onResize
  await connectionStore.init()
  realtimeStore.ensureOpen()
  // 通知系统：启动轮询（每 30s 刷新 summary + list，检测到新消息自动 toast）
  notifyStore.startPolling()
  pollTimer = setInterval(() => {
    connectionStore.checkConnection().catch(() => {})
  }, 30000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  notifyStore.stopPolling()
  realtimeStore.close()
})
</script>

<style scoped>
.layout { height: 100vh; }
.aside {
  background: #1d1e2c;
  overflow: hidden;
  transition: width 0.3s, transform 0.3s;
  display: flex;
  flex-direction: column;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  color: #fff;
  cursor: pointer;
  font-size: 16px;
  font-weight: bold;
  flex-shrink: 0;
}
.logo-text { white-space: nowrap; }
/* 菜单区域占满剩余高度，超出时可滚动 */
.aside :deep(.el-menu) {
  border-right: none;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}
.aside :deep(.el-menu::-webkit-scrollbar) { width: 4px; }
.aside :deep(.el-menu::-webkit-scrollbar-thumb) {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
}
.aside :deep(.el-menu::-webkit-scrollbar-track) { background: transparent; }

/* 移动端抽屉式侧边栏 */
@media (max-width: 768px) {
  .aside-mobile-drawer {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 2001;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.3);
  }
  .aside-mobile-hidden {
    transform: translateX(-100%);
    width: 220px !important;
  }
  .aside-mask {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 2000;
  }
}

.header {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--app-header-bg);
  border-bottom: 1px solid var(--app-header-border);
  padding: 0 20px;
  height: 56px;
}
.collapse-btn { font-size: 20px; }
.title { font-size: 18px; font-weight: 600; }
.header-right { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.status-tag { display: flex; align-items: center; gap: 4px; }
.user-name { color: #606266; }
.main { background: var(--app-bg); padding: 20px; overflow-y: auto; }

/* 移动端 header 紧凑化 */
@media (max-width: 768px) {
  .header { padding: 0 12px; gap: 8px; }
  .title { font-size: 16px; }
  .main { padding: 12px; }
  .header-right { gap: 6px; }
}
</style>
