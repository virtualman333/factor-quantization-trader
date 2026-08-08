<template>
  <div>
    <div class="page-header">
      <div class="title-wrap">
        <h2>交易信号</h2>
        <el-tooltip placement="right" :show-after="300">
          <template #content>
            <div style="max-width:280px;line-height:1.6">
              <div><b>什么是交易信号？</b></div>
              <div>策略基于因子模型对当前行情计算后产生的买卖建议。信号得分越高代表策略越确信。未执行的信号可以手动下单。</div>
            </div>
          </template>
          <el-icon class="tip-icon"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
      <div>
        <el-select v-model="filterSignal" placeholder="信号类型" clearable style="width:140px">
          <el-option label="买入/开多" value="buy" />
          <el-option label="卖出/开空" value="sell" />
          <el-option label="平多" value="close_long" />
          <el-option label="平空" value="close_short" />
          <el-option label="持有" value="hold" />
        </el-select>
        <el-select v-model="filterExecuted" placeholder="执行状态" clearable style="width:130px;margin-left:8px">
          <el-option label="已执行" :value="true" />
          <el-option label="未执行" :value="false" />
        </el-select>
        <el-button type="primary" :icon="Refresh" @click="load" style="margin-left:8px">刷新</el-button>
      </div>
    </div>

    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px" @row-click="openDetail">
      <el-table-column prop="inst_id" label="品种" width="140">
        <template #header>
          <span>品种</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>OKX 交易标的，如 BTC-USDT-SWAP 永续合约</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="strategy_name" label="所属策略" width="160" />
      <el-table-column label="信号类型" width="130">
        <template #header>
          <span>信号</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>策略根据行情判断给出的操作建议</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          <el-tag :type="signalTagType(row.signal)" size="small" effect="light">
            {{ row.signal_display || row.signal }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="信号得分" width="120">
        <template #header>
          <span>得分</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>0~1 的综合因子评分，越接近 1 代表策略越确信该信号正确</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          <el-progress
            :percentage="scorePct(row.score)"
            :stroke-width="10"
            :color="scoreColor(row.score)"
            :format="(p) => (Number(row.score || 0)).toFixed(2)"
          />
        </template>
      </el-table-column>
      <el-table-column label="持仓方向" width="100">
        <template #header>
          <span>方向</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>long=做多，short=做空，net=净仓</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          <el-tag v-if="row.pos_side_display || row.pos_side" size="small" :type="row.pos_side === 'long' ? 'success' : row.pos_side === 'short' ? 'danger' : 'info'">
            {{ row.pos_side_display || row.pos_side }}
          </el-tag>
          <span v-else style="color:#c0c4cc">--</span>
        </template>
      </el-table-column>
      <el-table-column label="保证金模式" width="110">
        <template #header>
          <span>模式</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>cash=现货，cross=全仓（账户余额共用保证金），isolated=逐仓（仅该仓位保证金承担风险）</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          {{ row.td_mode_display || row.td_mode || '--' }}
        </template>
      </el-table-column>
      <el-table-column label="杠杆" width="80" align="right">
        <template #default="{ row }">{{ row.leverage != null ? Number(row.leverage).toFixed(1) + 'x' : '--' }}</template>
      </el-table-column>
      <el-table-column label="触发价格" width="130" align="right">
        <template #default="{ row }">{{ fmtPrice(row.price) }}</template>
      </el-table-column>
      <el-table-column label="止损价" width="130" align="right">
        <template #header>
          <span>止损价</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>价格触碰后自动止损平仓，用于限制单笔亏损</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          <span style="color:#f56c6c">{{ fmtPrice(row.stop_loss_price) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="止盈价" width="130" align="right">
        <template #header>
          <span>止盈价</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>价格触碰后自动止盈平仓，用于锁定预期利润</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          <span style="color:#67c23a">{{ fmtPrice(row.take_profit_price) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="is_executed" label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_executed ? 'success' : 'warning'" size="small" effect="plain">
            {{ row.is_executed ? '已执行' : '未执行' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="信号时间" width="170">
        <template #default="{ row }">{{ fmtDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right" align="center">
        <template #default="{ row }">
          <el-button size="small" text type="primary" :icon="View" @click.stop="openDetail(row)">详情</el-button>
          <el-button
            v-if="!row.is_executed"
            size="small" text type="success" :icon="VideoPlay"
            @click.stop="execute(row)"
          >执行</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @size-change="onSizeChange"
        @current-change="load"
      />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="信号详情" width="680px" top="8vh" :close-on-click-modal="false">
      <el-descriptions v-if="selected" :column="2" border size="default">
        <el-descriptions-item label="品种">{{ selected.inst_id }}</el-descriptions-item>
        <el-descriptions-item label="所属策略">{{ selected.strategy_name || '--' }}</el-descriptions-item>
        <el-descriptions-item label="信号类型">
          <el-tag :type="signalTagType(selected.signal)" size="small">
            {{ selected.signal_display || selected.signal }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="信号得分">
          <el-progress
            style="width:180px;vertical-align:middle"
            :percentage="scorePct(selected.score)"
            :stroke-width="12"
            :color="scoreColor(selected.score)"
            :format="(p) => (Number(selected.score || 0)).toFixed(3)"
          />
        </el-descriptions-item>
        <el-descriptions-item label="持仓方向">
          <el-tag v-if="selected.pos_side_display || selected.pos_side" size="small" :type="selected.pos_side === 'long' ? 'success' : selected.pos_side === 'short' ? 'danger' : 'info'">
            {{ selected.pos_side_display || selected.pos_side }}
          </el-tag>
          <span v-else>--</span>
        </el-descriptions-item>
        <el-descriptions-item label="保证金模式">{{ selected.td_mode_display || selected.td_mode || '--' }}</el-descriptions-item>
        <el-descriptions-item label="杠杆">{{ selected.leverage != null ? Number(selected.leverage).toFixed(1) + 'x' : '--' }}</el-descriptions-item>
        <el-descriptions-item label="执行状态">
          <el-tag :type="selected.is_executed ? 'success' : 'warning'" size="small" effect="plain">
            {{ selected.is_executed ? '已执行' : '未执行' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="触发价格">{{ fmtPrice(selected.price) }}</el-descriptions-item>
        <el-descriptions-item label="信号时间">{{ fmtDateTime(selected.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="止损价" :span="1">
          <span style="color:#f56c6c;font-weight:500">{{ fmtPrice(selected.stop_loss_price) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="止盈价" :span="1">
          <span style="color:#67c23a;font-weight:500">{{ fmtPrice(selected.take_profit_price) }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <el-card v-if="selected && hasFactors" style="margin-top:16px">
        <template #header>
          <div style="display:flex;align-items:center;gap:6px">
            <span>因子明细（评分构成）</span>
            <el-tooltip placement="top" :show-after="300">
              <template #content>策略使用的每个因子分别给出的子评分，加权后形成最终信号得分</template>
              <el-icon class="tip-inline"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </template>
        <el-row :gutter="16">
          <el-col :span="12" v-for="(val, key) in selected.factors_detail || {}" :key="key" style="margin-bottom:10px">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:13px">
              <span style="color:#606266">{{ factorLabel(key) }}</span>
              <span style="font-weight:500;color:#303133">{{ Number(val).toFixed(3) }}</span>
            </div>
            <el-progress
              :percentage="scorePct(val)"
              :stroke-width="8"
              :color="scoreColor(val)"
              :show-text="false"
            />
          </el-col>
        </el-row>
      </el-card>

      <el-card v-if="selected" style="margin-top:16px">
        <template #header>信号原因 / 备注</template>
        <div style="white-space:pre-wrap;line-height:1.7;color:#303133;min-height:40px">
          {{ selected.reason || '（未填写原因）' }}
        </div>
      </el-card>

      <el-empty v-if="!selected" description="数据未加载" />

      <template #footer>
        <div style="display:flex;justify-content:space-between">
          <div>
            <span style="color:#909399;font-size:12px">
              Tip: 信号仅供参考，请结合风控参数和自身判断决定是否执行
            </span>
          </div>
          <div>
            <el-button @click="detailVisible = false">关闭</el-button>
            <el-button
              v-if="selected && !selected.is_executed"
              type="success" :icon="VideoPlay"
              @click="execute(selected); detailVisible = false"
            >立即执行</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'Signals' })
import { ref, computed, onMounted, watch } from 'vue'
import { getSignals, executeSignal } from '@/api/strategy'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, View, QuestionFilled, VideoPlay } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/time'

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const filterSignal = ref('')
const filterExecuted = ref('')

const detailVisible = ref(false)
const selected = ref(null)

// ========== 格式化辅助 ==========
function fmtPrice(v) {
  if (v === null || v === undefined || v === '') return '--'
  const n = parseFloat(v)
  if (isNaN(n)) return '--'
  if (n >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 2 })
  if (n >= 1) return n.toLocaleString('en-US', { maximumFractionDigits: 4 })
  return n.toLocaleString('en-US', { maximumFractionDigits: 6 })
}
function fmtDateTime(v) {
  // 统一按北京时间显示，避免浏览器时区差异
  return formatDateTime(v)
}
function scorePct(v) {
  // score 是 0~1 的小数 (Decimal)，转为 0~100 的百分比给 el-progress
  if (v === null || v === undefined || v === '') return 0
  const n = parseFloat(v)
  if (isNaN(n)) return 0
  // 如果已经是 > 1 的值（比如已经是百分比），直接截断
  const pct = n <= 1 ? n * 100 : n
  return Math.min(100, Math.max(0, Math.round(pct)))
}
function scoreColor(v) {
  const n = parseFloat(v)
  if (isNaN(n)) return '#909399'
  const val = n <= 1 ? n : n / 100
  if (val >= 0.7) return '#67c23a'
  if (val >= 0.5) return '#e6a23c'
  return '#f56c6c'
}
const FACTOR_LABELS = {
  momentum: '动量 (ROC)',
  volatility: '波动率 (ATR/BBW)',
  rsi: '相对强弱 (RSI)',
  macd: 'MACD 指标',
  bbands: '布林带',
  volume_ratio: '量比',
  trend_strength: '趋势强度 (ADX)',
}
function factorLabel(k) { return FACTOR_LABELS[k] || k }

// ========== 派生 ==========
const hasFactors = computed(() => {
  const fd = selected.value?.factors_detail
  return fd && typeof fd === 'object' && Object.keys(fd).length > 0
})
const factorsEntries = computed(() => Object.entries(selected.value?.factors_detail || {}))

// ========== 业务方法 ==========
const load = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filterSignal.value) params.signal = filterSignal.value
    if (filterExecuted.value !== '') params.is_executed = filterExecuted.value
    const res = await getSignals(params)
    if (res && Array.isArray(res.results)) {
      tableData.value = res.results
      total.value = res.count ?? res.results.length
    } else if (Array.isArray(res)) {
      tableData.value = res
      total.value = res.length
    } else {
      tableData.value = []
      total.value = 0
    }
  } catch (e) { ElMessage.error(e.message || '加载信号列表失败') }
  loading.value = false
}
const onSizeChange = () => { page.value = 1; load() }

const openDetail = (row) => {
  selected.value = row
  detailVisible.value = true
}

const execute = async (row) => {
  const name = `${row.signal_display || row.signal} ${row.inst_id} @ ${fmtPrice(row.price)}`
  try {
    await ElMessageBox.confirm(
      `确认执行信号【${name}】？\n执行后将调用 OKX 接口根据该信号下单，请确认当前环境与风控参数。`,
      '执行信号确认',
      { type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '取消' },
    )
  } catch { return }
  try {
    await executeSignal(row.id)
    ElMessage.success('信号已执行')
    load()
  } catch (e) { ElMessage.error(e.message || '执行失败') }
}

const signalTagType = (signal) => {
  if (signal === 'buy') return 'success'
  if (signal === 'sell') return 'danger'
  if (signal === 'close_long' || signal === 'close_short') return 'warning'
  return 'info'
}

watch([filterSignal, filterExecuted], () => { page.value = 1; load() })
onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.title-wrap { display: flex; align-items: center; gap: 8px; }
.tip-icon { color: #909399; font-size: 18px; cursor: help; }
.tip-inline { color: #909399; font-size: 13px; margin-left: 4px; vertical-align: middle; cursor: help; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
