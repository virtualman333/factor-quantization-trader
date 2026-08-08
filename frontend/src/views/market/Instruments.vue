<template>
  <div>
    <div class="page-header">
      <h2>交易品种</h2>
      <div class="header-actions">
        <el-radio-group v-model="instTypeFilter" size="small" @change="fetch">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="SPOT">现货</el-radio-button>
          <el-radio-button value="SWAP">合约</el-radio-button>
        </el-radio-group>
        <el-checkbox v-model="onlySelf" size="small" @change="fetch">只看自选</el-checkbox>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="syncInstruments('SPOT')">同步现货</el-button>
        <el-button type="success" :icon="Refresh" :loading="loading" @click="syncInstruments('SWAP')">同步合约</el-button>
      </div>
    </div>
    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <!-- 自选星标 -->
      <el-table-column width="56" align="center">
        <template #default="{ row }">
          <span
            class="fav-star"
            :class="{ on: isSelf(row.inst_id) }"
            :title="isSelf(row.inst_id) ? '取消自选' : '添加自选'"
            @click="toggleSelf(row.inst_id)"
          >{{ isSelf(row.inst_id) ? '★' : '☆' }}</span>
        </template>
      </el-table-column>
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
        :page-size="pageSize"
        :total="total"
        layout="total, sizes, prev, pager, next"
        :page-sizes="[50, 100, 200]"
        @size-change="onPageSizeChange"
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

// 自选存储 key：与 InstrumentSelect 组件共享，全站自选数据一致
const SELF_KEY = 'instrument_self_picks'
const MAX_SELF = 50

const router = useRouter()
const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const instTypeFilter = ref('')
const onlySelf = ref(false)

// ---------- 自选管理 ----------
const selfPicks = ref(JSON.parse(localStorage.getItem(SELF_KEY) || '[]'))

const isSelf = (id) => selfPicks.value.includes(id)

const persistSelf = () => {
  localStorage.setItem(SELF_KEY, JSON.stringify(selfPicks.value))
}

const toggleSelf = (id) => {
  selfPicks.value = isSelf(id)
    ? selfPicks.value.filter(x => x !== id)
    : [id, ...selfPicks.value].slice(0, MAX_SELF)
  persistSelf()
  // 若正处在"只看自选"且取消了当前自选，刷新列表移除该行
  if (onlySelf.value && !isSelf(id)) fetch()
}

// ---------- 数据加载 ----------
const fetch = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (instTypeFilter.value) params.inst_type = instTypeFilter.value
    const res = await getInstruments(params)
    let rows = res.results || res || []
    // 自选置顶
    rows = [...rows].sort((a, b) => {
      const sa = isSelf(a.inst_id) ? 0 : 1
      const sb = isSelf(b.inst_id) ? 0 : 1
      return sa - sb
    })
    if (onlySelf.value) {
      rows = rows.filter(r => isSelf(r.inst_id))
      total.value = rows.length
    } else {
      total.value = res.count || rows.length
    }
    tableData.value = rows
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const onPageSizeChange = () => {
  page.value = 1
  fetch()
}

// ---------- 跳转 ----------
const openKline = (row) => {
  router.push({
    path: '/market/klines',
    query: { inst_id: row.inst_id },
  })
}

const quickTrade = (row) => {
  router.push({
    path: '/market/klines',
    query: { inst_id: row.inst_id, trade: '1' },
  })
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
.page-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.header-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.fav-star {
  font-size: 18px;
  color: #c0c4cc;
  cursor: pointer;
  transition: all .2s;
  display: inline-block;
  padding: 2px 4px;
}
.fav-star:hover,
.fav-star.on {
  color: #e6a23c;
  transform: scale(1.15);
}
</style>
