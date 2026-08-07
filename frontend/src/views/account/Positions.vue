<template>
  <div>
    <div class="page-header">
      <h2>持仓管理</h2>
      <div>
        <el-select v-model="instType" style="width:120px">
          <el-option label="全部" value="" />
          <el-option label="现货" value="SPOT" />
          <el-option label="合约" value="SWAP" />
        </el-select>
        <el-button type="primary" :icon="Camera" :loading="loading" @click="takeSnapshot" style="margin-left:8px">保存快照</el-button>
        <el-button type="success" :icon="Refresh" :loading="loading" @click="loadLive" style="margin-left:8px">实时持仓</el-button>
      </div>
    </div>
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column prop="inst_id" label="品种" width="130" />
      <el-table-column prop="pos_side" label="方向" width="80">
        <template #default="{ row }">
          <el-tag :type="row.pos_side === 'long' ? 'success' : 'danger'" size="small">{{ row.pos_side }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="pos" label="持仓量" width="120" />
      <el-table-column prop="avg_px" label="开仓均价" width="120" />
      <el-table-column prop="mark_px" label="标记价格" width="120" />
      <el-table-column prop="upl" label="未实现盈亏" width="140">
        <template #default="{ row }">
          <span :style="{ color: parseFloat(row.upl) >= 0 ? '#67c23a' : '#f56c6c' }">{{ row.upl }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="margin" label="保证金" width="120" />
      <el-table-column prop="leverage" label="杠杆" width="80" />
      <el-table-column prop="liq_px" label="强平价格" width="120" />
      <el-table-column prop="snapshot_time" label="快照时间" width="180" />
    </el-table>
    <div class="pagination">
      <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="prev, pager, next, total" @current-change="load" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getPositions, savePositionSnapshot, getLivePositions } from '@/api/account'
import { ElMessage } from 'element-plus'

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const instType = ref('')

const load = async () => {
  loading.value = true
  try {
    const params = { page: page.value }
    if (instType.value) params.inst_type = instType.value
    const res = await getPositions(params)
    tableData.value = res.results || res
    total.value = res.count || 0
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const takeSnapshot = async () => {
  loading.value = true
  try {
    await savePositionSnapshot({ inst_type: instType.value || undefined })
    ElMessage.success('快照已保存'); await load()
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const loadLive = async () => {
  loading.value = true
  try {
    const params = {}
    if (instType.value) params.inst_type = instType.value
    const res = await getLivePositions(params)
    const positions = res?.data || []
    tableData.value = positions.map(p => ({
      inst_id: p.instId, pos_side: p.posSide, pos: p.pos,
      avg_px: p.avgPx, mark_px: p.markPx, upl: p.upl,
      margin: p.margin, leverage: p.lever, liq_px: p.liqPx,
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
