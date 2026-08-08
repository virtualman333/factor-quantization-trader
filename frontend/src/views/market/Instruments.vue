<template>
  <div>
    <div class="page-header">
      <h2>交易品种</h2>
      <div>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="syncInstruments('SPOT')">同步现货</el-button>
        <el-button type="success" :icon="Refresh" :loading="loading" @click="syncInstruments('SWAP')">同步合约</el-button>
      </div>
    </div>
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column prop="inst_id" label="品种ID" width="150" />
      <el-table-column prop="inst_type_display" label="类型" width="80" />
      <el-table-column prop="base_ccy" label="基础币" width="80" />
      <el-table-column prop="quote_ccy" label="计价币" width="80" />
      <el-table-column prop="lot_sz" label="最小下单" width="100" />
      <el-table-column prop="tick_sz" label="价格精度" width="100" />
      <el-table-column prop="state" label="状态" width="80" />
      <el-table-column prop="is_active" label="活跃" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '是' : '否' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right" align="center">
        <template #default="{ row }">
          <el-button size="small" type="primary" :icon="TrendCharts" @click="openKline(row)">K线</el-button>
          <el-button size="small" type="success" @click="quickTrade(row)">交易</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="50"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="fetch"
      />
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'Instruments' })
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getInstruments, syncInstruments as syncApi } from '@/api/market'
import { ElMessage } from 'element-plus'
import { Refresh, TrendCharts } from '@element-plus/icons-vue'

const router = useRouter()
const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)

/** 跳转到 K 线页，带上品种 */
const openKline = (row) => {
  router.push({
    path: '/market/klines',
    query: { inst_id: row.inst_id },
  })
}

/** 跳转到 K 线页并打开快捷交易面板 */
const quickTrade = (row) => {
  router.push({
    path: '/market/klines',
    query: { inst_id: row.inst_id, trade: '1' },
  })
}

const fetch = async () => {
  loading.value = true
  try {
    const res = await getInstruments({ page: page.value })
    tableData.value = res.results || res
    total.value = res.count || 0
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const syncInstruments = async (instType) => {
  loading.value = true
  try {
    const res = await syncApi({ inst_type: instType })
    if (res.submitted) {
      ElMessage.success('品种同步任务已提交，正在后台拉取，完成后刷新列表')
      setTimeout(fetch, 3000)
    } else {
      ElMessage.success('同步成功')
      await fetch()
    }
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

onMounted(fetch)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
