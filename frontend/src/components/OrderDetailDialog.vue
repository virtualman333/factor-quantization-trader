<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="订单详情"
    width="640px"
    destroy-on-close
    @open="onOpen"
  >
    <template v-if="order">
      <!-- 关键指标卡片 -->
      <el-row :gutter="12" style="margin-bottom:16px">
        <el-col :span="6">
          <el-card shadow="never" class="kpi-card">
            <div class="kpi-label">状态</div>
            <el-tag
              class="kpi-value"
              :type="order.state === 'filled' ? 'success' : order.state === 'live' ? 'warning' : order.state === 'canceled' ? 'info' : 'danger'"
              size="large"
            >{{ order.state_display }}</el-tag>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="kpi-card">
            <div class="kpi-label">盈亏 (估)</div>
            <div class="kpi-value" :style="{ color: pnlColor }">{{ pnlText }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="kpi-card">
            <div class="kpi-label">成交率</div>
            <div class="kpi-value">{{ fillRateText }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="kpi-card">
            <div class="kpi-label">手续费</div>
            <div class="kpi-value" style="color:#f56c6c">
              {{ order.fee || order.fee === 0 ? `${order.fee}` : '--' }}
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-tabs v-model="tab">
        <el-tab-pane label="完整属性" name="attrs">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="订单ID (本地)">
              <span class="mono">#{{ order.id }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="交易所单号 (ordId)">
              <span v-if="order.ord_id" class="mono">{{ order.ord_id }}</span>
              <span v-else class="text-muted">未提交成功</span>
            </el-descriptions-item>
            <el-descriptions-item label="品种">{{ order.inst_id }}</el-descriptions-item>
            <el-descriptions-item label="方向">
              <el-tag :type="order.side === 'buy' ? 'success' : 'danger'" size="small">
                {{ order.side_display || (order.side === 'buy' ? '买入' : '卖出') }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="订单类型">
              {{ order.ord_type_display }} <term-tip term-key="ord_type" />
            </el-descriptions-item>
            <el-descriptions-item label="保证金模式">{{ tdModeDisplay }}</el-descriptions-item>
            <el-descriptions-item label="委托数量">
              {{ order.sz }}
              <span v-if="order.leverage"> ({{ order.leverage }}x 杠杆)</span>
            </el-descriptions-item>
            <el-descriptions-item label="委托价">
              {{ order.px || (order.ord_type === 'market' ? '市价' : '--') }}
            </el-descriptions-item>
            <el-descriptions-item label="已成交数量">{{ order.fill_sz || '0' }}</el-descriptions-item>
            <el-descriptions-item label="成交均价">{{ order.fill_px || '--' }}</el-descriptions-item>
            <el-descriptions-item label="来源">
              <source-tag :source="order.source" />
            </el-descriptions-item>
            <el-descriptions-item label="关联策略 / 信号">
              <div v-if="order.strategy_id">策略 ID: {{ order.strategy_id }}</div>
              <div v-if="order.signal_id">信号 ID: {{ order.signal_id }}</div>
              <span v-else class="text-muted">--</span>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间" :span="2">{{ order.created_at }}</el-descriptions-item>
            <el-descriptions-item label="更新时间" :span="2">{{ order.updated_at || '--' }}</el-descriptions-item>
            <el-descriptions-item v-if="order.error_msg" label="错误信息" :span="2">
              <el-alert type="error" :closable="false" show-icon :title="order.error_msg" />
            </el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <el-tab-pane label="操作时间线" name="timeline">
          <el-timeline v-if="logs.length" style="padding-top:8px">
            <el-timeline-item
              v-for="(l, idx) in logs"
              :key="l.id || idx"
              :timestamp="l.created_at"
              :type="logType(l.action)"
              :hollow="logType(l.action) === 'info'"
            >
              <h4 style="margin:0 0 6px">
                <el-tag size="small" :type="logType(l.action)">{{ actionLabel(l.action) }}</el-tag>
              </h4>
              <p v-if="l.message" class="log-msg">{{ l.message }}</p>
              <div v-if="l.before || l.after" class="log-diff">
                <div v-if="l.before" class="diff-block">
                  <div class="diff-label">变更前</div>
                  <pre>{{ pretty(l.before) }}</pre>
                </div>
                <div v-if="l.after" class="diff-block">
                  <div class="diff-label">变更后</div>
                  <pre>{{ pretty(l.after) }}</pre>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无操作日志" :image-size="60" />
        </el-tab-pane>
      </el-tabs>
    </template>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
      <el-button type="primary" :loading="syncing" @click="onSync">从 OKX 同步最新状态</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, defineAsyncComponent, shallowRef } from 'vue'
import { ElMessage } from 'element-plus'
import { syncOrder } from '@/api/orders'
import { getOrderLogs } from '@/api/orders'

const SourceTag = defineAsyncComponent(() => import('@/components/SourceTag.vue'))

const props = defineProps({
  visible: { type: Boolean, default: false },
  order: { type: Object, default: null },
})

const emit = defineEmits(['update:visible', 'refreshed'])

const tab = ref('attrs')
const logs = ref([])
const syncing = ref(false)

function tdModeDisplay() {
  return { cash: '现金/现货', cross: '全仓合约', isolated: '逐仓合约' }[props.order?.td_mode] || props.order?.td_mode || '--'
}

const fillRateText = computed(() => {
  const sz = parseFloat(props.order?.sz || 0)
  const fill = parseFloat(props.order?.fill_sz || 0)
  if (!sz) return '--'
  const pct = Math.min(100, (fill / sz) * 100)
  return `${pct.toFixed(1)}% (${fill} / ${sz})`
})

// 简易盈亏估算：做多 = (成交均价-开仓价)*数量；做空反向。若订单有 upl 字段直接用。
const pnlText = computed(() => {
  const o = props.order
  if (!o) return '--'
  if (o.upl || o.upl === 0) return `${o.upl}`
  if (o.state !== 'filled') return '--'
  const side = o.side
  const sz = parseFloat(o.fill_sz || o.sz || 0)
  const px = parseFloat(o.fill_px || o.px || 0)
  const entry = parseFloat(o.px || 0)
  if (!sz || !px || !entry) return '--'
  const raw = (side === 'buy' ? (px - entry) : (entry - px)) * sz
  return raw.toFixed(Math.abs(raw) >= 1 ? 2 : 6)
})
const pnlColor = computed(() => {
  const t = String(pnlText.value)
  if (t === '--') return '#909399'
  const n = parseFloat(t)
  if (Number.isNaN(n)) return '#909399'
  return n >= 0 ? '#67c23a' : '#f56c6c'
})

function actionLabel(a) {
  return {
    created: '创建订单', submitted: '提交到交易所', synced: '状态同步',
    filled: '成交', canceled: '撤销', rejected: '被拒绝', risk_check: '风控检查',
    updated: '修改订单',
  }[a] || a || '--'
}
function logType(a) {
  if (['filled'].includes(a)) return 'success'
  if (['rejected', 'canceled'].includes(a)) return 'danger'
  if (['submitted', 'synced'].includes(a)) return 'primary'
  if (['risk_check'].includes(a)) return 'warning'
  return 'info'
}
function pretty(v) {
  try {
    if (typeof v === 'string') return JSON.stringify(JSON.parse(v), null, 2)
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

async function loadLogs() {
  if (!props.order?.id) { logs.value = []; return }
  try {
    const res = await getOrderLogs({ order: props.order.id, page_size: 100 })
    const list = res.results || res || []
    logs.value = list.sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0))
  } catch { logs.value = [] }
}

async function onSync() {
  if (!props.order?.id) return
  syncing.value = true
  try {
    await syncOrder(props.order.id)
    ElMessage.success('同步完成')
    emit('refreshed')
    await loadLogs()
  } catch (e) { ElMessage.error(e.message) }
  syncing.value = false
}

function onOpen() {
  tab.value = 'attrs'
  loadLogs()
}

watch(() => props.order, loadLogs)
</script>

<style scoped>
.kpi-card { text-align: center; border-radius: 6px; }
.kpi-card :deep(.el-card__body) { padding: 14px 10px; }
.kpi-label { font-size: 12px; color: #909399; margin-bottom: 6px; }
.kpi-value { font-size: 16px; font-weight: 600; word-break: break-all; }
.mono { font-family: Consolas, monospace; color: #303133; }
.text-muted { color: #909399; }
.log-msg { margin: 0; color: #606266; }
.log-diff { display: flex; gap: 12px; margin-top: 8px; flex-wrap: wrap; }
.diff-block { flex: 1 1 45%; min-width: 240px; border: 1px solid #ebeef5; border-radius: 4px; padding: 8px 10px; background: #fafafa; }
.diff-label { font-size: 11px; color: #909399; margin-bottom: 4px; }
.diff-block pre { margin: 0; white-space: pre-wrap; word-break: break-all; font-size: 12px; line-height: 1.5; color: #303133; }
</style>
