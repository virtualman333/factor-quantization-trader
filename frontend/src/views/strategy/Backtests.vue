<template>
  <div>
    <div class="page-header">
      <div class="title-wrap">
        <h2>回测结果</h2>
        <el-tooltip placement="right" :show-after="300">
          <template #content>
            <div style="max-width:260px;line-height:1.6">
              <div><b>回测是什么？</b></div>
              <div>用历史行情数据模拟策略表现，验证策略是否能在实盘盈利。建议先用回测确认策略逻辑，再谨慎用于实盘。</div>
            </div>
          </template>
          <el-icon class="tip-icon"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px" @row-click="showDetail">
      <el-table-column prop="strategy_name" label="策略" width="150">
        <template #header>
          <span>策略</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>产生该回测的策略名称</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="start_date" label="开始日期" width="120">
        <template #default="{ row }">{{ fmtDate(row.start_date) }}</template>
      </el-table-column>
      <el-table-column prop="end_date" label="结束日期" width="120">
        <template #default="{ row }">{{ fmtDate(row.end_date) }}</template>
      </el-table-column>
      <el-table-column prop="initial_capital" label="初始资金" width="120" align="right">
        <template #default="{ row }">{{ fmtNum(row.initial_capital) }}</template>
      </el-table-column>
      <el-table-column prop="final_capital" label="最终资金" width="130" align="right">
        <template #default="{ row }">{{ fmtNum(row.final_capital) }}</template>
      </el-table-column>
      <el-table-column prop="total_return" label="总收益率" width="110">
        <template #header>
          <span>总收益率</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>(最终资金 - 初始资金) / 初始资金</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          <span :style="{ color: pctNum(row.total_return) >= 0 ? '#67c23a' : '#f56c6c' }">{{ pct(row.total_return) }}%</span>
        </template>
      </el-table-column>
      <el-table-column prop="sharpe_ratio" label="夏普比" width="90" align="right">
        <template #header>
          <span>夏普比</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>(收益率 - 无风险利率) / 波动率；越高代表单位风险获得的超额收益越好</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">{{ row.sharpe_ratio != null ? Number(row.sharpe_ratio).toFixed(2) : '--' }}</template>
      </el-table-column>
      <el-table-column prop="max_drawdown" label="最大回撤" width="110">
        <template #header>
          <span>最大回撤</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>从权益峰值跌到谷底的最大百分比，反映最坏情况下的亏损幅度</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          <span style="color:#f56c6c">{{ pct(row.max_drawdown) }}%</span>
        </template>
      </el-table-column>
      <el-table-column prop="win_rate" label="胜率" width="90">
        <template #header>
          <span>胜率</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>盈利交易次数 / 总交易次数</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">{{ pct(row.win_rate, 1) }}%</template>
      </el-table-column>
      <el-table-column prop="total_trades" label="交易次数" width="90" align="right" />
      <el-table-column prop="profit_factor" label="盈亏比" width="90" align="right">
        <template #header>
          <span>盈亏比</span>
          <el-tooltip placement="top" :show-after="300">
            <template #content>平均盈利 / 平均亏损的绝对值；大于 1 代表盈利额大于亏损额</template>
            <el-icon class="tip-inline"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <template #default="{ row }">{{ row.profit_factor != null ? Number(row.profit_factor).toFixed(2) : '--' }}</template>
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
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @size-change="load"
        @current-change="load"
      />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" width="960px" top="5vh" :close-on-click-modal="false">
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
          <el-row :gutter="20">
            <el-col :span="6" v-for="m in metrics" :key="m.label" style="margin-bottom:16px">
              <el-card shadow="hover">
                <div class="metric-label">
                  {{ m.label }}
                  <el-tooltip v-if="m.tip" placement="top" :show-after="300">
                    <template #content>{{ m.tip }}</template>
                    <el-icon class="tip-inline"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </div>
                <div class="metric-value" :style="{ color: m.color }">{{ m.value }}</div>
              </el-card>
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
            <el-table-column prop="symbol" label="品种" width="120" />
            <el-table-column prop="action" label="方向" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.action === 'buy' ? 'success' : 'danger'">
                  {{ row.action === 'buy' ? '买入' : '卖出' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="price" label="价格" width="110" align="right">
              <template #default="{ row }">{{ fmtNum(row.price) }}</template>
            </el-table-column>
            <el-table-column prop="amount" label="金额" width="120" align="right">
              <template #default="{ row }">{{ fmtNum(row.amount) }}</template>
            </el-table-column>
            <el-table-column prop="fee" label="手续费" width="100" align="right">
              <template #default="{ row }">{{ fmtNum(row.fee) }}</template>
            </el-table-column>
            <el-table-column prop="pnl" label="盈亏" width="120" align="right">
              <template #default="{ row }">
                <span v-if="row.pnl !== undefined && row.pnl !== null" :style="{ color: Number(row.pnl) >= 0 ? '#67c23a' : '#f56c6c' }">{{ Number(row.pnl).toFixed(2) }}</span>
                <span v-else>--</span>
              </template>
            </el-table-column>
            <el-table-column prop="capital" label="权益" width="130" align="right">
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  getBacktests, getBacktestDetail,
  runBacktestMonteCarlo, exportBacktestResultReport,
} from '@/api/strategy'
import { ElMessage } from 'element-plus'
import {
  Refresh, View, Download, QuestionFilled, Histogram, DataLine,
} from '@element-plus/icons-vue'

const router = useRouter()
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([LineChart, BarChart, TitleComponent, TooltipComponent, GridComponent, CanvasRenderer])

// ========== 状态 ==========
const tableData = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const selected = ref(null)
const activeTab = ref('metrics')
const mcLoading = ref(false)
const mcResult = ref(null)

const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// ========== 格式化辅助 ==========
function pctNum(v) {
  // 把后端传的 Decimal/string/number 统一转为浮点数（例如 0.0523 -> 5.23）
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
function fmtDate(v) {
  if (!v) return '--'
  const d = new Date(v)
  if (isNaN(d.getTime())) return String(v).slice(0, 10)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
function fmtDateTime(v) {
  if (!v) return '--'
  const d = new Date(v)
  if (isNaN(d.getTime())) return String(v).slice(0, 19).replace('T', ' ')
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${day} ${hh}:${mm}:${ss}`
}

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
    { label: '年化收益率', value: `${annualReturn.toFixed(2)}%`, color: '#409eff', tip: '把区间收益率折算成一年的收益率，方便不同时长回测对比' },
    { label: '夏普比率', value: d.sharpe_ratio != null ? Number(d.sharpe_ratio).toFixed(2) : '--', color: '#409eff', tip: '越高代表承担单位风险获得的超额收益越好，通常 > 1 较好' },
    { label: '最大回撤', value: `${maxDD.toFixed(2)}%`, color: '#f56c6c', tip: '权益从峰值跌到谷底的最坏百分比，用于评估极端风险' },
    { label: '胜率', value: `${winRate.toFixed(1)}%`, color: '#67c23a', tip: '盈利交易次数 / 总交易次数' },
    { label: '盈亏比', value: d.profit_factor != null ? Number(d.profit_factor).toFixed(2) : '--', color: '#409eff', tip: '平均盈利 ÷ 平均亏损的绝对值；> 1 说明赚的比亏的多' },
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
    xAxis: { type: 'category', data: dds.map((_, i) => i + 1), axisLabel: { rotate: 0 } },
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
    const res = await getBacktests({ page: page.value, page_size: pageSize.value })
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
  } catch (e) { ElMessage.error(e.message || '加载回测列表失败') }
  loading.value = false
}

const showDetail = async (row) => {
  selected.value = row
  mcResult.value = null
  activeTab.value = 'metrics'
  // 如果已缓存过 MC 结果，直接恢复显示
  if (row.monte_carlo && row.monte_carlo.status === 'success' && row.monte_carlo.result) {
    mcResult.value = row.monte_carlo.result
  }
  detailVisible.value = true
  // 异步加载完整详情（确保 trade_detail / equity_curve 完整）
  try {
    const full = await getBacktestDetail(row.id)
    selected.value = { ...row, ...full }
    // 从详情数据再次检查 MC 缓存
    if (full.monte_carlo && full.monte_carlo.status === 'success' && full.monte_carlo.result) {
      mcResult.value = full.monte_carlo.result
    }
  } catch (e) { /* 列表数据已够用，不报错 */ }
}

// 推导回测关联的品种：优先 trade_detail 里的品种，其次策略配置的 symbols
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
      // 异步任务已提交，提示用户稍后重新打开查看
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
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.title-wrap { display: flex; align-items: center; gap: 8px; }
.tip-icon { color: #909399; font-size: 18px; cursor: help; }
.tip-inline { color: #909399; font-size: 13px; margin-left: 4px; vertical-align: middle; cursor: help; }
.detail-header { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.detail-actions { display: flex; gap: 8px; }
.metric-label { font-size: 13px; color: #909399; margin-bottom: 8px; display: flex; align-items: center; }
.metric-value { font-size: 22px; font-weight: bold; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
