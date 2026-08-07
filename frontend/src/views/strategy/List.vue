<template>
  <div>
    <div class="page-header">
      <h2>策略管理</h2>
      <el-button type="primary" :icon="Plus" @click="openDialog(null)">新建策略</el-button>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-bar">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="名称">
          <el-input v-model="filters.keyword" placeholder="策略名称模糊搜索" clearable @keyup.enter="onSearch" @clear="onSearch" style="width:180px" />
        </el-form-item>
        <el-form-item label="策略类型">
          <el-select v-model="filters.strategy_type" placeholder="全部" clearable @change="onSearch" style="width:140px">
            <el-option v-for="o in STRATEGY_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="品种类型">
          <el-select v-model="filters.inst_type" placeholder="全部" clearable @change="onSearch" style="width:120px">
            <el-option label="现货" value="SPOT" />
            <el-option label="永续合约" value="SWAP" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable @change="onSearch" style="width:120px">
            <el-option v-for="o in STATUS_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="方向">
          <el-select v-model="filters.direction" placeholder="全部" clearable @change="onSearch" style="width:120px">
            <el-option v-for="o in DIRECTION_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
          <el-button :icon="RefreshLeft" @click="onReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column prop="name" label="名称" width="150" />
      <el-table-column prop="strategy_type_display" label="策略类型" width="120" />
      <el-table-column prop="inst_type" label="品种类型" width="100" />
      <el-table-column prop="bar" label="K线周期" width="80" />
      <el-table-column prop="direction_display" label="方向" width="80" />
      <el-table-column prop="td_mode_display" label="保证金模式" width="110" />
      <el-table-column prop="leverage" label="杠杆" width="80" />
      <el-table-column prop="status_display" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : row.status === 'paused' ? 'warning' : 'info'" size="small">
            {{ row.status_display }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="initial_capital" label="初始资金" width="120" />
      <el-table-column prop="order_size_pct" label="仓位比例" width="100" />
      <el-table-column prop="max_positions" label="最大持仓" width="100" />
      <el-table-column label="操作" width="420" fixed="right">

        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button v-if="row.status !== 'active'" size="small" type="success" @click="activate(row.id)">激活</el-button>
          <el-button v-if="row.status === 'active'" size="small" type="warning" @click="pause(row.id)">暂停</el-button>
          <el-button size="small" @click="runSignals(row.id)">生成信号</el-button>
          <el-button size="small" type="danger" @click="executeSignals(row.id)">执行</el-button>
          <el-button size="small" @click="showBacktest(row)">回测</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      background
      layout="total, sizes, prev, pager, next, jumper"
      :total="total"
      :page-size="pageSize"
      :current-page="page"
      :page-sizes="[10, 20, 50, 100]"
      @size-change="(s) => { pageSize = s; page = 1; load() }"
      @current-change="(p) => { page = p; load() }"
    />

    <!-- 编辑/新建弹窗 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑策略' : '新建策略'" width="600px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>
        <el-form-item label="策略类型">
          <el-select v-model="form.strategy_type">
            <el-option label="因子综合评分" value="factor_composite" />
            <el-option label="趋势跟踪" value="trend_follow" />
            <el-option label="放量跟随" value="volume_breakout" />
          </el-select>
        </el-form-item>
        <el-form-item label="品种类型">
          <el-select v-model="form.inst_type">
            <el-option label="现货" value="SPOT" />
            <el-option label="永续合约" value="SWAP" />
          </el-select>
        </el-form-item>
        <el-form-item label="交易对">
          <el-select v-model="form.symbols" multiple filterable remote :remote-method="searchInstruments" :loading="instrumentsLoading" placeholder="选择交易对" style="width:100%">
            <el-option v-for="item in instrumentOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="K线周期">
          <el-select v-model="form.bar">
            <el-option v-for="b in ['1m','5m','15m','30m','1H','4H','1D','1W']" :key="b" :label="b" :value="b" />
          </el-select>
        </el-form-item>
        <el-form-item label="方向">
          <el-select v-model="form.direction">
            <el-option label="做多" value="long" />
            <el-option label="做空" value="short" />
            <el-option label="双向" value="both" />
          </el-select>
        </el-form-item>
        <el-form-item label="保证金模式">
          <el-select v-model="form.td_mode">
            <el-option label="现金/现货" value="cash" />
            <el-option label="全仓合约" value="cross" />
            <el-option label="逐仓合约" value="isolated" />
          </el-select>
        </el-form-item>
        <el-form-item label="杠杆倍数">
          <el-input-number v-model="form.leverage" :min="1" :max="100" :step="1" />
        </el-form-item>
        <el-form-item label="初始资金">
          <el-input-number v-model="form.initial_capital" :min="0" :step="1000" />
        </el-form-item>
        <el-form-item label="仓位比例">
          <el-input-number v-model="form.order_size_pct" :min="0.01" :max="1" :step="0.05" />
        </el-form-item>
        <el-form-item label="最大持仓">
          <el-input-number v-model="form.max_positions" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="止损比例">
          <el-input-number v-model="form.stop_loss_pct" :min="0.01" :max="0.5" :step="0.01" />
        </el-form-item>
        <el-form-item label="止盈比例">
          <el-input-number v-model="form.take_profit_pct" :min="0.01" :max="1" :step="0.01" />
        </el-form-item>
        <el-form-item label="因子列表" v-if="form.strategy_type === 'factor_composite'">
          <el-input v-model="factorsStr" placeholder="逗号分隔因子名 (momentum,rsi,macd)" />
        </el-form-item>

        <el-divider content-position="left" v-if="form.strategy_type === 'volume_breakout'">放量跟随参数</el-divider>
        <template v-if="form.strategy_type === 'volume_breakout'">
          <el-form-item label="成交量均线周期">
            <el-input-number v-model="form.params.vol_ma_len" :min="2" :max="200" />
          </el-form-item>
          <el-form-item label="放量倍数阈值">
            <el-input-number v-model="form.params.vol_ratio" :min="1" :max="10" :step="0.1" />
          </el-form-item>
          <el-form-item label="趋势均线周期">
            <el-input-number v-model="form.params.trend_ma_len" :min="5" :max="500" />
            <span class="hint">区分大方向(震荡过滤)，如60=1小时</span>
          </el-form-item>
          <el-form-item label="ATR周期">
            <el-input-number v-model="form.params.atr_len" :min="2" :max="100" />
          </el-form-item>
          <el-form-item label="最小波动阈值">
            <el-input-number v-model="form.params.min_atr_factor" :min="0" :max="0.02" :step="0.0001" />
            <span class="hint">ATR/价格 低于此值则震荡屏蔽</span>
          </el-form-item>
          <el-form-item label="冷却时间">
            <el-input-number v-model="form.params.cooling_min" :min="1" :max="60" />
            <span class="hint">同方向信号最小间隔(分钟)</span>
          </el-form-item>
          <el-form-item label="止损倍数">
            <el-input-number v-model="form.params.stop_loss_mul" :min="0.1" :max="5" :step="0.1" />
            <span class="hint">止损 = 倍数 × entry_atr</span>
          </el-form-item>
          <el-form-item label="止盈模式">
            <el-select v-model="form.params.tp_mode" style="width:160px">
              <el-option label="固定盈亏比" value="fixed" />
              <el-option label="移动止盈" value="trailing" />
            </el-select>
          </el-form-item>
          <el-form-item label="固定止盈盈亏比" v-if="form.params.tp_mode === 'fixed'">
            <el-input-number v-model="form.params.tp_ratio" :min="0.5" :max="10" :step="0.1" />
          </el-form-item>
          <el-form-item label="移动止盈激活" v-if="form.params.tp_mode === 'trailing'">
            <el-input-number v-model="form.params.trailing_trigger" :min="0.1" :max="2" :step="0.1" />
            <span class="hint">盈利达 倍数×止损距离 启动追踪</span>
          </el-form-item>
          <el-form-item label="移动追踪幅度" v-if="form.params.tp_mode === 'trailing'">
            <el-input-number v-model="form.params.trailing_factor" :min="0.1" :max="3" :step="0.1" />
            <span class="hint">追踪幅度 = 因子 × entry_atr</span>
          </el-form-item>
          <el-form-item label="拒绝单根脉冲K">
            <el-switch v-model="form.params.enhanced_no_single_pulse" />
            <span class="hint">增强1：要求前一根成交量≥均量×1.2</span>
          </el-form-item>
          <el-form-item label="单笔风险比例">
            <el-input-number v-model="form.params.risk_per_trade" :min="0.001" :max="0.05" :step="0.001" />
            <span class="hint">仓位=资金×比例÷止损距离(0.5%~1%)</span>
          </el-form-item>
          <el-form-item label="单日最大止损">
            <el-input-number v-model="form.params.daily_max_stop" :min="0" :max="10" />
            <span class="hint">达上限当日停止开仓</span>
          </el-form-item>
        </template>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 回测弹窗 -->
    <el-dialog v-model="backtestVisible" title="运行回测" width="500px">
      <el-form label-width="100px">
        <el-form-item label="开始日期">
          <el-date-picker v-model="btStart" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="btEnd" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="backtestVisible = false">取消</el-button>
        <el-button type="primary" @click="runBacktest" :loading="btLoading">运行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import {
  getStrategies, createStrategy, updateStrategy, deleteStrategy,
  activateStrategy, pauseStrategy, runSignals as runSignalsApi,
  executeSignals as execSignalsApi, runBacktest as runBacktestApi,
} from '@/api/strategy'
import { getInstruments as getMarketInstruments } from '@/api/market'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, RefreshLeft } from '@element-plus/icons-vue'

