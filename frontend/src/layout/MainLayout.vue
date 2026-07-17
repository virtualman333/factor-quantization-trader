<template>
  <el-container class="layout">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
      <div class="logo" @click="$router.push('/dashboard')">
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
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <el-button :icon="Fold" text @click="isCollapse = !isCollapse" class="collapse-btn" />
        <span class="title">{{ route.meta.title || '' }}</span>
        <div class="header-right">
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

          <el-tooltip :content="connectionStore.lastError || '点击检测连接'" placement="bottom">
            <el-tag
              size="small"
              :type="connectionStore.statusType"
              class="status-tag"
              @click="refreshConnection"
              :style="{ cursor: 'pointer' }"
            >
              <el-icon v-if="connectionStore.loading" class="is-loading"><Loading /></el-icon>
              <el-icon v-else-if="connectionStore.connected" :size="12"><CircleCheck /></el-icon>
              <el-icon v-else :size="12"><CircleClose /></el-icon>
              {{ connectionStore.statusText }}
            </el-tag>
          </el-tooltip>

        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { Fold, ArrowDown, Loading, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { useConnectionStore } from '@/stores/connection.js'

const route = useRoute()
const connectionStore = useConnectionStore()
const isCollapse = ref(false)
let pollTimer = null

async function handleEnvCommand(env) {
  await connectionStore.switchEnv(env)
}

async function refreshConnection() {
  await connectionStore.checkConnection().catch(() => {})
}

onMounted(async () => {
  await connectionStore.init()
  pollTimer = setInterval(() => {
    connectionStore.checkConnection().catch(() => {})
  }, 30000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #1d1e2c; overflow: hidden; transition: width 0.3s; }
.logo { display: flex; align-items: center; gap: 10px; padding: 16px 20px; color: #fff; cursor: pointer; font-size: 16px; font-weight: bold; }
.logo-text { white-space: nowrap; }
.header { display: flex; align-items: center; gap: 16px; background: #fff; border-bottom: 1px solid #e4e7ed; padding: 0 20px; height: 56px; }
.collapse-btn { font-size: 20px; }
.title { font-size: 18px; font-weight: 600; }
.header-right { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.status-tag { display: flex; align-items: center; gap: 4px; }
.main { background: #f5f7fa; padding: 20px; overflow-y: auto; }
.el-menu { border-right: none; }
</style>
