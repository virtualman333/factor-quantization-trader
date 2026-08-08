<template>
  <div>
    <div class="page-header">
      <h2>策略管理</h2>
      <el-button type="primary" :icon="Plus" @click="openDialog(null)">新建策略</el-button>
    </div>

    <!-- 新手提示 -->
    <el-alert
      v-if="showGuide"
      type="info"
      :closable="true"
      show-icon
      class="guide-alert"
      @close="onGuideClose"
    >
      <template #title>初次使用？先了解策略机制</template>
      <div class="guide-text">
        策略会按 K 线周期自动运行并生成买卖信号。建议先在<term-tip term-key="backtest" />中验证历史表现，
        重点关注<term-tip term-key="max_drawdown" />和<term-tip term-key="sharpe" />，满意后再激活。
        <el-link type="primary" :underline="false" @click="openHelp" style="margin-left:8px">查看新手引导 →</el-link>
      </div>
    </el-alert>

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

    <!-- 进行中的回测任务 -->
    <el-card v-if="activeTasks.length" shadow="never" style="margin-top:16px">
      <template #header>
        <div class="tasks-header">
          <span><el-icon style="margin-right:6px"><Loading /></el-icon>回测任务</span>
          <el-tag size="small" type="warning">{{ activeTasks.length }} 个进行中</el-tag>
        </div>
      </template>
      <el-table :data="activeTasks" size="small" border>
        <el-table-column label="任务ID" width="110">
          <template #default="{ row }">
            <span class="task-id">{{ row.task_id.slice(0, 8) }}…</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.task_type || '回测' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="策略" min-width="130">
          <template #default="{ row }">
            {{ row.result?.strategy_name || row.strategy_name || `策略 #${row.strategy_id}` }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="taskStateType(row.state)">
              {{ taskStateLabel(row.state) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="140">
          <template #default="{ row }">
            <el-progress
              v-if="row.state === 'SUCCESS' || row.state === 'FAILURE'"
              :percentage="100"
              :status="row.state === 'SUCCESS' ? 'success' : 'exception'"
            />
            <el-progress v-else :percentage="loadingProgress" :indeterminate="true" :duration="1" :show-text="false" />
          </template>
        </el-table-column>
        <el-table-column label="结果" min-width="180">
          <template #default="{ row }">
            <span v-if="row.state === 'SUCCESS'" style="color:#67c23a">
              收益 {{ (row.result.total_return * 100).toFixed(2) }}% · 夏普 {{ row.result.sharpe_ratio?.toFixed(2) }} · {{ row.result.total_trades }}笔
            </span>
            <span v-else-if="row.state === 'FAILURE'" style="color:#f56c6c">
              {{ row.result.error || '回测失败' }}
            </span>
            <span v-else style="color:#909399">执行中…</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
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
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button
            v-if="row.status !== 'active'"
            size="small" type="success" @click="activate(row.id)"
          >{{ row.status === 'draft' ? '激活' : '恢复' }}</el-button>
          <el-button v-if="row.status === 'active'" size="small" type="warning" @click="pause(row.id)">暂停</el-button>
          <el-dropdown trigger="click" @command="(cmd) => handleMore(row, cmd)">
            <el-button size="small">更多<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="signals">生成信号</el-dropdown-item>
                <el-dropdown-item command="execute">执行信号</el-dropdown-item>
                <el-dropdown-item command="backtest" divided>回测</el-dropdown-item>
                <el-dropdown-item command="optimize">参数优化</el-dropdown-item>
                <el-dropdown-item command="delete" divided><span style="color:#f56c6c">删除</span></el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
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
        <el-form-item>
          <template #label>策略类型 <term-tip term-key="strategy" /></template>
          <el-select v-model="form.strategy_type" style="width:100%">
            <el-option v-for="o in STRATEGY_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
          <div v-if="currentMeta" class="strategy-desc">{{ currentMeta.description }}</div>
        </el-form-item>
        <el-form-item label="品种类型">
          <el-select v-model="form.inst_type">
            <el-option label="现货" value="SPOT" />
            <el-option label="永续合约" value="SWAP" />
          </el-select>
        </el-form-item>
        <el-form-item label="交易对">
          <instrument-select
            v-model="form.symbols"
            multiple
            allow-create
            collapse-tags
            :inst-type="form.inst_type || 'SWAP'"
            placeholder="搜索选择交易对，可输入自定义"
            width="100%"
          />
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
        <el-form-item>
          <template #label>保证金模式 <term-tip term-key="td_mode" /></template>
          <el-select v-model="form.td_mode">
            <el-option label="现金/现货" value="cash" />
            <el-option label="全仓合约" value="cross" />
            <el-option label="逐仓合约" value="isolated" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <template #label>杠杆倍数 <term-tip term-key="leverage" /></template>
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
        <el-form-item>
          <template #label>止损比例 <term-tip term-key="stop_loss" /></template>
          <el-input-number v-model="form.stop_loss_pct" :min="0.01" :max="0.5" :step="0.01" />
        </el-form-item>
        <el-form-item>
          <template #label>止盈比例 <term-tip term-key="take_profit" /></template>
          <el-input-number v-model="form.take_profit_pct" :min="0.01" :max="1" :step="0.01" />
        </el-form-item>
        <el-form-item v-if="form.strategy_type === 'factor_composite'">
          <template #label>因子列表 <term-tip term-key="factor" /></template>
          <el-input v-model="factorsStr" placeholder="逗号分隔因子名 (momentum,rsi,macd)" />
        </el-form-item>

        <!-- 策略专属参数：根据后端 meta schema 动态渲染 -->
        <template v-if="currentMeta && currentMeta.params.length">
          <el-divider content-position="left">策略参数</el-divider>
          <el-form-item v-for="p in currentMeta.params" :key="p.key" :label="p.label">
            <template v-if="p.type === 'bool'">
              <el-switch v-model="form.params[p.key]" />
              <span class="hint">{{ p.help }}</span>
            </template>
            <template v-else-if="p.type === 'choice'">
              <el-select v-model="form.params[p.key]" style="width:200px">
                <el-option v-for="o in p.options" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
              <span class="hint">{{ p.help }}</span>
            </template>
            <template v-else>
              <el-input-number
                v-model="form.params[p.key]"
                :min="p.min"
                :max="p.max"
                :step="p.step"
                :precision="p.type === 'int' ? 0 : undefined"
              />
              <span class="hint">{{ p.help }}</span>
            </template>
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
        <el-form-item label="手续费率">
          <el-input-number v-model="btFeeRate" :min="0" :max="0.01" :step="0.0005" :precision="4" />
          <span class="hint">单边比例，默认 0.1%</span>
        </el-form-item>
        <el-form-item label="滑点">
          <el-input-number v-model="btSlippage" :min="0" :max="0.01" :step="0.0005" :precision="4" />
          <span class="hint">成交价偏移，默认 0.1%</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="backtestVisible = false">取消</el-button>
        <el-button type="primary" @click="runBacktest" :loading="btLoading">运行</el-button>
      </template>
    </el-dialog>

    <!-- 优化弹窗 -->
    <el-dialog v-model="optVisible" title="策略优化" width="620px">
      <el-tabs v-model="optTab">
        <el-tab-pane label="参数优化（网格搜索）" name="params">
          <el-form label-width="110px">
            <el-form-item label="参数网格">
              <div v-for="(g, idx) in gridRows" :key="idx" class="grid-row">
                <el-input v-model="g.key" placeholder="参数名，如 vol_ratio" style="width:180px" />
                <el-input v-model="g.values" placeholder="取值，逗号分隔，如 1.5,1.8,2.0" style="flex:1" />
                <el-button type="danger" text @click="gridRows.splice(idx, 1)">移除</el-button>
              </div>
              <el-button size="small" type="primary" text @click="addGridRow">+ 添加参数</el-button>
            </el-form-item>
            <el-form-item label="开始日期">
              <el-date-picker v-model="optStart" type="date" value-format="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="结束日期">
              <el-date-picker v-model="optEnd" type="date" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-form>
          <el-button type="primary" :loading="optLoading" @click="runParamOptimize">开始网格搜索</el-button>
          <el-table v-if="optResults.length" :data="optResults" border stripe size="small" style="margin-top:12px" max-height="260">
            <el-table-column label="参数" min-width="160">
              <template #default="{ row }">
                <el-tag v-for="(v, k) in row.params" :key="k" size="small" style="margin-right:4px">{{ k }}={{ v }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="收益" width="90">
              <template #default="{ row }">{{ (row.total_return * 100).toFixed(2) }}%</template>
            </el-table-column>
            <el-table-column label="夏普" width="80">
              <template #default="{ row }">{{ row.sharpe_ratio.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="胜率" width="80">
              <template #default="{ row }">{{ (row.win_rate * 100).toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column label="交易数" width="80">
              <template #default="{ row }">{{ row.total_trades }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="因子权重优化" name="weights">
          <el-form label-width="110px">
            <el-form-item label="开始日期">
              <el-date-picker v-model="wtStart" type="date" value-format="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="结束日期">
              <el-date-picker v-model="wtEnd" type="date" value-format="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="迭代次数">
              <el-input-number v-model="wtIterations" :min="5" :max="50" />
            </el-form-item>
          </el-form>
          <el-button type="primary" :loading="wtLoading" @click="runWeightOptimize">开始权重优化</el-button>
          <div v-if="wtResult" class="wt-result">
            <el-tag v-for="(v, k) in wtResult.weights" :key="k" size="small" style="margin:4px">
              {{ k }}: {{ v }}
            </el-tag>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, inject } from 'vue'
import {
  runSignals as runSignalsApi,
  executeSignals as execSignalsApi, runBacktest as runBacktestApi,
  optimizeParams as optimizeParamsApi, optimizeWeights as optimizeWeightsApi,
  getBacktestTasks, getStrategyMeta,
} from '@/api/strategy'
import InstrumentSelect from '@/components/InstrumentSelect.vue'
import { useStrategyStore } from '@/stores/strategy'
import { useConfirm } from '@/composables/useConfirm'
import { useFormDraft } from '@/composables/useFormDraft'
import { ElMessage } from 'element-plus'
import { Plus, Search, RefreshLeft, Delete, Loading, ArrowDown } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/time'

const strategyStore = useStrategyStore()
const { confirm } = useConfirm()
const { loadDraft, saveDraft, clearDraft, hasDraft } = useFormDraft('strategy_edit', {})
const isNew = ref(true)
const shortcutHelp = inject('shortcutHelp', null)
const showGuide = ref(!localStorage.getItem('strategy_guide_dismissed'))
function openHelp() { shortcutHelp?.open() }
function onGuideClose() { localStorage.setItem('strategy_guide_dismissed', '1'); showGuide.value = false }

// 策略类型与参数元数据（从后端动态获取，新增策略无需改前端）
const strategyMetaList = ref([])
const STRATEGY_TYPE_OPTIONS = computed(() =>
  strategyMetaList.value.map((m) => ({ label: m.name, value: m.code }))
)
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
const btFeeRate = ref(0.001)
const btSlippage = ref(0.001)
const btStrategyId = ref(null)

// 优化相关
const optVisible = ref(false)
const optTab = ref('params')
const optStrategyId = ref(null)
const optStart = ref('')
const optEnd = ref('')
const optLoading = ref(false)
const optResults = ref([])
const gridRows = ref([])
const wtStart = ref('')
const wtEnd = ref('')
const wtIterations = ref(10)
const wtLoading = ref(false)
const wtResult = ref(null)

// 回测任务（异步）
const btTasks = ref([])
const taskPollTimer = ref(null)
const taskPolling = ref(false)

const activeTasks = computed(() =>
  btTasks.value.filter((t) => t.state === 'STARTED' || t.state === 'PENDING' || t.state === 'RECEIVED')
)

const taskStateLabel = (s) => ({
  PENDING: '等待中', RECEIVED: '排队中', STARTED: '执行中',
  SUCCESS: '完成', FAILURE: '失败',
}[s] || s)

const taskStateType = (s) => ({
  PENDING: 'info', RECEIVED: 'warning', STARTED: 'warning',
  SUCCESS: 'success', FAILURE: 'danger',
}[s] || 'info')

const loadingProgress = ref(60)
const loadBtTasks = async () => {
  try {
    const res = await getBacktestTasks()
    const rows = res.results || []
    const prev = btTasks.value
    // 合并策略名
    for (const r of rows) {
      const old = prev.find((p) => p.task_id === r.task_id)
      if (old && !r.result?.strategy_name) r.strategy_name = old.strategy_name
      if (!r.strategy_name && r.strategy_id) {
        const s = tableData.value.find((x) => x.id === r.strategy_id)
        if (s) r.strategy_name = s.name
      }
    }
    btTasks.value = rows
    // 有任务完成时刷新表格（回测结果可能变化）
    if (prev.some((p) => p.state !== 'SUCCESS' && p.state !== 'FAILURE') &&
        rows.every((r) => r.state === 'SUCCESS' || r.state === 'FAILURE')) {
      load()
    }
  } catch { /* 轮询失败忽略 */ }
}

const startTaskPolling = () => {
  stopTaskPolling()
  loadBtTasks()
  taskPollTimer.value = setInterval(loadBtTasks, 3000)
}

const stopTaskPolling = () => {
  if (taskPollTimer.value) {
    clearInterval(taskPollTimer.value)
    taskPollTimer.value = null
  }
}

// 筛选与分页
const filters = ref({ keyword: '', strategy_type: '', inst_type: '', status: '', direction: '' })
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const form = ref({})
const factorsStr = ref('')

// 当前策略类型对应的 meta（含参数 schema）
const currentMeta = computed(() =>
  strategyMetaList.value.find((m) => m.code === form.value.strategy_type)
)
// 根据策略类型获取参数默认值（从 meta schema 动态生成）
const defaultParamsFor = (type) => {
  const meta = strategyMetaList.value.find((m) => m.code === type)
  const defaults = {}
  for (const p of (meta?.params || [])) {
    if (p.default !== undefined && p.default !== null) defaults[p.key] = p.default
  }
  return defaults
}
// 合并用户已保存参数与默认参数
const mergeParams = (type, raw) => ({ ...defaultParamsFor(type), ...(raw || {}) })

const loadMeta = async () => {
  try {
    const res = await getStrategyMeta()
    strategyMetaList.value = res.results || []
  } catch (e) { /* 元数据加载失败时前端保持空列表 */ }
}

watch(() => form.value.inst_type, () => {
  form.value.symbols = []
})

const load = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      ...Object.fromEntries(Object.entries(filters.value).filter(([, v]) => v !== '' && v != null)),
    }
    const { results, count } = await strategyStore.fetchList(params, { force: true })
    tableData.value = results
    total.value = count
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const onSearch = () => { page.value = 1; load() }
const onReset = () => {
  filters.value = { keyword: '', strategy_type: '', inst_type: '', status: '', direction: '' }
  page.value = 1
  load()
}

const showOptimize = (row) => {
  optStrategyId.value = row.id
  optTab.value = 'params'
  optResults.value = []
  wtResult.value = null
  gridRows.value = [{ key: 'vol_ratio', values: '1.5,1.8,2.0' }]
  optStart.value = ''
  optEnd.value = ''
  wtStart.value = ''
  wtEnd.value = ''
  optVisible.value = true
}

const addGridRow = () => { gridRows.value.push({ key: '', values: '' }) }

const buildParamGrid = () => {
  const grid = {}
  for (const g of gridRows.value) {
    if (!g.key || !g.values) continue
    grid[g.key] = g.values.split(',').map(s => s.trim()).filter(Boolean).map(s => {
      const n = Number(s)
      return isNaN(n) ? s : n
    })
  }
  return grid
}

const runParamOptimize = async () => {
  const grid = buildParamGrid()
  if (!Object.keys(grid).length) { ElMessage.warning('请配置参数网格'); return }
  optLoading.value = true
  try {
    const res = await optimizeParamsApi(optStrategyId.value, {
      param_grid: grid, start_date: optStart.value || undefined, end_date: optEnd.value || undefined,
    })
    // 异步任务提交（202），加入任务列表轮询
    if (res.submitted) {
      btTasks.value.unshift({
        task_id: res.task_id,
        strategy_id: optStrategyId.value,
        strategy_name: tableData.value.find((x) => x.id === optStrategyId.value)?.name,
        task_type: '参数优化',
        state: 'PENDING',
        result: {},
        created_at: new Date().toISOString(),
      })
      ElMessage.success('参数优化任务已提交，正在后台执行…')
      startTaskPolling()
    } else {
      optResults.value = res.results || []
      ElMessage.success(`网格搜索完成，共 ${optResults.value.length} 组结果`)
    }
  } catch (e) { ElMessage.error(e.message) }
  optLoading.value = false
}

const runWeightOptimize = async () => {
  wtLoading.value = true
  try {
    const res = await optimizeWeightsApi(optStrategyId.value, {
      start_date: wtStart.value || undefined, end_date: wtEnd.value || undefined,
      iterations: wtIterations.value,
    })
    if (res.submitted) {
      btTasks.value.unshift({
        task_id: res.task_id,
        strategy_id: optStrategyId.value,
        strategy_name: tableData.value.find((x) => x.id === optStrategyId.value)?.name,
        task_type: '权重优化',
        state: 'PENDING',
        result: {},
        created_at: new Date().toISOString(),
      })
      ElMessage.success('权重优化任务已提交，正在后台执行…')
      startTaskPolling()
    } else {
      wtResult.value = res
      ElMessage.success('权重优化完成')
    }
  } catch (e) { ElMessage.error(e.message) }
  wtLoading.value = false
}

const openDialog = (row) => {
  if (row) {
    isNew.value = false
    form.value = { ...row, symbols: (row.symbols || []).slice(), params: mergeParams(row.strategy_type, row.params) }
    factorsStr.value = (row.factors || []).join(',')
  } else {
    isNew.value = true
    const defaultForm = { strategy_type: strategyMetaList.value[0]?.code || 'factor_composite', inst_type: 'SWAP', symbols: [], params: {}, bar: '5m', direction: 'both', td_mode: 'cross', leverage: 3, initial_capital: 10000, order_size_pct: 0.1, max_positions: 5, stop_loss_pct: 0.05, take_profit_pct: 0.1, status: 'draft' }
    defaultForm.params = defaultParamsFor(defaultForm.strategy_type)
    // 恢复未保存的草稿（表单持久化）
    const restored = loadDraft()
    if (restored && Object.keys(restored).length > 1) {
      form.value = { ...defaultForm, ...restored, params: mergeParams(restored.strategy_type || defaultForm.strategy_type, restored.params) }
      factorsStr.value = Array.isArray(restored.factors) ? restored.factors.join(',') : ''
      ElMessage.info('已恢复上次未保存的草稿')
    } else {
      form.value = { ...defaultForm }
      factorsStr.value = ''
    }
  }
  dialogVisible.value = true
}

// 新建模式下自动持久化表单草稿
watch(form, () => {
  if (isNew.value && dialogVisible.value) {
    saveDraft({ ...form.value, factors: factorsStr.value.split(',').map(s => s.trim()).filter(Boolean) })
  }
}, { deep: true })

watch(() => form.value.strategy_type, (val) => {
  if (isNew.value && val) {
    form.value.params = defaultParamsFor(val)
  }
})

const save = async () => {
  const data = {
    ...form.value,
    factors: factorsStr.value.split(',').map(s => s.trim()).filter(Boolean),
  }
  try {
    if (data.id) { await strategyStore.update(data.id, data); ElMessage.success('更新成功') }
    else { await strategyStore.create(data); ElMessage.success('创建成功'); clearDraft() }
    dialogVisible.value = false
    isNew.value = false
    await load()
  } catch (e) { ElMessage.error(e.message) }
}

const activate = async (id) => { await strategyStore.activate(id); ElMessage.success('已激活'); load() }
const pause = async (id) => { await strategyStore.pause(id); ElMessage.success('已暂停'); load() }

const remove = async (row) => {
  const ok = await confirm.deleteStrategy(row.name)
  if (!ok) return
  try {
    await strategyStore.remove(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) { ElMessage.error(e.message) }
}
const runSignals = async (id) => {
  try { await runSignalsApi(id); ElMessage.success('信号已生成'); load() }
  catch (e) { ElMessage.error(e.message) }
}
const executeSignals = async (id) => {
  try { await execSignalsApi(id); ElMessage.success('信号已执行') }
  catch (e) { ElMessage.error(e.message) }
}

const handleMore = (row, cmd) => {
  if (cmd === 'signals') runSignals(row.id)
  else if (cmd === 'execute') executeSignals(row.id)
  else if (cmd === 'backtest') showBacktest(row)
  else if (cmd === 'optimize') showOptimize(row)
  else if (cmd === 'delete') remove(row)
}

const showBacktest = (row) => {
  btStrategyId.value = row.id
  // 默认最近30天
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 30)
  const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  btStart.value = fmt(start)
  btEnd.value = fmt(end)
  backtestVisible.value = true
}

const runBacktest = async () => {
  if (!btStart.value || !btEnd.value) { ElMessage.warning('请选择日期'); return }
  btLoading.value = true
  try {
    const res = await runBacktestApi(btStrategyId.value, {
      start_date: btStart.value, end_date: btEnd.value,
      fee_rate: btFeeRate.value, slippage: btSlippage.value,
    })
    // 异步任务提交成功（202），加入任务列表并轮询
    if (res.submitted) {
      const strategy = tableData.value.find((x) => x.id === btStrategyId.value)
      btTasks.value.unshift({
        task_id: res.task_id,
        strategy_id: res.strategy_id,
        strategy_name: strategy?.name || res.strategy_name,
        state: 'PENDING',
        result: {},
        created_at: new Date().toISOString(),
      })
      ElMessage.success('回测任务已提交，正在后台执行…')
      startTaskPolling()
    } else {
      ElMessage.success('回测完成')
    }
    backtestVisible.value = false
  } catch (e) { ElMessage.error(e.message) }
  btLoading.value = false
}

onMounted(async () => {
  await loadMeta()
  load()
  // 恢复进行中的回测任务轮询
  loadBtTasks().then(() => {
    if (activeTasks.value.length) startTaskPolling()
  })
})

onBeforeUnmount(stopTaskPolling)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.guide-alert { margin-top: 16px; }
.guide-text { font-size: 13px; line-height: 1.8; }
.filter-bar { margin-top: 16px; }
.filter-bar :deep(.el-card__body) { padding: 16px 16px 0; }
.pager { margin-top: 16px; justify-content: flex-end; display: flex; }
.hint { color: #909399; font-size: 12px; margin-left: 8px; }
.strategy-desc { color: #909399; font-size: 12px; line-height: 1.5; margin-top: 4px; }
.tasks-header { display: flex; align-items: center; justify-content: space-between; }
.task-id { font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; color: #909399; }
.grid-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; width: 100%; }
.wt-result { margin-top: 16px; padding: 12px; background: #f5f7fa; border-radius: 6px; }
</style>
