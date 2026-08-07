<template>
  <div>
    <div class="page-header">
      <h2>回测结果</h2>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px" @row-click="showDetail">
      <el-table-column prop="strategy_name" label="策略" width="150" />
      <el-table-column prop="start_date" label="开始日期" width="120" />
      <el-table-column prop="end_date" label="结束日期" width="120" />
      <el-table-column prop="initial_capital" label="初始资金" width="120" />
      <el-table-column prop="final_capital" label="最终资金" width="130" />
      <el-table-column prop="total_return" label="总收益率" width="100">
        <template #default="{ row }">
          <span :style="{ color: parseFloat(row.total_return) >= 0 ? '#67c23a' : '#f56c6c' }">{{ (row.total_return * 100).toFixed(2) }}%</span>
        </template>
      </el-table-column>
      <el-table-column prop="sharpe_ratio" label="夏普比" width="80" />
      <el-table-column prop="max_drawdown" label="最大回撤" width="100">
        <template #default="{ row }">
          <span style="color:#f56c6c">{{ (row.max_drawdown * 100).toFixed(2) }}%</span>
        </template>
      </el-table-column>
      <el-table-column prop="win_rate" label="胜率" width="80">
        <template #default="{ row }">{{ (row.win_rate * 100).toFixed(1) }}%</template>
      </el-table-column>
      <el-table-column prop="total_trades" label="交易次数" width="90" />
      <el-table-column prop="profit_factor" label="盈亏比" width="80" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click.stop="exportReport(row)">导出报告</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" width="900px" top="5vh">
      <template #header>
        <div class="detail-header">
          <span>回测详情 - {{ selected?.strategy_name }}</span>
          <div>
            <el-button size="small" type="primary" @click="runMonteCarlo" :loading="mcLoading">蒙特卡洛模拟</el-button>
            <el-button size="small" @click="exportReport(selected)">导出报告</el-button>
          </div>
        </div>
      </template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="核心指标" name="metrics">
          <el-row :gutter="20">
            <el-col :span="8" v-for="m in metrics" :key="m.label" style="margin-bottom:16px">
              <el-card shadow="hover">
                <div class="metric-label">{{ m.label }}</div>
                <div class="metric-value" :style="{ color: m.color }">{{ m.value }}</div>
              </el-card>
            </el-col>
          </el-row>
          <el-card>
            <template #header>权益曲线（手续费率 {{ selected?.fee_rate }} | 滑点 {{ selected?.slippage }}）</template>
            <v-chart :option="chartOption" style="height:300px" autoresize />
          </el-card>
        </el-tab-pane>
        <el-tab-pane label="交易明细" name="trades">
          <el-table :data="selected?.trade_detail || []" border stripe size="small" max-height="420">
            <el-table-column prop="timestamp" label="时间" width="150" />
            <el-table-column prop="symbol" label="品种" width="110" />
            <el-table-column prop="action" label="方向" width="70">
              <template #default="{ row }">
                <el-tag size="small" :type="row.action === 'buy' ? 'success' : 'danger'">{{ row.action }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="price" label="价格" width="100" />
            <el-table-column prop="amount" label="金额" width="100" />
            <el-table-column prop="fee" label="手续费" width="90" />
            <el-table-column prop="pnl" label="盈亏" width="110">
              <template #default="{ row }">
                <span v-if="row.pnl !== undefined" :style="{ color: row.pnl >= 0 ? '#67c23a' : '#f56c6c' }">{{ row.pnl.toFixed(2) }}</span>
                <span v-else>--</span>
              </template>
            </el-table-column>
            <el-table-column prop="capital" label="权益" width="110" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="蒙特卡洛" name="montecarlo">
          <template v-if="mcResult">
            <el-descriptions :column="3" border size="small">
              <el-descriptions-item label="最大回撤(中位数)">{{ (mcResult.max_drawdown.median * 100).toFixed(2) }}%</el-descriptions-item>
              <el-descriptions-item label="最大回撤(P95)">{{ (mcResult.max_drawdown.p95 * 100).toFixed(2) }}%</el-descriptions-item>
              <el-descriptions-item label="最大回撤(P99)">{{ (mcResult.max_drawdown.p99 * 100).toFixed(2) }}%</el-descriptions-item>
              <el-descriptions-item label="收益(中位数)">{{ (mcResult.total_return.median * 100).toFixed(2) }}%</el-descriptions-item>
              <el-descriptions-item label="收益(P5)">{{ (mcResult.total_return.p5 * 100).toFixed(2) }}%</el-descriptions-item>
              <el-descriptions-item label="收益(P95)">{{ (mcResult.total_return.p95 * 100).toFixed(2) }}%</el-descriptions-item>
            </el-descriptions>
            <v-chart :option="mcChartOption" style="height:280px;margin-top:16px" autoresize />
          </template>
          <el-empty v-else description="点击右上角「蒙特卡洛模拟」开始" />
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getBacktests, runMonteCarlo as mcApi, exportBacktestReport } from '@/api/strategy'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([LineChart, BarChart, TitleComponent, TooltipComponent, GridComponent, CanvasRenderer])

