<template>
  <div>
    <div class="page-header">
      <h2>持仓管理</h2>
      <div>
        <el-select v-model="instType" style="width:120px">
          <el-option label="全部" value="" />
          <el-option label="现货" value="SPOT" />
          <el-option label="合约" value="SWAP" />
        </el-select>
        <el-button type="primary" :icon="Camera" :loading="loading" @click="takeSnapshot" style="margin-left:8px">保存快照</el-button>
        <el-button type="success" :icon="Refresh" :loading="loading" @click="loadLive" style="margin-left:8px">实时持仓</el-button>
      </div>
    </div>
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column prop="inst_id" label="品种" width="130" />
      <el-table-column prop="pos_side" label="方向" width="80">
        <template #default="{ row }">
          <el-tag :type="row.pos_side === 'long' ? 'success' : 'danger'" size="small">
            {{ row.pos_side === 'long' ? '多' : '空' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="pos" label="持仓量" width="120" />
      <el-table-column prop="avg_px" label="开仓均价" width="120" />
      <el-table-column prop="mark_px" label="标记价格" width="120" />
      <el-table-column label="浮动盈亏率" width="130">
        <template #default="{ row }">
          <span v-if="row.upl_ratio !== undefined && row.upl_ratio !== null" :style="{ color: row.upl_ratio >= 0 ? '#67c23a' : '#f56c6c' }">
            {{ (row.upl_ratio * 100).toFixed(2) }}%
          </span>
          <span v-else>--</span>
        </template>
      </el-table-column>
      <el-table-column prop="upl" label="未实现盈亏" width="140">
        <template #default="{ row }">
          <span :style="{ color: parseFloat(row.upl) >= 0 ? '#67c23a' : '#f56c6c' }">{{ row.upl }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="margin" label="保证金" width="120" />
      <el-table-column prop="leverage" label="杠杆" width="80" />
      <el-table-column prop="liq_px" label="强平价格" width="120" />
      <el-table-column prop="snapshot_time" label="快照时间" width="180" />
      <el-table-column label="操作" width="200" fixed="right" align="center">
        <template #default="{ row }">
          <el-button
            v-if="parseFloat(row.pos) > 0"
            size="small" type="danger" text
            @click.stop="openClose(row)"
          >一键平仓</el-button>
          <el-button
            v-if="parseFloat(row.pos) > 0"
            size="small" type="primary" text
            @click.stop="openSetTpSl(row)"
          >止盈止损</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pagination">
      <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="prev, pager, next, total" @current-change="load" />
    </div>

    <!-- 一键平仓确认弹窗 -->
    <el-dialog v-model="closeVisible" title="确认市价平仓" width="460px">
      <template v-if="closeRow">
        <el-alert
          title="市价平仓将立即按当前市价反向成交，滑点不可控"
          type="warning" show-icon :closable="false" style="margin-bottom:16px"
        />
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="品种">{{ closeRow.inst_id }}</el-descriptions-item>
          <el-descriptions-item label="方向">
            <el-tag :type="closeRow.pos_side === 'long' ? 'success' : 'danger'" size="small">
              {{ closeRow.pos_side === 'long' ? '多头' : '空头' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="平仓数量">{{ closeRow.pos }}</el-descriptions-item>
          <el-descriptions-item label="当前标记价">{{ closeRow.mark_px }}</el-descriptions-item>
          <el-descriptions-item label="未实现盈亏">
            <span :style="{ color: parseFloat(closeRow.upl) >= 0 ? '#67c23a' : '#f56c6c' }">{{ closeRow.upl }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="保证金模式">
            <el-select v-model="closeForm.td_mode" style="width:100%" size="small">
              <el-option label="现金/现货" value="cash" />
              <el-option label="全仓合约" value="cross" />
              <el-option label="逐仓合约" value="isolated" />
            </el-select>
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <template #footer>
        <el-button @click="closeVisible = false">取消</el-button>
        <el-button type="danger" :loading="closeLoading" @click="confirmClose">确认市价平仓</el-button>
      </template>
    </el-dialog>

    <!-- 设置止盈止损弹窗 -->
    <el-dialog v-model="tpSlVisible" title="设置止盈止损 (条件单)" width="500px">
      <template v-if="tpSlRow">
        <el-alert type="info" :closable="false" show-icon style="margin-bottom:16px">
          <template #title>
            <b>提示</b>：条件单触发后按市价成交。
            多头止盈/止损方向为「卖出」，空头止盈/止损方向为「买入」。
            <term-tip term-key="ord_type" />
          </template>
        </el-alert>
        <el-descriptions :column="2" border size="small" style="margin-bottom:16px">
          <el-descriptions-item label="品种">{{ tpSlRow.inst_id }}</el-descriptions-item>
          <el-descriptions-item label="方向 / 持仓量">
            {{ tpSlRow.pos_side === 'long' ? '多头' : '空头' }} / {{ tpSlRow.pos }}
          </el-descriptions-item>
          <el-descriptions-item label="开仓均价">{{ tpSlRow.avg_px }}</el-descriptions-item>
          <el-descriptions-item label="当前标记价">{{ tpSlRow.mark_px }}</el-descriptions-item>
        </el-descriptions>
        <el-form label-width="120px">
          <el-form-item :label="`止盈触发价 ${tpSlHint.tp}`" required>
            <el-input-number
              v-model="tpSlForm.tp_trigger_px"
              :precision="4" :step="stepByPrice(tpSlRow.mark_px)"
              :min="0" style="width:100%"
              :controls="false"
              placeholder="达到该价格自动止盈，留空则不设置"
            />
            <div class="form-tip">
              建议：<b @click="suggestTp(true)">{{ suggestTp(true) }}</b>（开仓价 +5%） ·
              <b @click="suggestTp(false)">{{ suggestTp(false) }}</b>（开仓价 +10%）
            </div>
          </el-form-item>
          <el-form-item :label="`止损触发价 ${tpSlHint.sl}`" required>
            <el-input-number
              v-model="tpSlForm.sl_trigger_px"
              :precision="4" :step="stepByPrice(tpSlRow.mark_px)"
              :min="0" style="width:100%"
              :controls="false"
              placeholder="达到该价格自动止损，留空则不设置"
            />
            <div class="form-tip">
              建议：<b @click="suggestSl(true)">{{ suggestSl(true) }}</b>（开仓价 -3%） ·
              <b @click="suggestSl(false)">{{ suggestSl(false) }}</b>（开仓价 -5%）
            </div>
          </el-form-item>
          <el-form-item label="平仓数量">
            <el-input-number
              v-model="tpSlForm.sz"
              :precision="4" :min="0" style="width:100%" :controls="false"
            />
            <div class="form-tip">默认等于全部持仓</div>
          </el-form-item>
          <el-form-item label="保证金模式">
            <el-select v-model="tpSlForm.td_mode" style="width:100%">
              <el-option label="现金/现货" value="cash" />
              <el-option label="全仓合约" value="cross" />
              <el-option label="逐仓合约" value="isolated" />
            </el-select>
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="tpSlVisible = false">取消</el-button>
        <el-button type="primary" :loading="tpSlLoading" @click="confirmSetTpSl">提交止盈止损条件单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'Positions' })
import { ref, computed, onMounted } from 'vue'
import { Camera, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { nowBeijing } from '@/utils/time'
import { getPositions, savePositionSnapshot, getLivePositions } from '@/api/account'
import { closePosition, placeAlgoOrder } from '@/api/orders'

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const instType = ref('')

// 平仓弹窗
const closeVisible = ref(false)
const closeLoading = ref(false)
const closeRow = ref(null)
const closeForm = ref({ td_mode: 'cross' })

// 止盈止损弹窗
const tpSlVisible = ref(false)
const tpSlLoading = ref(false)
const tpSlRow = ref(null)
const tpSlForm = ref({ sz: '', td_mode: 'cross', tp_trigger_px: null, sl_trigger_px: null })

const tpSlHint = computed(() => {
  if (!tpSlRow.value) return { tp: '', sl: '' }
  // 给出方向提示：多头止盈/止损都是触发后卖出；空头则买入；提示"应高于/低于当前价"
  if (tpSlRow.value.pos_side === 'long') {
    return {
      tp: '(建议 > 当前价，触发后卖出)',
      sl: '(建议 < 当前价，触发后卖出)',
    }
  }
  return {
    tp: '(建议 < 当前价，触发后买入)',
    sl: '(建议 > 当前价，触发后买入)',
  }
})

const stepByPrice = (price) => {
  const p = parseFloat(price) || 0
  if (p >= 10000) return 1
  if (p >= 100) return 0.01
  return 0.0001
}

const roundByStep = (v, step) => {
  const digits = -Math.floor(Math.log10(step || 0.0001))
  return Number(v).toFixed(Math.max(0, digits))
}

// 计算某个方向的价格 (delta: +0.05 表示 +5%, -0.03 表示 -3%)
function priceAtDelta(base, delta) {
  const b = parseFloat(base) || 0
  const step = stepByPrice(b)
  return roundByStep(b * (1 + delta), step)
}

// 多头 long:  TP = avg * +5%/+10%  (涨了之后卖)
//            SL = avg * -3%/-5%  (跌了之后卖)
// 空头 short: TP = avg * -5%/-10% (跌了之后买平，赚了)
//            SL = avg * +3%/+5%  (涨了之后买平，亏了)

function suggestTp(moderate) {
  const row = tpSlRow.value
  if (!row) return ''
  const base = row.avg_px || row.mark_px || 0
  const delta = (moderate ? 0.05 : 0.10) * (row.pos_side === 'long' ? 1 : -1)
  const val = priceAtDelta(base, delta)
  tpSlForm.value.tp_trigger_px = Number(val)
  return val
}
function suggestSl(moderate) {
  const row = tpSlRow.value
  if (!row) return ''
  const base = row.avg_px || row.mark_px || 0
  const delta = (moderate ? 0.03 : 0.05) * (row.pos_side === 'long' ? -1 : 1)
  const val = priceAtDelta(base, delta)
  tpSlForm.value.sl_trigger_px = Number(val)
  return val
}

// 平仓按钮点击
function openClose(row) {
  closeRow.value = row
  closeForm.value = { td_mode: guessTdMode(row) }
  closeVisible.value = true
}

async function confirmClose() {
  if (!closeRow.value) return
  const sz = String(parseFloat(closeRow.value.pos) || 0)
  if (!sz || parseFloat(sz) <= 0) {
    ElMessage.warning('持仓数量无效')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认以市价平掉 ${closeRow.value.inst_id} ${sz} 的${closeRow.value.pos_side === 'long' ? '多头' : '空头'}？此操作不可撤销。`,
      '平仓二次确认',
      { type: 'warning', confirmButtonText: '确认平仓', cancelButtonText: '取消' },
    )
  } catch { return }

  closeLoading.value = true
  try {
    // 不传 side 由后端通过实时持仓检测方向，更可靠
    const res = await closePosition({
      inst_id: closeRow.value.inst_id,
      sz,
      side: closeRow.value.pos_side === 'long' ? 'sell' : 'buy',
      td_mode: closeForm.value.td_mode,
      source: 'manual',
    })
    ElMessage.success(`平仓提交成功，订单ID: ${res.ordId || res.ord_id || '--'}`)
    closeVisible.value = false
    setTimeout(loadLive, 1500)
  } catch (e) {
    ElMessage.error(e.message || '平仓失败')
  } finally {
    closeLoading.value = false
  }
}

// 止盈止损按钮点击
function openSetTpSl(row) {
  tpSlRow.value = row
  const sz = String(parseFloat(row.pos) || 0)
  tpSlForm.value = {
    sz,
    td_mode: guessTdMode(row),
    tp_trigger_px: null,
    sl_trigger_px: null,
  }
  tpSlVisible.value = true
}

function guessTdMode(row) {
  const lev = parseFloat(row.leverage) || 0
  if (lev > 1) return 'cross'
  return 'cash'
}

async function confirmSetTpSl() {
  const row = tpSlRow.value
  if (!row) return
  const sz = String(parseFloat(tpSlForm.value.sz) || 0)
  if (parseFloat(sz) <= 0) {
    ElMessage.warning('平仓数量必须大于 0')
    return
  }
  const tpPx = tpSlForm.value.tp_trigger_px
  const slPx = tpSlForm.value.sl_trigger_px
  if ((tpPx === null || tpPx === undefined || tpPx === '') &&
      (slPx === null || slPx === undefined || slPx === '')) {
    ElMessage.warning('止盈和止损至少填一个')
    return
  }
  // 方向：止盈止损条件单以"平仓方向"提交，long→sell / short→buy
  const side = row.pos_side === 'long' ? 'sell' : 'buy'

  tpSlLoading.value = true
  try {
    const res = await placeAlgoOrder({
      inst_id: row.inst_id,
      side,
      sz,
      ord_type: tpPx && slPx ? 'oco' : 'conditional',
      td_mode: tpSlForm.value.td_mode,
      tp_trigger_px: tpPx != null ? String(tpPx) : '',
      sl_trigger_px: slPx != null ? String(slPx) : '',
    })
    ElMessage.success(`止盈止损条件单已提交: ${res.result?.algoId || res.result?.ordId || '成功'}`)
    tpSlVisible.value = false
  } catch (e) {
    ElMessage.error(e.message || '条件单提交失败')
  } finally {
    tpSlLoading.value = false
  }
}

const load = async () => {
  loading.value = true
  try {
    const params = { page: page.value }
    if (instType.value) params.inst_type = instType.value
    const res = await getPositions(params)
    const list = res.results || res
    tableData.value = enrichUplRatio(list)
    total.value = res.count || 0
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const takeSnapshot = async () => {
  loading.value = true
  try {
    await savePositionSnapshot({ inst_type: instType.value || undefined })
    ElMessage.success('快照已保存'); await load()
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const loadLive = async () => {
  loading.value = true
  try {
    const params = {}
    if (instType.value) params.inst_type = instType.value
    const res = await getLivePositions(params)
    // 后端返回 { results: [...] }
    const positions = res?.results || res?.data || []
    const list = (Array.isArray(positions) ? positions : []).map(p => ({
      inst_id: p.inst_id || p.instId,
      pos_side: p.pos_side || p.posSide || 'net',
      pos: p.pos,
      avg_px: p.avg_px ?? p.avgPx,
      mark_px: p.mark_px ?? p.markPx,
      upl: p.upl,
      margin: p.margin,
      leverage: p.leverage ?? p.lever,
      liq_px: p.liq_px ?? p.liqPx,
      snapshot_time: nowBeijing(),
    }))
    tableData.value = enrichUplRatio(list)
    total.value = tableData.value.length
    ElMessage.success(`获取 ${tableData.value.length} 条实时持仓`)
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

function enrichUplRatio(list) {
  return (list || []).map(r => {
    const avg = parseFloat(r.avg_px)
    const mark = parseFloat(r.mark_px)
    const upl = parseFloat(r.upl)
    let upl_ratio = null
    if (avg && mark) {
      upl_ratio = (mark - avg) / avg
      if (r.pos_side === 'short') upl_ratio = -upl_ratio
    } else if (r.margin && upl) {
      upl_ratio = upl / parseFloat(r.margin)
    }
    return { ...r, upl_ratio }
  })
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.form-tip { margin-top: 6px; font-size: 12px; color: #909399; }
.form-tip b { color: #409eff; cursor: pointer; }
.form-tip b:hover { text-decoration: underline; }
</style>
