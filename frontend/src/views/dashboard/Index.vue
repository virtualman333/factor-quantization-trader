<template>
  <div>
    <h2>仪表盘</h2>
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
import { ref, onMounted } from 'vue'
import { getSignals } from '@/api/strategy'
import { getOrders } from '@/api/orders'
import { getLiveBalance, getLivePositions } from '@/api/account'
import { getTickers } from '@/api/market'

const stats = ref([
  { label: '账户权益', value: '--', color: '#409eff' },
  { label: '持仓数量', value: '--', color: '#67c23a' },
  { label: '今日信号', value: '--', color: '#e6a23c' },
  { label: '活跃策略', value: '--', color: '#f56c6c' },
])

const recentSignals = ref([])
const recentOrders = ref([])

onMounted(async () => {
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
</script>

<style scoped>
.stat-card { text-align: center; padding: 10px 0; }
.stat-label { font-size: 14px; color: #909399; margin-bottom: 8px; }
.stat-value { font-size: 28px; font-weight: bold; }
</style>