const tableData = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const selected = ref(null)
const activeTab = ref('metrics')
const mcLoading = ref(false)
const mcResult = ref(null)

const metrics = computed(() => {
  if (!selected.value) return []
  const d = selected.value
  return [
    { label: '总收益率', value: `${(d.total_return * 100).toFixed(2)}%`, color: d.total_return >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '年化收益率', value: `${(d.annual_return * 100).toFixed(2)}%`, color: '#409eff' },
    { label: '夏普比率', value: d.sharpe_ratio?.toFixed(2) || '--', color: '#409eff' },
    { label: '最大回撤', value: `${(d.max_drawdown * 100).toFixed(2)}%`, color: '#f56c6c' },
    { label: '胜率', value: `${(d.win_rate * 100).toFixed(1)}%`, color: '#67c23a' },
    { label: '盈亏比', value: d.profit_factor?.toFixed(2) || '--', color: '#409eff' },
    { label: '交易次数', value: d.total_trades, color: '#606266' },
    { label: '初始→最终资金', value: `${d.initial_capital} → ${d.final_capital}`, color: '#409eff' },
  ]
})

const mcChartOption = computed(() => {
  const dds = mcResult.value?.max_drawdowns_sample || []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 20, top: 20, bottom: 40 },
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
    tooltip: { trigger: 'axis' },
    grid: { left: 80, right: 20, bottom: 40 },
    xAxis: { type: 'category', data: curve.map((_, i) => i) },
    yAxis: { type: 'value' },
    series: [{
      data: curve, type: 'line', smooth: true, areaStyle: { opacity: 0.1 },
      itemStyle: { color: '#409eff' },
    }],
  }
})

const load = async () => {
  loading.value = true
  try {
    const res = await getBacktests()
    tableData.value = res.results || res
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const showDetail = (row) => {
  selected.value = row
  mcResult.value = null
  activeTab.value = 'metrics'
  detailVisible.value = true
}

const runMonteCarlo = async () => {
  const btId = selected.value?.id
  if (!btId) return
  mcLoading.value = true
  try {
    mcResult.value = await mcApi(btId, { n_simulations: 1000 })
    activeTab.value = 'montecarlo'
    ElMessage.success('蒙特卡洛模拟完成')
  } catch (e) { ElMessage.error(e.message) }
  mcLoading.value = false
}

const exportReport = async (row) => {
  try {
    const res = await exportBacktestReport(row.id)
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `backtest_${row.strategy_name}_${row.id}.html`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.detail-header { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.metric-label { font-size: 13px; color: #909399; margin-bottom: 8px; }
.metric-value { font-size: 22px; font-weight: bold; }
</style>
