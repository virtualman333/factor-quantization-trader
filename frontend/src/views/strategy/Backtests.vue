<template>
  <div>
    <div class="page-header">
      <div class="header-left">
        <h2>回测结果</h2>
        <span class="subtitle">验证策略历史表现，评估风险与收益</span>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <!-- 统计概览 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon blue"><el-icon><Histogram /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value">{{ total }}</div>
            <div class="stat-label">回测总数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon green"><el-icon><TrendCharts /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value" :style="{ color: avgReturn >= 0 ? '#67c23a' : '#f56c6c' }">{{ pct(avgReturn, 1) }}%</div>
            <div class="stat-label">平均收益</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon orange"><el-icon><DataLine /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value">{{ bestReturnStrategy || '--' }}</div>
            <div class="stat-label">最佳策略</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon purple"><el-icon><Odometer /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value">{{ winBacktestCount }}/{{ total || 0 }}</div>
            <div class="stat-label">盈利回测</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-bar">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="策略">
          <el-select v-model="filterStrategy" placeholder="全部策略" clearable filterable style="width:200px" @change="onFilterChange">
            <el-option v-for="s in strategyOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="结果">
          <el-select v-model="filterResult" placeholder="全部" clearable style="width:120px" @change="onFilterChange">
            <el-option label="盈利" value="profit" />
            <el-option label="亏损" value="loss" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Refresh" @click="load">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="pagedData" v-loading="loading" border stripe style="margin-top:16px" @row-click="showDetail">
      <el-table-column label="策略" min-width="140">
        <template #default="{ row }">
          <div class="strategy-cell">
            <span class="s-name">{{ row.strategy_name }}</span>
            <span class="s-date">{{ fmtDate(row.start_date) }} ~ {{ fmtDate(row.end_date) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="总收益率" width="120">
        <template #header>
          <span>总收益率</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>(最终资金 - 初始资金) / 初始资金</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          <div class="return-cell">
            <span class="return-value" :style="{ color: pctNum(row.total_return) >= 0 ? '#67c23a' : '#f56c6c' }">
              {{ pct(row.total_return) }}%
            </span>
            <span class="capital-sub">{{ fmtNum(row.initial_capital) }} → {{ fmtNum(row.final_capital) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="夏普比" width="100" align="center">
        <template #default="{ row }">{{ row.sharpe_ratio != null ? Number(row.sharpe_ratio).toFixed(2) : '--' }}</template>
      </el-table-column>
      <el-table-column label="最大回撤" width="110">
        <template #default="{ row }">
          <span style="color:#f56c6c">{{ pct(row.max_drawdown) }}%</span>
        </template>
      </el-table-column>
      <el-table-column label="胜率" width="90">
        <template #default="{ row }">{{ pct(row.win_rate, 1) }}%</template>
      </el-table-column>
      <el-table-column label="盈亏比" width="90" align="center">
        <template #default="{ row }">{{ row.profit_factor != null ? Number(row.profit_factor).toFixed(2) : '--' }}</template>
      </el-table-column>
      <el-table-column label="交易次数" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.total_trades }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="160">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right" align="center">
        <template #default="{ row }">
          <el-button size="small" text type="primary" :icon="View" @click.stop="showDetail(row)">详情</el-button>
          <el-button size="small" text type="success" :icon="Histogram" @click.stop="quickViewOnKline(row)">K线</el-button>
          <el-button size="small" text type="info" :icon="Download" @click.stop="exportReport(row)">导出</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="filteredData.length"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
      />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" width="980px" top="5vh" :close-on-click-modal="false">
      <template #header>
        <div class="detail-header">
          <span>回测详情 - {{ selected?.strategy_name }}</span>
          <div class="detail-actions">
            <el-button size="small" type="success" :icon="Histogram" @click="viewOnKline">在K线图查看买卖点</el-button>
            <el-button size="small" type="primary" :icon="DataLine" @click="runMonteCarlo" :loading="mcLoading">蒙特卡洛模拟</el-button>
            <el-button size="small" :icon="Download" @click="exportReport(selected)">导出报告</el-button>
          </div>
        </div>
      </template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="核心指标" name="metrics">
          <el-row :gutter="16">
            <el-col :span="6" v-for="m in metrics" :key="m.label" style="margin-bottom:14px">
              <div class="metric-card" :style="{ borderTopColor: m.color }">
                <div class="metric-label">
                  {{ m.label }}
                  <el-tooltip v-if="m.tip" placement="top" :show-after="300">
                    <template #content>{{ m.tip }}</template>
                    <el-icon class="tip-inline"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </div>
                <div class="metric-value" :style="{ color: m.color }">{{ m.value }}</div>
              </div>
            </el-col>
          </el-row>
          <el-card>
            <template #header>
              <div>
                权益曲线
                <el-tag size="small" style="margin-left:8px" type="info">手续费率 {{ pct(selected?.fee_rate) }}%</el-tag>
                <el-tag size="small" style="margin-left:4px" type="warning">滑点 {{ pct(selected?.slippage) }}%</el-tag>
              </div>
            </template>
            <v-chart :option="chartOption" style="height:320px" autoresize />
          </el-card>
        </el-tab-pane>
        <el-tab-pane label="交易明细" name="trades">
          <el-table :data="selected?.trade_detail || []" border stripe size="small" max-height="480">
            <el-table-column prop="timestamp" label="时间" width="170">
              <template #default="{ row }">{{ fmtDateTime(row.timestamp) }}</template>
            </el-table-column>
            <el-table-column prop="symbol" label="品种" width="130" />
            <el-table-column prop="action" label="方向" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.action === 'buy' ? 'success' : 'danger'">
                  {{ row.action === 'buy' ? '买入' : '卖出' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="price" label="价格" width="120" align="right">
              <template #default="{ row }">{{ fmtNum(row.price) }}</template>
            </el-table-column>
            <el-table-column prop="amount" label="金额" width="130" align="right">
              <template #default="{ row }">{{ fmtNum(row.amount) }}</template>
            </el-table-column>
            <el-table-column prop="fee" label="手续费" width="110" align="right">
              <template #default="{ row }">{{ fmtNum(row.fee) }}</template>
            </el-table-column>
            <el-table-column prop="pnl" label="盈亏" width="130" align="right">
              <template #default="{ row }">
                <span v-if="row.pnl !== undefined && row.pnl !== null" :style="{ color: Number(row.pnl) >= 0 ? '#67c23a' : '#f56c6c' }">{{ Number(row.pnl).toFixed(2) }}</span>
                <span v-else>--</span>
              </template>
            </el-table-column>
            <el-table-column prop="capital" label="权益" width="140" align="right">
              <template #default="{ row }">{{ fmtNum(row.capital) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="蒙特卡洛" name="montecarlo">
          <template v-if="mcResult">
            <el-alert
              title="蒙特卡洛模拟：把历史交易打乱顺序重新组合 N 次，观察收益/回撤的可能分布，评估策略稳健性。"
              type="info" :closable="false" show-icon style="margin-bottom:16px"
            />
            <el-descriptions :column="3" border size="small">
              <el-descriptions-item label="最大回撤(中位数)">{{ pct(mcResult.max_drawdown?.median) }}%</el-descriptions-item>
              <el-descriptions-item label="最大回撤(P95)">{{ pct(mcResult.max_drawdown?.p95) }}%</el-descriptions-item>
              <el-descriptions-item label="最大回撤(P99)">{{ pct(mcResult.max_drawdown?.p99) }}%</el-descriptions-item>
              <el-descriptions-item label="收益(中位数)">{{ pct(mcResult.total_return?.median) }}%</el-descriptions-item>
              <el-descriptions-item label="收益(P5)">{{ pct(mcResult.total_return?.p5) }}%</el-descriptions-item>
              <el-descriptions-item label="收益(P95)">{{ pct(mcResult.total_return?.p95) }}%</el-descriptions-item>
            </el-descriptions>
            <v-chart :option="mcChartOption" style="height:300px;margin-top:16px" autoresize />
          </template>
          <el-empty v-else description="点击右上角「蒙特卡洛模拟」开始分析">
            <el-button type="primary" :icon="DataLine" @click="runMonteCarlo" :loading="mcLoading">开始模拟</el-button>
          </el-empty>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'Backtests' })
import { ref, computed, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import {
  getBacktests, getBacktestDetail,
  runBacktestMonteCarlo, exportBacktestResultReport,
} from '@/api/strategy'
import { ElMessage } from 'element-plus'
import {
  Refresh, View, Download, QuestionFilled, Histogram, DataLine,
} from '@element-plus/icons-vue'
import { formatDate, formatDateTime } from '@/utils/time'

const router = useRouter()
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([LineChart, BarChart, TitleComponent, TooltipComponent, GridComponent, CanvasRenderer])

// ========== 状态 ==========
const allData = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const selected = ref(null)
const activeTab = ref('metrics')
const mcLoading = ref(false)
const mcResult = ref(null)

const page = ref(1)
const pageSize = ref(20)

const filterStrategy = ref(null)
const filterResult = ref('')

// 策略选项（去重）
const strategyOptions = computed(() => {
  const seen = new Map()
  for (const r of allData.value) {
    if (!seen.has(r.strategy_id) && r.strategy_name) {
      seen.set(r.strategy_id, { id: r.strategy_id, name: r.strategy_name })
    }
  }
  return [...seen.values()]
})

const filteredData = computed(() => {
  let rows = allData.value
  if (filterStrategy.value != null && filterStrategy.value !== '') {
    rows = rows.filter((r) => r.strategy_id === filterStrategy.value)
  }
  if (filterResult.value === 'profit') rows = rows.filter((r) => Number(r.total_return) > 0)
  if (filterResult.value === 'loss') rows = rows.filter((r) => Number(r.total_return) <= 0)
  return rows
})

const pagedData = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredData.value.slice(start, start + pageSize.value)
})

const total = computed(() => filteredData.value.length)

// 统计概览
const avgReturn = computed(() => {
  if (!allData.value.length) return 0
  return allData.value.reduce((s, r) => s + Number(r.total_return || 0), 0) / allData.value.length
})
const bestReturnStrategy = computed(() => {
  if (!allData.value.length) return null
  const best = [...allData.value].sort((a, b) => Number(b.total_return || 0) - Number(a.total_return || 0))[0]
  return best.total_return > 0 ? best.strategy_name : null
})
const winBacktestCount = computed(() =>
  allData.value.filter((r) => Number(r.total_return) > 0).length
)

const onFilterChange = () => { page.value = 1 }

// ========== 格式化辅助 ==========
function pctNum(v) {
  if (v === null || v === undefined || v === '') return 0
  const n = parseFloat(v)
  if (isNaN(n)) return 0
  return n * 100
}
function pct(v, digits = 2) {
  return pctNum(v).toFixed(digits)
}
function fmtNum(v, digits = 2) {
  if (v === null || v === undefined || v === '') return '--'
  const n = parseFloat(v)
  if (isNaN(n)) return '--'
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}
function fmtDate(v) { return formatDate(v) }
function fmtDateTime(v) { return formatDateTime(v) }

// ========== 派生数据 ==========
const metrics = computed(() => {
  if (!selected.value) return []
  const d = selected.value
  const totalReturn = pctNum(d.total_return)
  const annualReturn = pctNum(d.annual_return)
  const maxDD = pctNum(d.max_drawdown)
  const winRate = pctNum(d.win_rate)
  return [
    { label: '总收益率', value: `${totalReturn.toFixed(2)}%`, color: totalReturn >= 0 ? '#67c23a' : '#f56c6c', tip: '整个回测区间的累计收益率' },
    { label: '年化收益率', value: `${annualReturn.toFixed(2)}%`, color: '#409eff', tip: '把区间收益率折算成一年的收益率' },
    { label: '夏普比率', value: d.sharpe_ratio != null ? Number(d.sharpe_ratio).toFixed(2) : '--', color: '#409eff', tip: '承担单位风险获得的超额收益，>1 较好' },
    { label: '最大回撤', value: `${maxDD.toFixed(2)}%`, color: '#f56c6c', tip: '权益从峰值跌到谷底的最坏百分比' },
    { label: '胜率', value: `${winRate.toFixed(1)}%`, color: '#67c23a', tip: '盈利交易次数 / 总交易次数' },
    { label: '盈亏比', value: d.profit_factor != null ? Number(d.profit_factor).toFixed(2) : '--', color: '#409eff', tip: '平均盈利 ÷ 平均亏损的绝对值' },
    { label: '交易次数', value: d.total_trades ?? '--', color: '#606266', tip: '回测期间触发的买卖总次数' },
    { label: '初始→最终资金', value: `${fmtNum(d.initial_capital)} → ${fmtNum(d.final_capital)}`, color: '#909399', tip: '回测开始与结束时的账户权益' },
  ]
})

const mcChartOption = computed(() => {
  const dds = mcResult.value?.max_drawdowns_sample || []
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params[0]
        if (!p) return ''
        return `第 ${p.axisValue} 次模拟<br/>最大回撤: ${(Number(p.value) * 100).toFixed(2)}%`
      },
    },
    grid: { left: 70, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: dds.map((_, i) => i + 1) },
    yAxis: { type: 'value', axisLabel: { formatter: (v) => (v * 100).toFixed(0) + '%' } },
    series: [{
      name: '最大回撤分布', type: 'bar', data: dds,
      itemStyle: { color: '#f56c6c' },
    }],
  }
})

