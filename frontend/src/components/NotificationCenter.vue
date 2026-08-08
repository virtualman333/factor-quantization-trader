<template>
  <el-drawer
    v-model="localVisible"
    title="消息中心"
    direction="rtl"
    size="420px"
    :append-to-body="true"
    destroy-on-close
    @open="onOpen"
  >
    <template #header>
      <div class="drawer-header">
        <span>消息中心</span>
        <el-badge
          v-if="store.totalUnread"
          :value="store.totalUnread"
          class="unread-badge"
          type="danger"
        />
      </div>
    </template>

    <!-- 筛选与操作条 -->
    <div class="toolbar">
      <el-checkbox v-model="store.filter.unread_only">只看未读</el-checkbox>
      <el-select
        v-model="store.filter.type"
        placeholder="全部类型"
        style="width:140px"
        clearable
        @change="store.fetchList()"
      >
        <el-option v-for="o in TYPE_OPTIONS" :key="o.v" :label="o.label" :value="o.v" />
      </el-select>
      <div class="spacer" />
      <el-button size="small" @click="onRefresh" :loading="store.loading">
        <el-icon><Refresh /></el-icon>
      </el-button>
      <el-button size="small" type="primary" :disabled="!store.totalUnread" @click="onMarkAll">
        全部已读
      </el-button>
      <el-button size="small" type="danger" plain :disabled="!store.list.length" @click="onClearAll">
        清空
      </el-button>
    </div>

    <!-- 类型汇总条 -->
    <div class="summary-bar" v-if="Object.keys(store.summary.by_type || {}).length">
      <el-tag
        v-for="n in TYPE_OPTIONS"
        :key="n.v"
        class="sum-chip"
        :effect="store.filter.type === n.v ? 'dark' : 'plain'"
        :type="(store.summary.by_level && store.summary.by_type[n.v]) ? 'primary' : 'info'"
        @click="store.filter.type = store.filter.type === n.v ? '' : n.v; store.fetchList()"
        style="cursor:pointer"
      >
        {{ n.label }}
        <el-badge
          v-if="store.summary.by_type[n.v]"
          is-dot
          style="margin-left:4px"
        />
        {{ store.summary.by_type[n.v] || 0 }}
      </el-tag>
    </div>

    <el-divider style="margin:8px 0 12px" />

    <!-- 列表 -->
    <div v-loading="store.loading" class="list-wrap">
      <el-empty v-if="!store.list.length && !store.loading" description="暂无消息" />
      <TransitionGroup name="list-fade" tag="div" class="list-inner">
        <div
          v-for="item in store.list"
          :key="item.id"
          class="notify-card"
          :class="{ unread: !item.read }"
          @click="onCardClick(item)"
        >
          <div class="card-icon">
            <el-icon :size="18">
              <component :is="store.iconFor(item)" />
            </el-icon>
          </div>
          <div class="card-body">
            <div class="card-head">
              <span class="title">{{ item.title }}</span>
              <el-tag size="small" :type="store.levelType(item)" effect="light">
                {{ item.type_display }}
              </el-tag>
            </div>
            <div class="content" v-if="item.content">{{ item.content }}</div>
            <div class="meta">
              <span>{{ formatDateTime(item.created_at) }}</span>
              <span v-if="!item.read" class="unread-dot">• 未读</span>
              <div class="actions" @click.stop>
                <el-button
                  v-if="!item.read" size="small" text type="primary"
                  @click="store.markRead(item)"
                >标为已读</el-button>
                <el-button
                  v-if="item.target_route" size="small" text type="primary"
                  @click="goTarget(item.target_route)"
                >前往</el-button>
                <el-popconfirm
                  title="删除这条消息？"
                  confirm-button-text="删除"
                  cancel-button-text="取消"
                  @confirm="store.remove(item.id)"
                >
                  <template #reference>
                    <el-button size="small" text type="danger">删除</el-button>
                  </template>
                </el-popconfirm>
              </div>
            </div>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, watch, defineAsyncComponent } from 'vue'