const STRATEGY_TYPE_OPTIONS = [
  { label: '因子综合评分', value: 'factor_composite' },
  { label: '趋势跟踪', value: 'trend_follow' },
  { label: '放量跟随', value: 'volume_breakout' },
]
const STATUS_OPTIONS = [
  { label: '草稿', value: 'draft' },
  { label: '运行中', value: 'active' },
  { label: '已暂停', value: 'paused' },
  { label: '已停止', value: 'stopped' },
]
const DIRECTION_OPTIONS = [
  { label: '只做多', value: 'long' },
  { label: '只做空', value: 'short' },
  { label: '多空双向', value: 'both' },
]

const tableData = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const backtestVisible = ref(false)
const btLoading = ref(false)
const btStart = ref('')
const btEnd = ref('')
const btStrategyId = ref(null)

// 筛选与分页
const filters = ref({ keyword: '', strategy_type: '', inst_type: '', status: '', direction: '' })
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const form = ref({})
const factorsStr = ref('')
const instrumentOptions = ref([])
const instrumentsLoading = ref(false)

const DEFAULT_VOLUME_PARAMS = {
  vol_ma_len: 20,
  vol_ratio: 1.8,
  trend_ma_len: 60,
  atr_len: 14,
  min_atr_factor: 0.0015,
  cooling_min: 3,
  stop_loss_mul: 1.2,
  tp_mode: 'fixed',
  tp_ratio: 1.5,
  trailing_trigger: 0.5,
  trailing_factor: 0.8,
  enhanced_no_single_pulse: false,
  risk_per_trade: 0.01,
  daily_max_stop: 3,
}
const mergeVolumeParams = (raw) => ({ ...DEFAULT_VOLUME_PARAMS, ...(raw || {}) })

