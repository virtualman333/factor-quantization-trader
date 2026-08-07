<template>
  <div>
    <div class="page-header">
      <h2>净值曲线</h2>
      <el-button type="primary" :icon="Plus" :loading="loading" @click="record">记录净值</el-button>
    </div>
    <el-card style="margin-top:16px">
      <v-chart :option="chartOption" style="height:400px" autoresize />
    </el-card>
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column prop="total_eq" label="总权益" width="160" />
      <el-table-column prop="total_pnl" label="累计盈亏" width="160" />
      <el-table-column prop="daily_pnl" label="日盈亏" width="160" />
      <el-table-column prop="pnl_ratio" label="收益率%" width="100" />
      <el-table-column prop="record_time" label="记录时间" width="180" />
    </el-table>
    <div class="pagination">
      <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="prev, pager, next, total" @current-change="load" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getNetValues, recordNetValue, getNetValueChart } from '@/api/account'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([LineChart, TitleComponent, TooltipComponent, GridComponent, CanvasRenderer])

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)

const chartData = ref([])

const chartOption = computed(() => {
  const data = chartData.value || []
  return {
    title: { text: '净值走势', left: 'center' },
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 20, bottom: 40 },
    xAxis: { type: 'category', data: data.map(d => d.time) },
    yAxis: { type: 'value', name: '权益(USD)', scale: true },
    series: [{
      data: data.map(d => d.total_eq),
      type: 'line', smooth: true, areaStyle: { opacity: 0.1 },
      itemStyle: { color: '#409eff' },
    }],
  }
})

const load = async () => {
  loading.value = true
  try {
    const res = await getNetValues({ page: page.value })
    tableData.value = res.results || res
    total.value = res.count || 0
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const record = async () => {
  loading.value = true
  try { await recordNetValue(); ElMessage.success('净值已记录'); await load(); loadChart() }
  catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const loadChart = async () => {
  try {
    const res = await getNetValueChart({ days: 90 })
    chartData.value = res.results || []
  } catch { /* 图表加载失败忽略 */ }
}

onMounted(() => { load(); loadChart() })
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
