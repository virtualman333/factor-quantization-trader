<template>
  <div>
    <div class="page-header">
      <h2>
        账户余额
        <term-tip term-key="balance_vs_live" icon>
          <b>快照余额</b>：本地 BalanceSnapshot 表的历史快照（可回溯、用于净值曲线）；
          <b>实时余额</b>：直接从 OKX 拉取当前最新余额（用于下单前核对）。两者差额过大请检查是否有未同步的出入金或挂单。
        </term-tip>
      </h2>
      <div>
        <el-switch
          v-model="autoRefresh"
          active-text="自动刷新"
          inactive-text=""
          style="margin-right:12px"
        />
        <el-tag v-if="liveDataTime" size="small" type="success" style="margin-right:8px">
          实时更新于 {{ liveDataTime }}
        </el-tag>
        <el-tooltip content="从 BalanceSnapshot 表读取最近一次保存的快照">
          <el-button @click="loadSnapshots" :icon="DataLine" :loading="snapshotLoading">
            刷新快照
          </el-button>
        </el-tooltip>
        <el-tooltip content="保存 OKX 当前余额到本地快照表（记录净值用于后续回溯）">
          <el-button type="primary" :icon="Camera" :loading="snapshotLoading" @click="takeSnapshot">
            保存快照
          </el-button>
        </el-tooltip>
        <el-tooltip content="直接从 OKX 拉取最新实时余额（不走本地快照表）">
          <el-button type="success" :icon="Refresh" :loading="liveLoading" @click="loadLive">
            拉取实时余额
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- 新手提示 -->
    <el-alert
      type="info"
      :closable="false"
      show-icon
      style="margin:12px 0"
    >
      <template #title>
        <b>使用建议：</b>
        每次入金/出金后点击「保存快照」记录一次历史快照；
        下单前先看一次「实时余额」核对账户；
        长期观察账户净值用「净值曲线」页。
      </template>
    </el-alert>

    <!-- 顶部汇总卡：快照 vs 实时 总资产 -->
    <el-row :gutter="16" style="margin-bottom:16px" v-if="snapTotalUsd !== null || liveTotalUsd !== null">
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="sum-card">
          <div class="sum-label">快照总资产 (USD)
            <term-tip term-key="sum_snap" class="ml-1">本地快照表最新一条的 USD 估值汇总</term-tip>
          </div>
          <div class="sum-value">{{ fmtMoney(snapTotalUsd) }}</div>
          <div class="sum-sub" v-if="snapshotTime">截至：{{ snapshotTime }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="sum-card sum-card-live">
          <div class="sum-label">实时总资产 (USD)
            <term-tip term-key="sum_live" class="ml-1">OKX API 返回的最新估值</term-tip>
          </div>
          <div class="sum-value">{{ fmtMoney(liveTotalUsd) }}</div>
          <div class="sum-sub" v-if="liveDataTime">更新：{{ liveDataTime }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="sum-card">
          <div class="sum-label">差额 (实时 − 快照)</div>
          <div class="sum-value" :style="{ color: deltaColor }">{{ deltaText }}</div>
          <div class="sum-sub" :style="{ color: deltaColor }">{{ deltaPctText }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-table
      :data="mergedRows"
      border
      stripe
      style="width:100%"
      :row-class-name="rowClass"
    >
      <el-table-column prop="ccy" label="币种" width="90" fixed="left" />
      <!-- 快照列 -->
      <el-table-column label="快照（本地）" align="center" header-align="center">
        <template #header>
          快照（本地）
          <term-tip term-key="snapshot_cols" icon>BalanceSnapshot 保存时的快照数据，仅点击「保存快照」才会更新。</term-tip>
        </template>
        <el-table-column label="总余额" width="150" align="right">
          <template #default="{ row }">
            <span :class="!row.snap ? 'text-muted' : ''">{{ row.snap?.total_eq != null ? fmtMoney(row.snap.total_eq) : '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="可用" width="130" align="right">
          <template #default="{ row }">
            <span :class="!row.snap ? 'text-muted' : ''">{{ row.snap?.avail_eq != null ? fmtMoney(row.snap.avail_eq) : '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="冻结" width="110" align="right">
          <template #default="{ row }">
            <span :class="!row.snap ? 'text-muted' : ''">{{ row.snap?.frozen_bal != null ? fmtMoney(row.snap.frozen_bal) : '--' }}</span>
          </template>
        </el-table-column>
      </el-table-column>
      <!-- 实时列 -->
      <el-table-column label="实时（OKX）" align="center" header-align="center">
        <template #header>
          实时（OKX）
          <term-tip term-key="live_cols" icon>直接从 OKX REST API 拉取，点「拉取实时余额」刷新或开启自动刷新。</term-tip>
        </template>
        <el-table-column label="总余额" width="150" align="right">
          <template #default="{ row }">
            <el-tag
              v-if="row.hasLiveDelta"
              size="small"
              :type="liveDeltaColor(row)"
              effect="plain"
              style="margin-right:4px"
            >{{ liveDeltaPct(row) }}</el-tag>
            <b :class="row.live ? '' : 'text-muted'">{{ row.live?.total_eq != null ? fmtMoney(row.live.total_eq) : '--' }}</b>
          </template>
        </el-table-column>
        <el-table-column label="可用" width="130" align="right">
          <template #default="{ row }">
            <span :class="row.live ? '' : 'text-muted'">{{ row.live?.avail_eq != null ? fmtMoney(row.live.avail_eq) : '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="冻结" width="110" align="right">
          <template #default="{ row }">
            <span :class="row.live ? '' : 'text-muted'">{{ row.live?.frozen_bal != null ? fmtMoney(row.live.frozen_bal) : '--' }}</span>
          </template>
        </el-table-column>
      </el-table-column>
      <!-- 对比列 -->
      <el-table-column label="差额(实时-快照)" width="150" align="right">
        <template #default="{ row }">
          <span :style="{ color: row.deltaColor }">{{ row.deltaText }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="usd_value" label="USD价值" width="150" align="right">
        <template #default="{ row }">
          {{ fmtMoney(row.live?.usd_value ?? row.snap?.usd_value) }}
        </template>
      </el-table-column>
      <el-table-column label="折扣率" width="80" align="right">
        <template #default="{ row }">{{ row.live?.discount ?? row.snap?.discount ?? '--' }}</template>
      </el-table-column>
      <el-table-column label="时间对比" width="200">
        <template #default="{ row }">
          <div>快照：<span class="text-muted">{{ row.snap?.snapshot_time ?? '--' }}</span></div>
          <div>实时：<span class="text-success">{{ liveDataTime || '--' }}</span></div>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-if="snapshots.length"
        v-model:current-page="page"
        :page-size="50"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="loadSnapshots"
      />
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'Balances' })
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { Camera, Refresh, DataLine } from '@element-plus/icons-vue'
import { getBalances, saveBalanceSnapshot, getLiveBalance } from '@/api/account'
import { ElMessage } from 'element-plus'
import { nowBeijing } from '@/utils/time'

const snapshots = ref([])
const snapshotLoading = ref(false)
const page = ref(1)
const total = ref(0)
const snapshotTime = ref('')

const liveDetails = ref([])  // OKX raw details
const liveLoading = ref(false)
const liveDataTime = ref('')

// 自动刷新
const autoRefresh = ref(false)
let timer = null

// 汇总
const snapTotalUsd = computed(() => sumUsd(snapshots.value, x => x.usd_value))
const liveTotalUsd = computed(() => sumUsd(liveDetails.value, x => x.usd_value))
const deltaUsd = computed(() =>
  (liveTotalUsd.value === null || snapTotalUsd.value === null)
    ? null
    : (liveTotalUsd.value - snapTotalUsd.value)
)
const deltaText = computed(() =>
  deltaUsd.value === null ? '--' : (deltaUsd.value >= 0 ? '+' : '') + fmtMoney(deltaUsd.value)
)
const deltaColor = computed(() => {
  if (deltaUsd.value === null) return 'inherit'
  if (deltaUsd.value > 0.01) return '#67c23a'
  if (deltaUsd.value < -0.01) return '#f56c6c'
  return 'inherit'
})
const deltaPctText = computed(() => {
  if (deltaUsd.value === null || !snapTotalUsd.value || Math.abs(snapTotalUsd.value) < 0.01) return ''
  const pct = (deltaUsd.value / snapTotalUsd.value) * 100
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
})

// 合并快照与实时，按币种对齐
const mergedRows = computed(() => {
  const map = new Map()
  snapshots.value.forEach(s => {
    const ccy = (s.ccy || '').toUpperCase()
    map.set(ccy, { ccy, snap: s, live: null })
  })
  liveDetails.value.forEach(d => {
    const ccy = (d.ccy || '').toUpperCase()
    if (!map.has(ccy)) map.set(ccy, { ccy, snap: null, live: null })
    const row = map.get(ccy)
    row.live = d
  })
  const rows = Array.from(map.values())
  // 注入差额信息
  rows.forEach(r => {
    const snapEq = parseFloat(r.snap?.total_eq) || 0
    const liveEq = parseFloat(r.live?.total_eq) || 0
    const delta = r.live && r.snap ? (liveEq - snapEq) : null
    const hasDelta = r.live && r.snap && Math.abs(delta) > 0
    const pct = (r.snap && r.live && Math.abs(snapEq) > 1e-12)
      ? ((liveEq - snapEq) / Math.abs(snapEq)) * 100 : null
    r.delta = delta
    r.hasLiveDelta = hasDelta
    r.deltaColor = (delta === null) ? 'inherit' : (delta > 0 ? '#67c23a' : (delta < 0 ? '#f56c6c' : 'inherit'))
    r.deltaText = (delta === null) ? '--' : ((delta >= 0 ? '+' : '') + fmtNum(delta, snapEq))
    r._deltaPct = pct
  })
  // 排序：按 usd_value 降序
  rows.sort((a, b) => {
    const au = parseFloat(a.live?.usd_value ?? a.snap?.usd_value ?? 0)
    const bu = parseFloat(b.live?.usd_value ?? b.snap?.usd_value ?? 0)
    return bu - au
  })
  return rows
})

function rowClass({ row }) {
  if (row.live && !row.snap) return 'row-only-live'
  if (row.snap && !row.live) return 'row-only-snap'
  return ''
}

function liveDeltaColor(row) {
  if (!row.hasLiveDelta) return 'info'
  return row.delta > 0 ? 'success' : 'danger'
}
function liveDeltaPct(row) {
  const p = row._deltaPct
  if (p === null) return ''
  return `${p >= 0 ? '+' : ''}${p.toFixed(2)}%`
}

// ========= helpers =========
function sumUsd(arr, selector) {
  if (!arr || !arr.length) return null
  let s = 0, any = false
  for (const x of arr) {
    const v = parseFloat(selector(x))
    if (!Number.isNaN(v) && Number.isFinite(v)) { s += v; any = true }
  }
  return any ? s : null
}
function fmtMoney(v) {
  if (v === null || v === undefined || v === '') return '--'
  const n = Number(v)
  if (Number.isNaN(n)) return '--'
  return formatNumber(n)
}
function fmtNum(delta, ref) {
  const abs = Math.abs(Math.max(Math.abs(delta), Math.abs(ref)))
  const digits = abs >= 1 ? 2 : 6
  return formatNumber(Number(delta), digits)
}
// 统一数值格式化：极小值（<1e-6 且非0）用科学计数法，避免显示为 0
function formatNumber(n, maxDigits = 8) {
  if (n === 0) return '0'
  const abs = Math.abs(n)
  if (abs < 1e-6) {
    return n.toExponential(2)
  }
  const digits = abs >= 1 ? Math.min(maxDigits, 2) : (abs >= 0.01 ? Math.min(maxDigits, 4) : Math.min(maxDigits, 8))
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

// ========= loaders =========
async function loadSnapshots() {
  snapshotLoading.value = true
  try {
    const res = await getBalances({ page: page.value, page_size: 200 })
    snapshots.value = res.results || res
    total.value = res.count || 0
    if (snapshots.value.length) {
      snapshotTime.value = snapshots.value[0].snapshot_time || snapshots.value[0].created_at || ''
    }
  } catch (e) { ElMessage.error(e.message) }
  snapshotLoading.value = false
}

async function takeSnapshot() {
  snapshotLoading.value = true
  try {
    await saveBalanceSnapshot()
    ElMessage.success('快照已保存')
    page.value = 1
    await Promise.all([loadSnapshots(), loadLive()])
  } catch (e) { ElMessage.error(e.message) }
  snapshotLoading.value = false
}

async function loadLive() {
  liveLoading.value = true
  try {
    const res = await getLiveBalance()
    // 后端 get_balance_from_api 返回 { total_eq_usd, details, snapshot_time }
    const details = res?.details || []
    // 过滤：total_eq=0 且 avail_eq=0 的币种不展示（OKX 经常返回上百个 0 余额垃圾币）
    liveDetails.value = details.filter(d => {
      const total = parseFloat(d.total_eq) || 0
      const avail = parseFloat(d.avail_eq) || 0
      const usd = parseFloat(d.usd_value) || 0
      return Math.abs(total) > 0 || Math.abs(avail) > 0 || Math.abs(usd) > 0.01
    })
    liveDataTime.value = nowBeijing()
    ElMessage.success(`已拉取 ${liveDetails.value.length} 个币种实时余额`)
  } catch (e) { ElMessage.error(e.message) }
  liveLoading.value = false
}

// ===== auto-refresh =====
watch(autoRefresh, v => {
  if (v) {
    loadLive()
    timer = setInterval(loadLive, 15000)
    ElMessage.info('已开启 15s 自动刷新实时余额')
  } else {
    if (timer) clearInterval(timer)
    timer = null
  }
})

onMounted(async () => {
  // 默认两者同时拉取，让用户一进来就看到「快照 vs 实时」对比
  await Promise.all([loadSnapshots(), loadLive()])
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.page-header h2 { margin: 0; font-size: 18px; display: flex; align-items: center; gap: 6px; }
.ml-1 { margin-left: 4px; }
.text-muted { color: #909399; }
.text-success { color: #67c23a; }

.sum-card { border-radius: 8px; transition: transform .15s; }
.sum-card :deep(.el-card__body) { padding: 16px; }
.sum-card-live { background: linear-gradient(135deg, #67c23a08 0%, #409eff10 100%); border: 1px solid #67c23a22; }
.sum-label { color: #606266; font-size: 13px; margin-bottom: 6px; display: flex; align-items: center; }
.sum-value { font-size: 22px; font-weight: 700; color: #303133; }
.sum-sub { font-size: 12px; color: #909399; margin-top: 4px; }

.row-only-live { background: rgba(103, 194, 58, .06); }
.row-only-snap { background: rgba(144, 147, 153, .06); }

.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }

@media (max-width: 768px) {
  .sum-value { font-size: 18px; }
  .page-header h2 { font-size: 16px; }
}
</style>