const loadInstruments = async (instType, keyword = '') => {
  instrumentsLoading.value = true
  try {
    const params = {}
    if (instType) params.inst_type = instType
    if (keyword) params.keyword = keyword
    params.page_size = 50
    const res = await getMarketInstruments(params)
    const rows = res.results || res || []
    instrumentOptions.value = rows
      .filter(i => i.inst_id)
      .map(i => ({ label: i.inst_id, value: i.inst_id }))
  } catch (e) { ElMessage.error(e.message) }
  instrumentsLoading.value = false
}

const searchInstruments = (query) => {
  loadInstruments(form.value.inst_type || 'SWAP', query)
}

watch(() => form.value.inst_type, (val) => {
  form.value.symbols = []
  loadInstruments(val || 'SWAP')
})

const load = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      ...Object.fromEntries(Object.entries(filters.value).filter(([, v]) => v !== '' && v != null)),
    }
    const res = await getStrategies(params)
    tableData.value = res.results || res
    total.value = res.count ?? (res.results || res).length
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const onSearch = () => { page.value = 1; load() }
const onReset = () => {
  filters.value = { keyword: '', strategy_type: '', inst_type: '', status: '', direction: '' }
  page.value = 1
  load()
}

const openDialog = (row) => {
  if (row) {
    form.value = { ...row, symbols: (row.symbols || []).slice(), params: mergeVolumeParams(row.params) }
    factorsStr.value = (row.factors || []).join(',')
  } else {
    form.value = { strategy_type: 'trend_follow', inst_type: 'SWAP', symbols: [], params: { ...DEFAULT_VOLUME_PARAMS }, bar: '5m', direction: 'both', td_mode: 'cross', leverage: 3, initial_capital: 10000, order_size_pct: 0.1, max_positions: 5, stop_loss_pct: 0.05, take_profit_pct: 0.1, status: 'draft' }

    factorsStr.value = ''
  }
  loadInstruments(form.value.inst_type || 'SWAP')
  dialogVisible.value = true
}

