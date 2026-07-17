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
    </el-table>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="回测详情" width="800px">
      <el-row :gutter="20">
        <el-col :span="8" v-for="m in metrics" :key="m.label">
          <el-card shadow="hover">
            <div class="metric-label">{{ m.label }}</div>
            <div class="metric-value" :style="{ color: m.color }">{{ m.value }}</div>
          </el-card>
        </el-col>
      </el-row>
      <el-card style="margin-top:16px">
        <template #header>权益曲线</template>
        <v-chart :option="chartOption" style="height:300px" autoresize />
      </el-card>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getBacktests } from '@/api/strategy'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([LineChart, TitleComponent, TooltipComponent, GridComponent, CanvasRenderer])

const tableData = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const selected = ref(null)

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
  ]
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
  detailVisible.value = true
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.metric-label { font-size: 13px; color: #909399; margin-bottom: 8px; }
.metric-value { font-size: 22px; font-weight: bold; }
</style>