const chartOption = computed(() => {
  const curve = selected.value?.equity_curve || []
  return {
    title: { text: '权益曲线', left: 'center' },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params[0]
        if (!p) return ''
        const ts = curve[p.dataIndex]?.[0] || ''
        return `${fmtDateTime(ts)}<br/>权益: ${Number(p.value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
      },
    },
    grid: { left: 90, right: 20, bottom: 50 },
    xAxis: {
      type: 'category',
      data: curve.map(d => d[0]),
      axisLabel: {
        rotate: 30,
        formatter: (v) => {
          const d = new Date(v)
          if (isNaN(d.getTime())) return String(v).slice(5, 10)
          return `${d.getMonth() + 1}/${d.getDate()}`
        },
      },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: {
        formatter: (v) => Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 }),
      },
    },
    series: [{
      data: curve.map(d => d[1]),
      type: 'line',
      smooth: true,
      showSymbol: false,
      areaStyle: { opacity: 0.15, color: '#409eff' },
      itemStyle: { color: '#409eff' },
      lineStyle: { width: 2 },
    }],
  }
})

// ========== 业务方法 ==========
const load = async () => {
  loading.value = true
  try {
    const res = await getBacktests({ page: 1, page_size: 200 })
    if (res && Array.isArray(res.results)) {
      allData.value = res.results
    } else if (Array.isArray(res)) {
      allData.value = res
    } else {
      allData.value = []
    }
  } catch (e) { ElMessage.error(e.message || '加载回测列表失败') }
  loading.value = false
}

const showDetail = async (row) => {
  selected.value = row
  mcResult.value = null
  activeTab.value = 'metrics'
  if (row.monte_carlo && row.monte_carlo.status === 'success' && row.monte_carlo.result) {
    mcResult.value = row.monte_carlo.result
  }
  detailVisible.value = true
  try {
    const full = await getBacktestDetail(row.id)
    selected.value = { ...row, ...full }
    if (full.monte_carlo && full.monte_carlo.status === 'success' && full.monte_carlo.result) {
      mcResult.value = full.monte_carlo.result
    }
  } catch (e) { /* 列表数据已够用，不报错 */ }
}

const guessSymbol = (row) => {
  const fromTrades = row.trade_detail?.find(t => t.symbol)?.symbol
  if (fromTrades) return fromTrades
  const symbols = row.strategy?.symbols
  if (Array.isArray(symbols) && symbols.length) return symbols[0]
  return ''
}

const viewOnKline = () => {
  const d = selected.value
  if (!d) return
  router.push({
    path: '/market/klines',
    query: { backtest_id: d.id, inst_id: guessSymbol(d) },
  })
}

const quickViewOnKline = (row) => {
  router.push({
    path: '/market/klines',
    query: { backtest_id: row.id, inst_id: guessSymbol(row) },
  })
}

const runMonteCarlo = async () => {
  const btId = selected.value?.id
  if (!btId) return
  mcLoading.value = true
  try {
    const res = await runBacktestMonteCarlo(btId, { n_simulations: 1000 })
    if (res.submitted) {
      ElMessage.info('蒙特卡洛模拟已提交后台执行，请稍候重新打开详情查看结果')
    } else if (res.from_cache) {
      mcResult.value = res
      activeTab.value = 'montecarlo'
      ElMessage.success('已加载缓存结果')
    } else {
      mcResult.value = res
      activeTab.value = 'montecarlo'
      ElMessage.success('蒙特卡洛模拟完成')
    }
  } catch (e) { ElMessage.error(e.message || '蒙特卡洛模拟失败') }
  mcLoading.value = false
}

const exportReport = async (row) => {
  if (!row) return
  try {
    const res = await exportBacktestResultReport(row.id)
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    const safeName = (row.strategy_name || 'strategy').replace(/[\\/:*?"<>|]/g, '_')
    a.download = `backtest_${safeName}_${row.id}.html`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) { ElMessage.error(e.message || '导出报告失败') }
}

onMounted(load)
// 多 tab 缓存后重新激活时刷新数据
onActivated(() => {
  if (allData.value.length === 0) load()
})
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
.stat-icon.blue { background: #ecf5ff; color: #409eff; }
.stat-icon.green { background: #f0f9eb; color: #67c23a; }
.stat-icon.orange { background: #fdf6ec; color: #e6a23c; }
.stat-icon.purple { background: #f5f0ff; color: #909399; }
.stat-value { font-size: 22px; font-weight: 700; }
.stat-label { color: #909399; font-size: 12px; margin-top: 2px; }
.filter-bar { margin-top: 16px; }
.filter-bar :deep(.el-card__body) { padding: 16px 16px 0; }
.strategy-cell { display: flex; flex-direction: column; gap: 2px; }
.s-name { font-weight: 600; }
.s-date { color: #909399; font-size: 12px; }
.return-cell { display: flex; flex-direction: column; gap: 2px; }
.return-value { font-weight: 600; }
.capital-sub { color: #909399; font-size: 12px; }
.tip-inline { color: #909399; font-size: 13px; margin-left: 4px; vertical-align: middle; cursor: help; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
.detail-header { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.detail-actions { display: flex; gap: 8px; }
.metric-card {
  border: 1px solid var(--app-header-border);
  border-top: 3px solid transparent;
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--app-header-bg);
}
.metric-label { font-size: 12px; color: #909399; margin-bottom: 8px; display: flex; align-items: center; }
.metric-value { font-size: 20px; font-weight: bold; }
</style>