watch(() => form.value.strategy_type, (val) => {
  if (val === 'volume_breakout' && (!form.value.params || Object.keys(form.value.params).length === 0)) {
    form.value.params = { ...DEFAULT_VOLUME_PARAMS }
  }
})

const save = async () => {
  const data = {
    ...form.value,
    factors: factorsStr.value.split(',').map(s => s.trim()).filter(Boolean),
  }
  try {
    if (data.id) { await updateStrategy(data.id, data); ElMessage.success('更新成功') }
    else { await createStrategy(data); ElMessage.success('创建成功') }
    dialogVisible.value = false
    await load()
  } catch (e) { ElMessage.error(e.message) }
}

const activate = async (id) => { await activateStrategy(id); ElMessage.success('已激活'); load() }
const pause = async (id) => { await pauseStrategy(id); ElMessage.success('已暂停'); load() }
const runSignals = async (id) => { await runSignalsApi(id); ElMessage.success('信号已生成'); load() }
const executeSignals = async (id) => {
  try { await execSignalsApi(id); ElMessage.success('信号已执行') }
  catch (e) { ElMessage.error(e.message) }
}

const showBacktest = (row) => {
  btStrategyId.value = row.id
  btStart.value = ''
  btEnd.value = ''
  backtestVisible.value = true
}

const runBacktest = async () => {
  if (!btStart.value || !btEnd.value) { ElMessage.warning('请选择日期'); return }
  btLoading.value = true
  try {
    await runBacktestApi(btStrategyId.value, { start_date: btStart.value, end_date: btEnd.value })
    ElMessage.success('回测已提交')
    backtestVisible.value = false
  } catch (e) { ElMessage.error(e.message) }
  btLoading.value = false
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.filter-bar { margin-top: 16px; }
.filter-bar :deep(.el-card__body) { padding: 16px 16px 0; }
.pager { margin-top: 16px; justify-content: flex-end; display: flex; }
.hint { color: #909399; font-size: 12px; margin-left: 8px; }
</style>
