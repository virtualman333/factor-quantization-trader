<template>
  <div>
    <div class="page-header">
      <h2>K线数据</h2>
      <div class="header-right">
        <el-input v-model="instId" placeholder="品种ID (BTC-USDT)" style="width:200px" clearable />
        <el-select v-model="bar" style="width:100px;margin-left:8px">
          <el-option v-for="b in bars" :key="b" :label="b" :value="b" />
        </el-select>
        <el-button type="primary" :icon="Download" @click="fetchKlines" style="margin-left:8px">拉取</el-button>
        <el-button :icon="Refresh" @click="load" style="margin-left:8px">刷新</el-button>
      </div>
    </div>
    <el-card v-loading="loading" style="margin-top:16px">
      <div ref="chartRef" style="width:100%;height:640px"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { getKlines, fetchKlines as fetchApi } from '@/api/market'
import { ElMessage } from 'element-plus'
import { init, dispose } from 'klinecharts'
import dayjs from 'dayjs'

const chartRef = ref(null)
const loading = ref(false)
const instId = ref('BTC-USDT')
const bar = ref('1H')
const bars = ['1m', '3m', '5m', '15m', '30m', '1H', '2H', '4H', '6H', '12H', '1D', '1W', '1M']

let chart = null

const initChart = () => {
  if (!chartRef.value) return
  chart = init(chartRef.value, {
    styles: {
      grid: { horizontal: { color: '#f0f0f0' }, vertical: { color: '#f0f0f0' } },
      candle: {
        bar: { upColor: '#67c23a', downColor: '#f56c6c', noChangeColor: '#999' },
        priceMark: { last: { text: { backgroundColor: '#409eff' } } },
      },
      indicator: { lastValueMark: { text: { backgroundColor: '#409eff' } } },
    },
  })
}

const renderChart = (list) => {
  if (!chart) return
  // klinecharts 要求数据按时间升序，且时间戳为毫秒
  const data = [...list]
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    .map(d => ({
      timestamp: new Date(d.timestamp).getTime(),
      open: parseFloat(d.open),
      high: parseFloat(d.high),
      low: parseFloat(d.low),
      close: parseFloat(d.close),
      volume: parseFloat(d.vol) || 0,
    }))
  chart.applyNewData(data)
}

const load = async () => {
  loading.value = true
  try {
    const params = { page: 1 }
    if (instId.value) params.instrument__inst_id = instId.value
    if (bar.value) params.bar = bar.value
    const res = await getKlines(params)
    const list = res.results || res
    renderChart(list)
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const fetchKlines = async () => {
  if (!instId.value) { ElMessage.warning('请输入品种ID'); return }
  loading.value = true
  try {
    await fetchApi({ inst_id: instId.value, bar: bar.value, limit: 300 })
    ElMessage.success('拉取成功')
    await load()
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

onMounted(async () => {
  await nextTick()
  initChart()
  await load()
})

onBeforeUnmount(() => {
  if (chart) { dispose(chart); chart = null }
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.header-right { display: flex; align-items: center; }
</style>
