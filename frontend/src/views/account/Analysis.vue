<template>
  <div>
    <div class="page-header">
      <h2>账户分析</h2>
      <el-radio-group v-model="days" size="small" @change="loadAll">
        <el-radio-button :value="7">7天</el-radio-button>
        <el-radio-button :value="30">30天</el-radio-button>
        <el-radio-button :value="90">90天</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 资金曲线 vs BTC 基准 -->
    <el-card style="margin-top:16px">
      <template #header>资金曲线与 BTC 基准对比（归一化 100 起点）</template>
      <v-chart :option="benchmarkOption" style="height:300px" autoresize />
    </el-card>

    <el-row :gutter="16" style="margin-top:16px">
      <!-- 盈亏分析报表 -->
      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>盈亏分析报表</span>
              <el-radio-group v-model="period" size="small" @change="loadPnl">
                <el-radio-button value="day">日</el-radio-button>
                <el-radio-button value="week">周</el-radio-button>
                <el-radio-button value="month">月</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div v-if="pnlSummary" class="pnl-summary">
            <el-tag :type="pnlSummary.total_pnl >= 0 ? 'success' : 'danger'" size="large">
              总盈亏 {{ pnlSummary.total_pnl }} USD ({{ pnlSummary.total_ratio }}%)
            </el-tag>
            <el-tag style="margin-left:8px" size="large">
              盈利期间 {{ pnlSummary.positive_periods }}/{{ pnlSummary.total_periods }}
            </el-tag>
          </div>
          <v-chart :option="pnlOption" style="height:240px;margin-top:12px" autoresize />
        </el-card>
      </el-col>

      <!-- 手续费统计 -->
      <el-col :span="10">
        <el-card>
          <template #header>手续费统计</template>
          <div v-if="feeData" class="fee-total">
            <span class="fee-label">近 {{ feeData.days }} 天总手续费</span>
            <span class="fee-value" :style="{ color: feeData.total_fee >= 0 ? '#f56c6c' : '#67c23a' }">
              {{ feeData.total_fee }} USD
            </span>
          </div>
          <el-table v-if="feeByInst.length" :data="feeByInst" size="small" border style="margin-top:12px" max-height="260">
            <el-table-column prop="inst" label="品种" />
            <el-table-column prop="fee" label="手续费(USD)" width="130" />
          </el-table>
          <el-empty v-else description="暂无手续费数据" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getPnlReport, getFeeStatistics, getEquityBenchmark } from '@/api/account'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([LineChart, BarChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const days = ref(30)
const period = ref('month')

const benchmarkData = ref(null)
const pnlData = ref([])
const pnlSummary = ref(null)
const feeData = ref(null)

const benchmarkOption = computed(() => {
  const d = benchmarkData.value
  if (!d) return {}
  const eq = d.equity || []
  const btc = d.benchmark || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: [d.equity_label, d.benchmark_label] },
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: eq.map(e => e.time?.slice(0, 10)) },
    yAxis: { type: 'value', scale: true },
    series: [
      { name: d.equity_label, type: 'line', data: eq.map(e => e.value), smooth: true, showSymbol: false, itemStyle: { color: '#409eff' }, areaStyle: { opacity: 0.1 } },
      { name: d.benchmark_label, type: 'line', data: btc.map(b => b.value), smooth: true, showSymbol: false, itemStyle: { color: '#f39c12' } },
    ],
  }
})

const pnlOption = computed(() => {
  return {
    tooltip: { trigger: 'axis', formatter: (ps) => `${ps[0].axisValue}<br/>盈亏: ${ps[0].value} USD` },
    grid: { left: 60, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: pnlData.value.map(i => i.period) },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: pnlData.value.map(i => ({
        value: i.pnl,
        itemStyle: { color: i.pnl >= 0 ? '#67c23a' : '#f56c6c' },
      })),
    }],
  }
})

const feeByInst = computed(() => {
  if (!feeData.value?.by_inst) return []
  return Object.entries(feeData.value.by_inst).map(([inst, fee]) => ({ inst, fee }))
})

const loadBenchmark = async () => {
  try { benchmarkData.value = await getEquityBenchmark({ days: days.value }) } catch {}
}
const loadPnl = async () => {
  try {
    const res = await getPnlReport({ period: period.value })
    pnlData.value = res.items || []
    pnlSummary.value = res.summary || null
  } catch {}
}
const loadFee = async () => {
  try { feeData.value = await getFeeStatistics({ days: days.value }) } catch {}
}
const loadAll = () => { loadBenchmark(); loadPnl(); loadFee() }

onMounted(loadAll)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.pnl-summary { display: flex; align-items: center; }
.fee-total { display: flex; flex-direction: column; }
.fee-label { font-size: 13px; color: #909399; }
.fee-value { font-size: 26px; font-weight: bold; margin-top: 6px; }
</style>
