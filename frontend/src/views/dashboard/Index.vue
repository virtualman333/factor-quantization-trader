<template>
  <div>
    <h2>仪表盘</h2>

    <!-- 实时行情卡片 -->
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="6" v-for="m in marketPrices" :key="m.inst_id">
        <el-card shadow="hover">
          <div class="market-card">
            <div class="market-head">
              <span class="market-name">{{ m.inst_id }}</span>
              <el-tag size="small" :type="m.changePct >= 0 ? 'success' : 'danger'">
                {{ m.changePct >= 0 ? '+' : '' }}{{ m.changePct }}%
              </el-tag>
            </div>
            <div class="market-last" :style="{ color: m.changePct >= 0 ? '#67c23a' : '#f56c6c' }">
              {{ m.last }}
            </div>
            <div class="market-bidask">买一 {{ m.bid_px || '--' }} / 卖一 {{ m.ask_px || '--' }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 统计卡片 -->
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="6" v-for="s in stats" :key="s.label">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-label">{{ s.label }}</div>
            <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 净值曲线 + 策略排行 -->
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>净值实时曲线</span>
              <el-radio-group v-model="netDays" size="small" @change="loadNetValue">
                <el-radio-button :value="7">7天</el-radio-button>
                <el-radio-button :value="30">30天</el-radio-button>
                <el-radio-button :value="90">90天</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <v-chart :option="netChartOption" style="height:260px" autoresize />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card>
          <template #header>策略收益排行</template>
          <el-table :data="strategyRanking" size="small" max-height="290">
            <el-table-column prop="name" label="策略" show-overflow-tooltip />
            <el-table-column label="收益" width="100">
              <template #default="{ row }">
                <span v-if="row.latest_return !== null" :style="{ color: row.latest_return >= 0 ? '#67c23a' : '#f56c6c' }">
                  {{ (row.latest_return * 100).toFixed(2) }}%
                </span>
                <span v-else style="color:#909399">--</span>
              </template>
            </el-table-column>
            <el-table-column label="夏普" width="70">
              <template #default="{ row }">{{ row.latest_sharpe?.toFixed(2) ?? '--' }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 因子热力图 + 市场概览 -->
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="14">
        <el-card>
          <template #header>因子热力图</template>
          <v-chart :option="heatmapOption" style="height:260px" autoresize />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card>
          <template #header>市场概览（涨跌幅排行）</template>
          <el-table :data="marketOverview" size="small" max-height="290">
            <el-table-column prop="inst_id" label="品种" />
            <el-table-column label="涨跌幅" width="110">
              <template #default="{ row }">
                <span :style="{ color: row.change_pct >= 0 ? '#67c23a' : '#f56c6c' }">
                  {{ row.change_pct >= 0 ? '+' : '' }}{{ row.change_pct }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="last" label="最新价" width="110" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近信号 / 订单 -->
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="12">
        <el-card>
          <template #header>最近信号</template>
          <el-table :data="recentSignals" size="small" max-height="300">
            <el-table-column prop="inst_id" label="品种" width="120" />
            <el-table-column prop="signal" label="信号" width="80">
              <template #default="{ row }">
                <el-tag :type="row.signal === 'buy' ? 'success' : row.signal === 'sell' ? 'danger' : 'info'" size="small">
                  {{ row.signal }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="score" label="得分" width="80" />
            <el-table-column prop="reason" label="原因" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>最近订单</template>
          <el-table :data="recentOrders" size="small" max-height="300">
            <el-table-column prop="inst_id" label="品种" width="120" />
            <el-table-column prop="side" label="方向" width="80">
              <template #default="{ row }">
                <el-tag :type="row.side === 'buy' ? 'success' : 'danger'" size="small">{{ row.side }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="sz" label="数量" width="100" />
            <el-table-column prop="state" label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.state }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
defineOptions({ name: 'Dashboard' })
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { getSignals } from '@/api/strategy'
import { getOrders } from '@/api/orders'
import { getLiveBalance, getLivePositions } from '@/api/account'
import { getTickers } from '@/api/market'
import { getStrategyRanking, getFactorHeatmap, getMarketOverview, getNetValueCurve } from '@/api/dashboard'
import { useRealtimeStore } from '@/stores/realtime'
import { formatShort } from '@/utils/time'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, BarChart, HeatmapChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([LineChart, BarChart, HeatmapChart, TitleComponent, TooltipComponent, GridComponent, VisualMapComponent, CanvasRenderer])

const realtimeStore = useRealtimeStore()

// ---------- 实时行情卡片 ----------
const MARKET_IDS = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
const marketPrices = ref(
  MARKET_IDS.map((inst_id) => ({
    inst_id,
    last: '--',
    changePct: 0,
    bid_px: '--',
    ask_px: '--',
  }))
)
const unsubscribers = []

const applyMarketPrice = (p) => {
  const item = marketPrices.value.find((m) => m.inst_id === p.inst_id)
  if (!item) return
  item.last = p.last ?? item.last
  item.bid_px = p.bid_px ?? item.bid_px
  item.ask_px = p.ask_px ?? item.ask_px
  if (p.open_24h && p.last) {
    const last = parseFloat(p.last)
    const open = parseFloat(p.open_24h)
    item.changePct = open ? parseFloat(((last - open) / open * 100).toFixed(2)) : 0
  }
}

const loadMarketPrices = async () => {
  const results = await Promise.allSettled(
    MARKET_IDS.map((id) => getTickers({ instrument__inst_id: id }))
  )
  results.forEach((res, i) => {
    if (res.status !== 'fulfilled') return
    const rows = res.value?.results || res.value || []
    if (rows[0]) applyMarketPrice(rows[0])
  })
}

const stats = ref([
  { label: '账户权益', value: '--', color: '#409eff' },
  { label: '持仓数量', value: '--', color: '#67c23a' },
  { label: '今日信号', value: '--', color: '#e6a23c' },
  { label: '活跃策略', value: '--', color: '#f56c6c' },
])

const recentSignals = ref([])
const recentOrders = ref([])

// ---------- 净值曲线 ----------
const netDays = ref(30)
const netCurve = ref([])
const netChartOption = computed(() => {
  const data = netCurve.value || []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 70, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: data.map(d => formatShort(d.time)) },
    yAxis: { type: 'value', scale: true },
    series: [{
      name: '净值', type: 'line', data: data.map(d => d.net_value),
      smooth: true, showSymbol: false, areaStyle: { opacity: 0.15 },
      itemStyle: { color: '#409eff' },
    }],
  }
})
const loadNetValue = async () => {
  try {
    const res = await getNetValueCurve({ days: netDays.value })
    netCurve.value = res.results || res || []
  } catch {}
}

// ---------- 策略排行 ----------
const strategyRanking = ref([])
const loadRanking = async () => {
  try {
    const res = await getStrategyRanking({ limit: 10 })
    strategyRanking.value = res.results || []
  } catch {}
}

// ---------- 因子热力图 ----------
const heatmapData = ref([])
const heatmapOption = computed(() => {
  const rows = heatmapData.value || []
  const strategies = [...new Set(rows.map(r => r.strategy))]
  const factors = [...new Set(rows.map(r => r.factor))]
  const idxMap = {}
  strategies.forEach((s, i) => { idxMap[s] = i })
  const fMap = {}
  factors.forEach((f, i) => { fMap[f] = i })
  const data = rows.map(r => [fMap[r.factor], idxMap[r.strategy], r.score])
  return {
    tooltip: {
      position: 'top',
      formatter: (p) => `${strategies[p.value[1]]}<br/>${factors[p.value[0]]}: ${(p.value[2] * 100).toFixed(1)}%`,
    },
    grid: { left: 90, right: 20, top: 10, bottom: 50 },
    xAxis: { type: 'category', data: factors, splitArea: { show: true } },
    yAxis: { type: 'category', data: strategies, splitArea: { show: true } },
    visualMap: {
      min: 0, max: 1, calculable: true, orient: 'horizontal',
      left: 'center', bottom: 0, text: ['多', '空'],
    },
    series: [{
      type: 'heatmap', data,
      label: { show: true, formatter: (p) => (p.value[2] * 100).toFixed(0) },
    }],
  }
})
const loadHeatmap = async () => {
  try {
    const res = await getFactorHeatmap({ n: 300 })
    heatmapData.value = res.results || []
  } catch {}
}

// ---------- 市场概览 ----------
const marketOverview = ref([])
const loadMarketOverview = async () => {
  try {
    const res = await getMarketOverview({ limit: 20 })
    marketOverview.value = res.results || []
  } catch {}
}

onMounted(async () => {
  loadMarketPrices().catch(() => {})
  MARKET_IDS.forEach((id) => {
    unsubscribers.push(realtimeStore.subscribe(`tickers:${id}`, applyMarketPrice))
  })
  loadNetValue()
  loadRanking()
  loadHeatmap()
  loadMarketOverview()
  try {
    const balance = await getLiveBalance()
    if (balance?.data?.length) {
      const total = balance.data[0].details.reduce((s, d) => s + parseFloat(d.usdValue || 0), 0)
      stats.value[0].value = `$${total.toFixed(2)}`
    }
  } catch {}
  try {
    const pos = await getLivePositions()
    if (pos?.data) stats.value[1].value = pos.data.length
  } catch {}
  try {
    const sigs = await getSignals({ limit: 10 })
    recentSignals.value = sigs.results || sigs || []
    stats.value[2].value = recentSignals.value.length
  } catch {}
  try {
    const orders = await getOrders({ limit: 10 })
    recentOrders.value = orders.results || orders || []
  } catch {}
})

onBeforeUnmount(() => {
  unsubscribers.forEach((fn) => fn())
  unsubscribers.length = 0
})
</script>

<style scoped>
.stat-card { text-align: center; padding: 10px 0; }
.stat-label { font-size: 14px; color: #909399; margin-bottom: 8px; }
.stat-value { font-size: 28px; font-weight: bold; }
.market-card { text-align: center; padding: 6px 0; }
.market-head { display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 8px; }
.market-name { font-size: 14px; font-weight: 600; color: #303133; }
.market-last { font-size: 24px; font-weight: bold; font-family: 'Consolas', 'Monaco', monospace; }
.market-bidask { margin-top: 8px; font-size: 12px; color: #909399; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
