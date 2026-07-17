<template>
  <div>
    <div class="page-header">
      <h2>策略管理</h2>
      <el-button type="primary" :icon="Plus" @click="openDialog(null)">新建策略</el-button>
    </div>
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
  getInstruments,
} from '@/api/strategy'
import { ElMessage, ElMessageBox } from 'element-plus'

const tableData = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const backtestVisible = ref(false)
const btLoading = ref(false)
const btStart = ref('')
const btEnd = ref('')
const btStrategyId = ref(null)

const form = ref({})
const factorsStr = ref('')
const instrumentOptions = ref([])
const instrumentsLoading = ref(false)

const loadInstruments = async (instType, keyword = '') => {
  instrumentsLoading.value = true
  try {
    const res = await getInstruments(instType)
    let items = (res.instruments || []).filter(i => i.value)
    if (keyword) {
      const k = keyword.toUpperCase()
      items = items.filter(i => i.label.toUpperCase().includes(k))
    }
    instrumentOptions.value = items
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
    const res = await getStrategies()
    tableData.value = res.results || res
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const openDialog = (row) => {
  if (row) {
    form.value = { ...row, symbols: (row.symbols || []).slice() }
    factorsStr.value = (row.factors || []).join(',')
  } else {
    form.value = { strategy_type: 'trend_follow', inst_type: 'SWAP', symbols: [], bar: '5m', direction: 'both', td_mode: 'cross', leverage: 3, initial_capital: 10000, order_size_pct: 0.1, max_positions: 5, stop_loss_pct: 0.05, take_profit_pct: 0.1, status: 'draft' }

    factorsStr.value = ''
  }
  loadInstruments(form.value.inst_type || 'SWAP')
  dialogVisible.value = true
}

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
</style>
