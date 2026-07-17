<template>
  <div>
    <div class="page-header">
      <h2>实时行情</h2>
      <div>
        <el-input v-model="instId" placeholder="品种ID" style="width:200px" clearable />
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="refresh" style="margin-left:8px">刷新行情</el-button>
      </div>
    </div>
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column prop="inst_id" label="品种" width="130" />
      <el-table-column prop="last" label="最新价" width="120">
        <template #default="{ row }">
          <span :style="{ color: parseFloat(row.last) >= parseFloat(row.open_24h) ? '#67c23a' : '#f56c6c' }">{{ row.last }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="open_24h" label="24h开盘" width="120" />
      <el-table-column prop="high_24h" label="24h最高" width="120" />
      <el-table-column prop="low_24h" label="24h最低" width="120" />
      <el-table-column prop="vol_24h" label="24h成交量" width="140" />
      <el-table-column prop="bid_px" label="买一价" width="120" />
      <el-table-column prop="ask_px" label="卖一价" width="120" />
      <el-table-column prop="bid_sz" label="买一量" width="100" />
      <el-table-column prop="ask_sz" label="卖一量" width="100" />
    </el-table>
    <div class="pagination">
      <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="prev, pager, next, total" @current-change="load" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getTickers, refreshTicker } from '@/api/market'
import { ElMessage } from 'element-plus'

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const instId = ref('')

const load = async () => {
  loading.value = true
  try {
    const params = { page: page.value }
    if (instId.value) params.instrument__inst_id = instId.value
    const res = await getTickers(params)
    tableData.value = res.results || res
    total.value = res.count || 0
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const refresh = async () => {
  loading.value = true
  try {
    await refreshTicker({ inst_id: instId.value || undefined })
    ElMessage.success('刷新成功')
    await load()
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
