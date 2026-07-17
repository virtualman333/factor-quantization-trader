<template>
  <div>
    <div class="page-header">
      <h2>订单管理</h2>
      <div>
        <el-select v-model="filterState" placeholder="状态" clearable style="width:130px">
          <el-option label="活跃" value="live" />
          <el-option label="部分成交" value="partially_filled" />
          <el-option label="已成交" value="filled" />
          <el-option label="已取消" value="canceled" />
        </el-select>
        <el-select v-model="filterSide" placeholder="方向" clearable style="width:100px;margin-left:8px">
          <el-option label="买入" value="buy" />
          <el-option label="卖出" value="sell" />
        </el-select>
        <el-button type="primary" :icon="Refresh" @click="load" style="margin-left:8px">刷新</el-button>
        <el-button type="warning" :icon="Refresh" @click="syncPending" style="margin-left:8px">同步待处理</el-button>
      </div>
    </div>
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column prop="inst_id" label="品种" width="130" />
      <el-table-column prop="side_display" label="方向" width="70">
        <template #default="{ row }">
          <el-tag :type="row.side === 'buy' ? 'success' : 'danger'" size="small">{{ row.side_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="ord_type_display" label="类型" width="70" />
      <el-table-column prop="sz" label="数量" width="100" />
      <el-table-column prop="px" label="价格" width="100" />
      <el-table-column prop="fill_sz" label="已成交" width="100" />
      <el-table-column prop="fill_px" label="成交价" width="100" />
      <el-table-column prop="fee" label="手续费" width="100" />
      <el-table-column prop="state_display" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.state === 'filled' ? 'success' : row.state === 'live' ? 'warning' : row.state === 'canceled' ? 'info' : 'danger'" size="small">
            {{ row.state_display }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="source" label="来源" width="80" />
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.state === 'live'" size="small" type="danger" @click="cancel(row.id)">撤销</el-button>
          <el-button size="small" @click="sync(row.id)">同步</el-button>
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
import { getOrders, cancelOrder, syncOrder, syncPendingOrders } from '@/api/orders'
import { ElMessage, ElMessageBox } from 'element-plus'

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const filterState = ref('')
const filterSide = ref('')

const load = async () => {
  loading.value = true
  try {
    const params = { page: page.value }
    if (filterState.value) params.state = filterState.value
    if (filterSide.value) params.side = filterSide.value
    const res = await getOrders(params)
    tableData.value = res.results || res
    total.value = res.count || 0
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const cancel = async (id) => {
  try {
    await ElMessageBox.confirm('确认撤销此订单？', '确认', { type: 'warning' })
    await cancelOrder(id); ElMessage.success('已撤销'); load()
  } catch {}
}

const sync = async (id) => {
  try { await syncOrder(id); ElMessage.success('同步成功'); load() }
  catch (e) { ElMessage.error(e.message) }
}

const syncPending = async () => {
  try { await syncPendingOrders(); ElMessage.success('同步完成'); load() }
  catch (e) { ElMessage.error(e.message) }
}

watch([filterState, filterSide], () => { page.value = 1; load() })
onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
