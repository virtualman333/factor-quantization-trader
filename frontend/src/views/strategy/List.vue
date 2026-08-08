<template>
  <div>
    <div class="page-header">
      <div class="header-left">
        <h2>策略管理</h2>
        <span class="subtitle">创建、配置、回测你的量化策略</span>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog(null)">新建策略</el-button>
    </div>

    <!-- 统计概览 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <div class="stat-card total">
          <div class="stat-icon"><el-icon><Files /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value">{{ total }}</div>
            <div class="stat-label">策略总数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card running">
          <div class="stat-icon"><el-icon><VideoPlay /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value">{{ runningCount }}</div>
            <div class="stat-label">运行中</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card paused">
          <div class="stat-icon"><el-icon><VideoPause /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value">{{ pausedCount }}</div>
            <div class="stat-label">已暂停</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card draft">
          <div class="stat-icon"><el-icon><EditPen /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value">{{ draftCount }}</div>
            <div class="stat-label">草稿</div>
          </div>
        </div>
      </el-col>
    </el-row>

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
        策略会按 K 线周期自动运行并生成买卖信号。建议先回测验证历史表现，
        重点关注最大回撤和夏普比率，满意后再激活。
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
          <el-select v-model="filters.strategy_type" placeholder="全部" clearable @change="onSearch" style="width:150px">
            <el-option v-for="o in STRATEGY_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
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

    <!-- 进行中的任务 -->
    <el-card v-if="activeTasks.length" shadow="never" style="margin-top:16px">
      <template #header>
        <div class="tasks-header">
          <span><el-icon style="margin-right:6px"><Loading /></el-icon>后台任务</span>
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
            <el-tag size="small" :type="taskStateType(row.state)">{{ taskStateLabel(row.state) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="结果" min-width="200">
          <template #default="{ row }">
            <span v-if="row.state === 'SUCCESS'" style="color:#67c23a">
              收益 {{ (row.result.total_return * 100).toFixed(2) }}% · 夏普 {{ row.result.sharpe_ratio?.toFixed(2) }} · {{ row.result.total_trades }}笔
            </span>
            <span v-else-if="row.state === 'FAILURE'" style="color:#f56c6c">
              {{ row.result.error || '任务失败' }}
            </span>
            <span v-else style="color:#909399">
              <el-progress :percentage="80" :indeterminate="true" :duration="1" :show-text="false" style="width:120px" />执行中…
            </span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 策略表格 -->
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column label="策略" min-width="180">
        <template #default="{ row }">
          <div class="strategy-cell">
            <div class="s-name">{{ row.name }}</div>
            <div class="s-tags">
              <el-tag size="small" type="primary" effect="plain">{{ row.strategy_type_display }}</el-tag>
              <el-tag size="small" effect="plain">{{ row.bar }}</el-tag>
              <el-tag size="small" :type="row.direction === 'long' ? 'success' : row.direction === 'short' ? 'danger' : 'info'" effect="plain">
                {{ row.direction_display }}
              </el-tag>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="交易对" min-width="160">
        <template #default="{ row }">
          <div class="symbol-tags">
            <el-tag v-for="s in (row.symbols || []).slice(0, 3)" :key="s" size="small" effect="plain" style="margin:2px 4px 2px 0">
              {{ s }}
            </el-tag>
            <el-tag v-if="(row.symbols || []).length > 3" size="small" type="info">+{{ row.symbols.length - 3 }}</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : row.status === 'paused' ? 'warning' : 'info'" size="small">
            {{ row.status_display }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最新回测" min-width="170">
        <template #default="{ row }">
          <template v-if="row.latest_backtest">
            <div class="bt-cell">
              <span :style="{ color: Number(row.latest_backtest.total_return) >= 0 ? '#67c23a' : '#f56c6c', fontWeight: 600 }">
                {{ (Number(row.latest_backtest.total_return) * 100).toFixed(2) }}%
              </span>
              <span class="bt-sub">夏普 {{ Number(row.latest_backtest.sharpe_ratio || 0).toFixed(2) }} · {{ row.latest_backtest.total_trades }}笔</span>
            </div>
          </template>
          <span v-else class="bt-empty">尚未回测</span>
        </template>
      </el-table-column>
      <el-table-column prop="initial_capital" label="初始资金" width="110" align="right">
        <template #default="{ row }">{{ Number(row.initial_capital).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column prop="order_size_pct" label="仓位" width="80">
        <template #default="{ row }">{{ (Number(row.order_size_pct) * 100).toFixed(0) }}%</template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
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
                <el-dropdown-item command="backtest">运行回测</el-dropdown-item>
                <el-dropdown-item command="optimize">参数优化</el-dropdown-item>
                <el-dropdown-item command="signals" divided>生成信号</el-dropdown-item>
                <el-dropdown-item command="execute">执行信号</el-dropdown-item>
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
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑策略' : '新建策略'" width="640px" top="6vh">
      <el-form :model="form" label-width="110px" @submit.prevent>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="名称" required>
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item>
              <template #label>策略类型 <term-tip term-key="strategy" /></template>
              <el-select v-model="form.strategy_type" style="width:100%">
                <el-option v-for="o in STRATEGY_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item v-if="currentMeta" label="说明">
          <span class="strategy-desc">{{ currentMeta.description }}</span>
        </el-form-item>
        <el-form-item label="交易对" required>
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
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="品种类型">
              <el-select v-model="form.inst_type" style="width:100%">
                <el-option label="现货" value="SPOT" />
                <el-option label="永续合约" value="SWAP" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="K线周期">
              <el-select v-model="form.bar" style="width:100%">
                <el-option v-for="b in ['1m','5m','15m','30m','1H','4H','1D','1W']" :key="b" :label="b" :value="b" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="方向">
              <el-select v-model="form.direction" style="width:100%">
                <el-option label="做多" value="long" />
                <el-option label="做空" value="short" />
                <el-option label="双向" value="both" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item>
              <template #label>保证金模式 <term-tip term-key="td_mode" /></template>
              <el-select v-model="form.td_mode" style="width:100%">
                <el-option label="现金/现货" value="cash" />
                <el-option label="全仓合约" value="cross" />
                <el-option label="逐仓合约" value="isolated" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item>
              <template #label>杠杆 <term-tip term-key="leverage" /></template>
              <el-input-number v-model="form.leverage" :min="1" :max="100" :step="1" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="初始资金">
              <el-input-number v-model="form.initial_capital" :min="0" :step="1000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="仓位比例">
              <el-input-number v-model="form.order_size_pct" :min="0.01" :max="1" :step="0.05" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大持仓">
              <el-input-number v-model="form.max_positions" :min="1" :max="20" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item>
              <template #label>止损 <term-tip term-key="stop_loss" /></template>
              <el-input-number v-model="form.stop_loss_pct" :min="0.01" :max="0.5" :step="0.01" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item>
              <template #label>止盈 <term-tip term-key="take_profit" /></template>
              <el-input-number v-model="form.take_profit_pct" :min="0.01" :max="1" :step="0.01" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item v-if="form.strategy_type === 'factor_composite'">
          <template #label>因子列表 <term-tip term-key="factor" /></template>
          <el-input v-model="factorsStr" placeholder="逗号分隔因子名 (momentum,rsi,macd)" />
        </el-form-item>

        <!-- 策略专属参数 -->
        <template v-if="currentMeta && currentMeta.params.length">
          <el-divider content-position="left">策略参数</el-divider>
          <el-row :gutter="16">
            <el-col :span="12" v-for="p in currentMeta.params" :key="p.key">
              <el-form-item :label="p.label" style="margin-bottom:14px">
                <template v-if="p.type === 'bool'">
                  <el-switch v-model="form.params[p.key]" />
                  <span class="hint">{{ p.help }}</span>
                </template>
                <template v-else-if="p.type === 'choice'">
                  <el-select v-model="form.params[p.key]" style="width:100%">
                    <el-option v-for="o in p.options" :key="o.value" :label="o.label" :value="o.value" />
                  </el-select>
                </template>
                <template v-else>
                  <el-input-number
                    v-model="form.params[p.key]"
                    :min="p.min"
                    :max="p.max"
                    :step="p.step"
                    :precision="p.type === 'int' ? 0 : undefined"
                    style="width:100%"
                  />
                </template>
              </el-form-item>
            </el-col>
          </el-row>
        </template>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 回测弹窗 -->
    <StrategyBacktestDialog
      v-model="backtestVisible"
      :strategy-id="btStrategyId"
      :strategy-name="btStrategyName"
      @submit="submitBacktest"
    />

    <!-- 优化弹窗 -->
    <StrategyOptimizeDialog
      v-model="optVisible"
      :strategy-id="optStrategyId"
      @submit-params="submitParamOptimize"
      @submit-weights="submitWeightOptimize"
    />
  </div>
</template>

<script setup>
defineOptions({ name: 'StrategyList' })
import { ref, computed, onMounted, onBeforeUnmount, onActivated, watch, inject } from 'vue'
import {
  runSignals as runSignalsApi,
  executeSignals as execSignalsApi,
  runBacktest as runBacktestApi,
  optimizeParams as optimizeParamsApi,
  optimizeWeights as optimizeWeightsApi,
  getBacktestTasks, getStrategyMeta,
} from '@/api/strategy'
import InstrumentSelect from '@/components/InstrumentSelect.vue'
import StrategyBacktestDialog from '@/components/strategy/StrategyBacktestDialog.vue'
import StrategyOptimizeDialog from '@/components/strategy/StrategyOptimizeDialog.vue'
import { useStrategyStore } from '@/stores/strategy'
import { useConfirm } from '@/composables/useConfirm'
import { useFormDraft } from '@/composables/useFormDraft'
import { ElMessage } from 'element-plus'
import { Plus, Search, RefreshLeft, ArrowDown } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/time'

const strategyStore = useStrategyStore()
const { confirm } = useConfirm()
const { loadDraft, saveDraft, clearDraft } = useFormDraft('strategy_edit', {})
const isNew = ref(true)
const shortcutHelp = inject('shortcutHelp', null)
const showGuide = ref(!localStorage.getItem('strategy_guide_dismissed'))
function openHelp() { shortcutHelp?.open() }
function onGuideClose() { localStorage.setItem('strategy_guide_dismissed', '1'); showGuide.value = false }

// 策略类型与参数元数据（从后端动态获取）
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
const btStrategyId = ref(null)
const btStrategyName = ref('')
const optVisible = ref(false)
const optStrategyId = ref(null)

// 回测任务（异步）
const btTasks = ref([])
const taskPollTimer = ref(null)

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

const loadBtTasks = async () => {
  try {
    const res = await getBacktestTasks()
    const rows = res.results || []
    const prev = btTasks.value
    for (const r of rows) {
      const old = prev.find((p) => p.task_id === r.task_id)
      if (old && !r.result?.strategy_name) r.strategy_name = old.strategy_name
      if (!r.strategy_name && r.strategy_id) {
        const s = tableData.value.find((x) => x.id === r.strategy_id)
        if (s) r.strategy_name = s.name
      }
    }
    btTasks.value = rows
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
const filters = ref({ keyword: '', strategy_type: '', status: '', direction: '' })
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const runningCount = computed(() => tableData.value.filter((s) => s.status === 'active').length)
const pausedCount = computed(() => tableData.value.filter((s) => s.status === 'paused').length)
const draftCount = computed(() => tableData.value.filter((s) => s.status === 'draft').length)

const form = ref({})
const factorsStr = ref('')

const currentMeta = computed(() =>
  strategyMetaList.value.find((m) => m.code === form.value.strategy_type)
)

const defaultParamsFor = (type) => {
  const meta = strategyMetaList.value.find((m) => m.code === type)
  const defaults = {}
  for (const p of (meta?.params || [])) {
    if (p.default !== undefined && p.default !== null) defaults[p.key] = p.default
  }
  return defaults
}

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
  filters.value = { keyword: '', strategy_type: '', status: '', direction: '' }
  page.value = 1
  load()
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
  btStrategyName.value = row.name
  backtestVisible.value = true
}

const submitBacktest = async (payload) => {
  const res = await runBacktestApi(btStrategyId.value, payload)
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
}

const showOptimize = (row) => {
  optStrategyId.value = row.id
  optVisible.value = true
}

const submitParamOptimize = async (payload) => {
  const res = await optimizeParamsApi(optStrategyId.value, payload)
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
  }
  return res
}

const submitWeightOptimize = async (payload) => {
  const res = await optimizeWeightsApi(optStrategyId.value, payload)
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
  }
  return res
}

onMounted(async () => {
  await loadMeta()
  load()
  loadBtTasks().then(() => {
    if (activeTasks.value.length) startTaskPolling()
  })
})

// 多 tab 缓存后重新激活：刷新列表数据
onActivated(() => {
  if (!loading.value) load()
})

onBeforeUnmount(stopTaskPolling)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.header-left { display: flex; align-items: baseline; gap: 12px; }
.subtitle { color: #909399; font-size: 13px; }
.stats-row { margin-top: 16px; }
.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border-radius: 8px;
  background: var(--app-header-bg);
  border: 1px solid var(--app-header-border);
  transition: transform .2s, box-shadow .2s;
}
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,.08); }
.stat-icon {
  width: 44px; height: 44px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
}
.total .stat-icon { background: #ecf5ff; color: #409eff; }
.running .stat-icon { background: #f0f9eb; color: #67c23a; }
.paused .stat-icon { background: #fdf6ec; color: #e6a23c; }
.draft .stat-icon { background: #f4f4f5; color: #909399; }
.stat-value { font-size: 22px; font-weight: 700; }
.stat-label { color: #909399; font-size: 12px; margin-top: 2px; }
.guide-alert { margin-top: 16px; }
.guide-text { font-size: 13px; line-height: 1.8; }
.filter-bar { margin-top: 16px; }
.filter-bar :deep(.el-card__body) { padding: 16px 16px 0; }
.pager { margin-top: 16px; justify-content: flex-end; display: flex; }
.hint { color: #909399; font-size: 12px; margin-left: 8px; }
.strategy-desc { color: #909399; font-size: 12px; line-height: 1.5; }
.tasks-header { display: flex; align-items: center; justify-content: space-between; }
.task-id { font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; color: #909399; }
.strategy-cell { display: flex; flex-direction: column; gap: 4px; }
.s-name { font-weight: 600; }
.s-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.symbol-tags { display: flex; flex-wrap: wrap; }
.bt-cell { display: flex; flex-direction: column; gap: 2px; }
.bt-sub { color: #909399; font-size: 12px; }
.bt-empty { color: #c0c4cc; font-size: 12px; }
</style>
