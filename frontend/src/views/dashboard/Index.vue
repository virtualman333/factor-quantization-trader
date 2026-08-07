<template>
  <div>
    <h2>仪表盘</h2>
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
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { getSignals } from '@/api/strategy'
import { getOrders } from '@/api/orders'
import { getLiveBalance, getLivePositions } from '@/api/account'
import { getTickers } from '@/api/market'
import { useRealtimeStore } from '@/stores/realtime'

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

onMounted(async () => {
  loadMarketPrices().catch(() => {})
  MARKET_IDS.forEach((id) => {
    unsubscribers.push(realtimeStore.subscribe(`tickers:${id}`, applyMarketPrice))
  })
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
</style>
