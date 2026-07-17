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
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column prop="inst_id" label="品种" width="130" />
      <el-table-column prop="bar_display" label="周期" width="80" />
      <el-table-column prop="timestamp" label="时间" width="170" />
      <el-table-column prop="open" label="开" width="120" />
      <el-table-column prop="high" label="高" width="120" />
      <el-table-column prop="low" label="低" width="120" />
      <el-table-column prop="close" label="收" width="120">
        <template #default="{ row }">
          <span :style="{ color: row.close >= row.open ? '#67c23a' : '#f56c6c' }">{{ row.close }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="vol" label="成交量" width="120" />
    </el-table>
    <div class="pagination">
      <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="prev, pager, next, total" @current-change="load" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getKlines, fetchKlines as fetchApi } from '@/api/market'
import { ElMessage } from 'element-plus'

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const instId = ref('BTC-USDT')
const bar = ref('1H')
const bars = ['1m', '5m', '15m', '30m', '1H', '4H', '1D', '1W', '1M']

const load = async () => {
  loading.value = true
  try {
    const params = { page: page.value }
    if (instId.value) params.instrument__inst_id = instId.value
    if (bar.value) params.bar = bar.value
    const res = await getKlines(params)
    tableData.value = res.results || res
    total.value = res.count || 0
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

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.header-right { display: flex; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