import { Refresh, Bell, List, TrendCharts, Warning, SetUp, DataAnalysis, Coin,
         InfoFilled, CircleCheckFilled, WarningFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import { useNotificationStore } from '@/stores/notifications'
import { formatDateTime } from '@/utils/time'
import { useRouter } from 'vue-router'

const props = defineProps({ visible: Boolean })
const emit = defineEmits(['update:visible'])
const router = useRouter()
const store = useNotificationStore()

const localVisible = computed({
  get: () => props.visible,
  set: v => emit('update:visible', v),
})

const TYPE_OPTIONS = [
  { v: 'order_state', label: '订单更新' },
  { v: 'signal_generated', label: '策略信号' },
  { v: 'risk_warning', label: '风控告警' },
  { v: 'strategy_event', label: '策略事件' },
  { v: 'backtest_done', label: '回测完成' },
  { v: 'system_notice', label: '系统公告' },
  { v: 'market_alert', label: '行情异动' },
]

function onOpen() {
  store.refreshAll().catch(() => {})
}
function onRefresh() { store.refreshAll().catch(() => {}) }
async function onMarkAll() {
  await store.markAllRead()
}
async function onClearAll() {
  await store.clearAll()
}
async function onCardClick(item) {
  if (!item.read) await store.markRead(item)
  if (item.target_route) goTarget(item.target_route)
}
function goTarget(route) {
  if (!route) return
  try {
    // route 支持 ?tab=normal&detail=5 这种，转成 path+query
    if (route.startsWith('/')) {
      const [path, qs = ''] = route.split('?')
      const query = {}
      qs.split('&').filter(Boolean).forEach(kv => {
        const [k, v = ''] = kv.split('=')
        if (k) query[decodeURIComponent(k)] = decodeURIComponent(v)
      })
      router.push({ path, query })
    } else {
      router.push(route)
    }
    emit('update:visible', false)
  } catch (err) { console.warn(err) }
}

// 未读筛选变化时刷新列表
watch(() => store.filter.unread_only, () => {
  store.fetchList().catch(() => {})
})
</script>

<style scoped>
.drawer-header { display: flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 600; }
.unread-badge { margin-left: 4px; }
.toolbar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-bottom: 8px;
}
.toolbar .spacer { flex: 1; }
.summary-bar {
  display: flex; gap: 6px; flex-wrap: wrap; align-items: center;
}
.sum-chip { }
.list-wrap { min-height: 300px; }
.list-inner { display: flex; flex-direction: column; gap: 10px; }

.notify-card {
  display: flex;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 8px;
  transition: box-shadow .2s, transform .2s, background .2s;
  cursor: pointer;
  background: var(--el-bg-color, #fff);
}
.notify-card:hover { box-shadow: 0 2px 10px rgba(0,0,0,.05); }
.notify-card.unread {
  background: linear-gradient(90deg, rgba(64,158,255,.06) 0%, transparent 50%);
  border-color: rgba(64,158,255,.25);
}
.card-icon {
  width: 34px; height: 34px; border-radius: 50%;
  background: var(--el-color-primary-light-9, #ecf5ff);
  color: var(--el-color-primary, #409eff);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.notify-card.unread .card-icon { background: var(--el-color-primary, #409eff); color: #fff; }
.card-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.card-head {
  display: flex; justify-content: space-between; align-items: center; gap: 8px;
}
.card-head .title { font-weight: 600; font-size: 14px; }
.content {
  color: var(--el-text-color-regular, #606266);
  font-size: 13px;
  white-space: pre-wrap;
  line-height: 1.5;
}
.meta {
  color: var(--el-text-color-secondary, #909399);
  font-size: 12px;
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin-top: 4px;
}
.meta .unread-dot { color: #409eff; font-weight: 600; }
.meta .actions { margin-left: auto; display: flex; gap: 4px; }

.list-fade-enter-active, .list-fade-leave-active { transition: all .25s ease; }
.list-fade-enter-from { opacity: 0; transform: translateY(-6px); }
.list-fade-leave-to { opacity: 0; transform: translateX(30px); }
</style>
