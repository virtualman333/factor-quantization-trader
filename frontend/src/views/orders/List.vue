<template>
  <div>
    <div class="page-header">
      <h2>
        订单管理
        <term-tip term-key="ord_type" />
      </h2>
      <div class="header-actions">
        <template v-if="activeTab === 'normal'">
          <el-select v-model="filterState" placeholder="状态" clearable style="width:130px">
            <el-option label="活跃" value="live" />
            <el-option label="部分成交" value="partially_filled" />
            <el-option label="已成交" value="filled" />
            <el-option label="已取消" value="canceled" />
          </el-select>
          <el-select v-model="filterSide" placeholder="方向" clearable style="width:100px;margin-left:8px">
            <el-option label="买入" value="buy" />
            <el-option label="卖出" value="sell" />
          </el-select>
        </template>
        <template v-else>
          <InstrumentSelect
            v-model="filterInstId"
            placeholder="筛选品种（留空=全部）"
            clearable
            style="width:200px"
          />
          <el-select v-model="filterInstType" placeholder="产品类型" style="width:120px;margin-left:8px">
            <el-option label="永续合约" value="SWAP" />
            <el-option label="现货" value="SPOT" />
            <el-option label="期货" value="FUTURES" />
          </el-select>
          <el-switch
            v-model="includeHistory"
            active-text="含历史" inactive-text="仅进行中"
            style="margin-left:12px"
          />
        </template>
        <el-button type="primary" :icon="Refresh" @click="loadCurrentTab" style="margin-left:8px">刷新</el-button>
        <el-button v-if="activeTab === 'normal'" type="warning" :icon="Refresh" @click="syncPending" style="margin-left:8px">同步待处理</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="orders-tabs" style="margin-top:8px">
      <el-tab-pane label="普通订单" name="normal">
        <!-- 新手提示 -->
        <el-alert
          v-if="showGuide"
          type="info"
          :closable="true"
          show-icon
          class="guide-alert"
          @close="onGuideClose"
        >
          <template #title>订单状态说明</template>
          <div class="guide-text">
            <el-tag size="small" type="warning">活跃</el-tag> 订单已提交但未完全成交；
            <el-tag size="small" type="success">已成交</el-tag> 订单全部成交；
            <el-tag size="small" type="info">已取消</el-tag> 订单已撤销。
            活跃订单可撤销，撤销后不可恢复。
          </div>
        </el-alert>

        <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
          <el-table-column prop="inst_id" label="品种" width="130" />
          <el-table-column prop="side_display" label="方向" width="70">
            <template #default="{ row }">
              <el-tag :type="row.side === 'buy' ? 'success' : 'danger'" size="small">{{ row.side_display }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="70">
            <template #default="{ row }">
              {{ row.ord_type_display }}
              <term-tip term-key="ord_type" />
            </template>
          </el-table-column>
          <el-table-column prop="sz" label="数量" width="100" />
          <el-table-column prop="px" label="价格" width="100" />
          <el-table-column prop="fill_sz" label="已成交" width="100" />
          <el-table-column prop="fill_px" label="成交价" width="100" />
          <el-table-column prop="fee" label="手续费" width="100" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="row.state === 'filled' ? 'success' : row.state === 'live' ? 'warning' : row.state === 'canceled' ? 'info' : 'danger'" size="small">
                {{ row.state_display }}
              </el-tag>
              <term-tip :term-key="row.state === 'live' ? 'state_live' : 'state_filled'" />
            </template>
          </el-table-column>
          <el-table-column prop="source" label="来源" width="80" />
          <el-table-column prop="created_at" label="创建时间" width="170" />
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.state === 'live'" size="small" type="danger" @click="cancel(row)">撤销</el-button>
              <el-button size="small" type="primary" text @click="openOrderDetail(row)">详情</el-button>
              <el-button size="small" @click="sync(row.id)">同步</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination">
          <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="prev, pager, next, total" @current-change="loadCurrentTab" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="条件单 / 止盈止损" name="conditional">
        <el-alert type="info" :closable="false" show-icon style="margin-top:16px">
          <template #title>
            条件单/止盈止损单由 OKX 托管，满足触发条件时自动成交。
            <term-tip term-key="ord_type" />
          </template>
        </el-alert>
        <el-table :data="conditionalList" v-loading="algoLoading" border stripe style="margin-top:16px">
          <el-table-column prop="instId" label="品种" width="130" />
          <el-table-column label="方向" width="70">
            <template #default="{ row }">
              <el-tag :type="row.side === 'buy' ? 'success' : 'danger'" size="small">
                {{ row.side === 'buy' ? '买入' : '卖出' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small">
                {{ ordTypeLabel(row.ordType) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="sz" label="数量" width="100" />
          <el-table-column label="触发价" width="120">
            <template #default="{ row }">
              <div v-if="row.triggerPx">
                <div>触发: {{ row.triggerPx }}</div>
                <div class="sub-tip">委托价: {{ row.px || '市价' }}</div>
              </div>
              <span v-else>--</span>
            </template>
          </el-table-column>
          <el-table-column label="止盈 / 止损" min-width="200">
            <template #default="{ row }">
              <div v-if="row.tpTriggerPx || row.slTriggerPx" class="tp-sl-cell">
                <div v-if="row.tpTriggerPx" class="tp-line">
                  <el-tag size="small" type="success">TP</el-tag>
                  触发 {{ row.tpTriggerPx }} · 委托 {{ row.tpOrdPx === '-1' ? '市价' : row.tpOrdPx }}
                </div>
                <div v-if="row.slTriggerPx" class="sl-line">
                  <el-tag size="small" type="danger">SL</el-tag>
                  触发 {{ row.slTriggerPx }} · 委托 {{ row.slOrdPx === '-1' ? '市价' : row.slOrdPx }}
                </div>
              </div>
              <span v-else>--</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="stateTagType(row.state)" size="small">
                {{ stateLabel(row.state) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">{{ formatTs(row.cTime) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button v-if="isLiveAlgoState(row.state)" size="small" type="danger" @click="cancelConditional(row)">撤销</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="conditionalHistory && conditionalHistory.length" style="margin-top:24px">
          <h4 class="sub-title">历史条件单（最近 {{ conditionalHistory.length }} 条）</h4>
          <el-table :data="conditionalHistory" size="small" border stripe max-height="240">
            <el-table-column prop="instId" label="品种" width="130" />
            <el-table-column label="方向" width="70">
              <template #default="{ row }">{{ row.side === 'buy' ? '买入' : '卖出' }}</template>
            </el-table-column>
            <el-table-column label="触发价 / 止盈止损" min-width="200">
              <template #default="{ row }">
                <span v-if="row.triggerPx">{{ row.triggerPx }}</span>
                <span v-else-if="row.tpTriggerPx || row.slTriggerPx">TP {{ row.tpTriggerPx || '--' }} / SL {{ row.slTriggerPx || '--' }}</span>
                <span v-else>--</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="stateTagType(row.state)" size="small">{{ stateLabel(row.state) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="触发时间" width="170">
              <template #default="{ row }">{{ formatTs(row.actualTriggerTime || row.cTime) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="TWAP 进度" name="twap">
        <el-alert type="info" :closable="false" show-icon style="margin-top:16px">
          <template #title>TWAP（时间加权）是本地模拟算法单：将大订单拆分成多个小单，按固定时间间隔（默认 60 秒）依次提交，减少滑点冲击。</template>
        </el-alert>
        <algo-batches-table
          title="进行中的 TWAP 批次"
          :list="twapBatches"
          :empty="!includeHistory && twapBatches.length === 0"
          :loading="algoLoading"
          @cancel="cancelTwapBatch"
        />
        <algo-batches-table
          v-if="includeHistory"
          :title="`历史批次（最近 ${twapBatchesHistory.length} 条）`"
          :list="twapBatchesHistory"
          :history="true"
          :loading="algoLoading"
        />
      </el-tab-pane>

      <el-tab-pane label="冰山单进度" name="iceberg">
        <el-alert type="info" :closable="false" show-icon style="margin-top:16px">
          <template #title>冰山单：将大订单按「显示数量」拆分成小限价单，每成交一片后自动挂上一片，避免暴露意图。</template>
        </el-alert>
        <algo-batches-table
          title="进行中的冰山单批次"
          :list="icebergBatches"
          :empty="!includeHistory && icebergBatches.length === 0"
          :loading="algoLoading"
          @cancel="cancelIcebergBatch"
        />
        <algo-batches-table
          v-if="includeHistory"
          :title="`历史批次（最近 ${icebergBatchesHistory.length} 条）`"
          :list="icebergBatchesHistory"
          :history="true"
          :loading="algoLoading"
        />
      </el-tab-pane>
    </el-tabs>

    <!-- 订单详情弹窗（P2-1 预埋：完整属性 + OrderLog） -->
    <order-detail-dialog v-model:visible="detailVisible" :order="currentOrder" @refreshed="load" />
  </div>
</template>

<script setup>
import { ref, onMounted, watch, defineAsyncComponent } from 'vue'
import { useOrderStore } from '@/stores/orders'
import { useConfirm } from '@/composables/useConfirm'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import InstrumentSelect from '@/components/InstrumentSelect.vue'
import { listAlgoOrders, cancelAlgoOrder } from '@/api/orders'
import { formatDateTime } from '@/utils/time'

const OrderDetailDialog = defineAsyncComponent(() => import('@/components/OrderDetailDialog.vue'))
// 批次表格子组件（TWAP/Iceberg 共用）
const AlgoBatchesTable = defineAsyncComponent(() => import('@/components/AlgoBatchesTable.vue'))

const orderStore = useOrderStore()
const { confirm } = useConfirm()

// ====== Tab & 通用筛选 ======
const activeTab = ref('normal')
const filterInstId = ref('')
const filterInstType = ref('SWAP')
const includeHistory = ref(false)
const algoLoading = ref(false)

// ====== 普通订单 ======
const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const filterState = ref('')
const filterSide = ref('')
const showGuide = ref(!localStorage.getItem('order_guide_dismissed'))

// ====== 订单详情 ======
const detailVisible = ref(false)
const currentOrder = ref(null)
function openOrderDetail(row) {
  currentOrder.value = row
  detailVisible.value = true
}

function onGuideClose() { localStorage.setItem('order_guide_dismissed', '1'); showGuide.value = false }

const load = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 50 }
    if (filterState.value) params.state = filterState.value
    if (filterSide.value) params.side = filterSide.value
    const { results, count } = await orderStore.fetchList(params, { force: true })
    tableData.value = results
    total.value = count
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const cancel = async (row) => {
  const ok = await confirm(
    `确认撤销订单 ${row.inst_id}（${row.side === 'buy' ? '买入' : '卖出'} ${row.sz}）？`,
    '撤销确认',
    { type: 'warning', confirmButtonText: '撤销' }
  )
  if (!ok) return
  try {
    await orderStore.cancel(row.id)
    ElMessage.success('已撤销')
    load()
  } catch (e) { ElMessage.error(e.message) }
}

const sync = async (id) => {
  try { await orderStore.sync(id); ElMessage.success('同步成功'); load() }
  catch (e) { ElMessage.error(e.message) }
}

const syncPending = async () => {
  try { await orderStore.syncPending(); ElMessage.success('同步完成'); load() }
  catch (e) { ElMessage.error(e.message) }
}

// ====== 条件单 ======
const conditionalList = ref([])
const conditionalHistory = ref([])

// ====== TWAP / 冰山批次 ======
const twapBatches = ref([])
const twapBatchesHistory = ref([])
const icebergBatches = ref([])
const icebergBatchesHistory = ref([])

function ordTypeLabel(t) {
  return { '1': '条件单', '2': 'OCO', '3': '止盈止损', conditional: '条件单', oco: 'OCO', 'oco_single': 'OCO', 'limit': '限价条件' }[t] || t || '--'
}
function stateLabel(s) {
  if (!s) return '--'
  // OKX 条件单状态: 1 live / 2 暂停 / 3 已触发? /9 已完成 / 10 已撤回 / 11 部分触发 / 12 已拒绝 / 13 部分触发
  return {
    '1': '进行中', '2': '暂停', '9': '已完成', '10': '已撤回',
    '11': '已触发', '12': '已拒绝', '13': '部分触发', '14': '已失效',
  }[String(s)] || String(s)
}
function stateTagType(s) {
  const live = ['1', '2', 'live']
  const ok = ['9', '11', 'filled']
  const cancel = ['10', 'canceled']
  const bad = ['12', '13', '14']
  s = String(s)
  if (live.includes(s)) return 'warning'
  if (ok.includes(s)) return 'success'
  if (cancel.includes(s)) return 'info'
  if (bad.includes(s)) return 'danger'
  return ''
}
function isLiveAlgoState(s) { return ['1', '2', 'live', 'pending'].includes(String(s)) }
function formatTs(t) {
  if (!t) return '--'
  const ts = String(t).length === 13 ? Number(t) : Number(t) * 1000
  return formatDateTime(new Date(ts))
}

async function loadConditional() {
  algoLoading.value = true
  try {
    const res = await listAlgoOrders({
      algo_type: 'conditional',
      inst_type: filterInstType.value,
      inst_id: filterInstId.value,
      include_history: includeHistory.value ? 'true' : 'false',
    })
    conditionalList.value = res.results || []
    conditionalHistory.value = res.history || []
  } catch (e) { ElMessage.error(e.message) }
  algoLoading.value = false
}

async function cancelConditional(row) {
  const ok = await confirm(
    `确认撤销条件单 ${row.instId}（${row.side === 'buy' ? '买入' : '卖出'} ${row.sz}）？`,
    '撤销条件单',
    { type: 'warning', confirmButtonText: '撤销' },
  )
  if (!ok) return
  try {
    await cancelAlgoOrder({
      algo_type: 'conditional',
      inst_id: row.instId,
      algo_id: row.algoId,
    })
    ElMessage.success('撤销请求已发送')
    setTimeout(loadConditional, 800)
  } catch (e) { ElMessage.error(e.message) }
}

async function loadLocalAlgo(kind) {
  algoLoading.value = true
  try {
    const res = await listAlgoOrders({
      algo_type: kind,
      inst_id: filterInstId.value,
      include_history: 'true',
    })
    const all = res.results || []
    const liveState = (progress, sliceStatus) =>
      progress > 0 && progress < 1
    const live = []
    const hist = []
    for (const b of all) {
      if (liveState(b.progress, b.pending_slices) || b.pending_slices > 0) live.push(b)
      else hist.push(b)
    }
    if (kind === 'twap') {
      twapBatches.value = live
      twapBatchesHistory.value = includeHistory.value ? hist : []
    } else {
      icebergBatches.value = live
      icebergBatchesHistory.value = includeHistory.value ? hist : []
    }
  } catch (e) { ElMessage.error(e.message) }
  algoLoading.value = false
}

async function cancelTwapBatch(batch) {
  const ids = (batch.details || []).filter(d => ['live', 'partially_filled'].includes(d.state)).map(d => d.id)
  if (!ids.length) { ElMessage.warning('没有可撤销的待成交子单'); return }
  const ok = await confirm(
    `撤销 TWAP 批次 ${batch.inst_id} 剩余 ${batch.pending_slices} 片 (${ids.length} 个子单)？`,
    '撤销 TWAP',
    { type: 'warning', confirmButtonText: '撤销全部' },
  )
  if (!ok) return
  try {
    const res = await cancelAlgoOrder({ algo_type: 'twap', inst_id: batch.inst_id, ids })
    ElMessage.success(`已请求撤销: 成功 ${res.canceled || ids.length} 个`)
    setTimeout(() => loadLocalAlgo('twap'), 800)
  } catch (e) { ElMessage.error(e.message) }
}

async function cancelIcebergBatch(batch) {
  const ids = (batch.details || []).filter(d => ['live', 'partially_filled'].includes(d.state)).map(d => d.id)
  if (!ids.length) { ElMessage.warning('没有可撤销的挂单'); return }
  const ok = await confirm(
    `撤销冰山单批次 ${batch.inst_id} 剩余 ${batch.pending_slices} 片 (${ids.length} 个子单)？`,
    '撤销冰山单',
    { type: 'warning', confirmButtonText: '撤销全部' },
  )
  if (!ok) return
  try {
    const res = await cancelAlgoOrder({ algo_type: 'iceberg', inst_id: batch.inst_id, ids })
    ElMessage.success(`已请求撤销: 成功 ${res.canceled || ids.length} 个`)
    setTimeout(() => loadLocalAlgo('iceberg'), 800)
  } catch (e) { ElMessage.error(e.message) }
}

function loadCurrentTab() {
  switch (activeTab.value) {
    case 'normal': return load()
    case 'conditional': return loadConditional()
    case 'twap': return loadLocalAlgo('twap')
    case 'iceberg': return loadLocalAlgo('iceberg')
  }
}

watch(activeTab, loadCurrentTab)
watch([filterState, filterSide], () => { page.value = 1; load() })
watch([filterInstId, filterInstType, includeHistory], () => {
  if (activeTab.value !== 'normal') loadCurrentTab()
})

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.header-actions { display: flex; align-items: center; flex-wrap: wrap; }
.guide-alert { margin-top: 16px; }
.guide-text { font-size: 13px; line-height: 1.8; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.sub-title { margin: 12px 0 8px; font-size: 14px; color: #606266; }
.sub-tip { font-size: 11px; color: #909399; }
.tp-sl-cell .tp-line { color: #67c23a; }
.tp-sl-cell .sl-line { color: #f56c6c; margin-top: 4px; }
@media (max-width: 768px) {
  .header-actions { width: 100%; }
  .header-actions .el-select { flex: 1; }
}
</style>
