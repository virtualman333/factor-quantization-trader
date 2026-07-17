<template>
  <div>
    <div class="page-header">
      <h2>交易信号</h2>
      <div>
        <el-select v-model="filterSignal" placeholder="信号类型" clearable style="width:130px">
          <el-option label="买入/开多" value="buy" />
          <el-option label="卖出/开空" value="sell" />
          <el-option label="平多" value="close_long" />
          <el-option label="平空" value="close_short" />
          <el-option label="持有" value="hold" />
        </el-select>

        <el-select v-model="filterExecuted" placeholder="执行状态" clearable style="width:130px;margin-left:8px">
          <el-option label="已执行" :value="true" />
          <el-option label="未执行" :value="false" />
        </el-select>
        <el-button type="primary" :icon="Refresh" @click="load" style="margin-left:8px">刷新</el-button>
      </div>
    </div>
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column prop="inst_id" label="品种" width="130" />
      <el-table-column prop="strategy_name" label="策略" width="150" />
      <el-table-column prop="signal" label="信号" width="110">
        <template #default="{ row }">
          <el-tag :type="signalTagType(row.signal)" size="small">
            {{ row.signal_display || row.signal }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="score" label="得分" width="80">
        <template #default="{ row }">
          <el-progress :percentage="Math.round(row.score * 100)" :stroke-width="8" :color="row.score >= 0.5 ? '#67c23a' : '#e6a23c'" />
        </template>
      </el-table-column>
      <el-table-column prop="pos_side" label="持仓方向" width="90" />
      <el-table-column prop="td_mode" label="保证金模式" width="110" />
      <el-table-column prop="leverage" label="杠杆" width="80" />
      <el-table-column prop="price" label="价格" width="120" />
      <el-table-column prop="reason" label="原因" min-width="200" show-overflow-tooltip />
      <el-table-column prop="is_executed" label="已执行" width="80">

        <template #default="{ row }">
          <el-tag :type="row.is_executed ? 'success' : 'warning'" size="small">{{ row.is_executed ? '是' : '否' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button v-if="!row.is_executed" size="small" type="success" @click="execute(row.id)">执行</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pagination">
      <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="prev, pager, next, total" @current-change="load" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { getSignals, executeSignal } from '@/api/strategy'
import { ElMessage } from 'element-plus'

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const filterSignal = ref('')
const filterExecuted = ref('')

const load = async () => {
  loading.value = true
  try {
    const params = { page: page.value }
    if (filterSignal.value) params.signal = filterSignal.value
    if (filterExecuted.value !== '') params.is_executed = filterExecuted.value
    const res = await getSignals(params)
    tableData.value = res.results || res
    total.value = res.count || 0
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const execute = async (id) => {
  try { await executeSignal(id); ElMessage.success('已执行'); load() }
  catch (e) { ElMessage.error(e.message) }
}

const signalTagType = (signal) => {
  if (signal === 'buy') return 'success'
  if (signal === 'sell') return 'danger'
  if (signal === 'close_long' || signal === 'close_short') return 'warning'
  return 'info'
}

watch([filterSignal, filterExecuted], () => { page.value = 1; load() })

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
