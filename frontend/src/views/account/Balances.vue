<template>
  <div>
    <div class="page-header">
      <h2>账户余额</h2>
      <div>
        <el-button type="primary" :icon="Camera" :loading="loading" @click="takeSnapshot">保存快照</el-button>
        <el-button type="success" :icon="Refresh" :loading="loading" @click="loadLive">实时余额</el-button>
      </div>
    </div>
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column prop="ccy" label="币种" width="100" />
      <el-table-column prop="total_eq" label="总余额" width="160" />
      <el-table-column prop="avail_eq" label="可用余额" width="160" />
      <el-table-column prop="frozen_bal" label="冻结" width="160" />
      <el-table-column prop="usd_value" label="USD价值" width="160" />
      <el-table-column prop="discount" label="折扣率" width="100" />
      <el-table-column prop="snapshot_time" label="快照时间" width="180" />
    </el-table>
    <div class="pagination">
      <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="prev, pager, next, total" @current-change="load" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getBalances, saveBalanceSnapshot, getLiveBalance } from '@/api/account'
import { ElMessage } from 'element-plus'

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)

const load = async () => {
  loading.value = true
  try {
    const res = await getBalances({ page: page.value })
    tableData.value = res.results || res
    total.value = res.count || 0
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const takeSnapshot = async () => {
  loading.value = true
  try { await saveBalanceSnapshot(); ElMessage.success('快照已保存'); await load() }
  catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const loadLive = async () => {
  loading.value = true
  try {
    const res = await getLiveBalance()
    const details = res?.data?.[0]?.details || []
    tableData.value = details.map(d => ({
      ccy: d.ccy,
      total_eq: d.cashBal,
      avail_eq: d.availBal,
      frozen_bal: d.frozenBal,
      usd_value: d.usdValue,
      discount: d.discount || '1',
      snapshot_time: new Date().toLocaleString(),
    }))
    total.value = tableData.value.length
    ElMessage.success('获取成功')
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
