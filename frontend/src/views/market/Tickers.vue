<template>
  <div>
    <div class="page-header">
      <h2>实时行情</h2>
      <div>
        <instrument-select v-model="instId" placeholder="搜索品种" width="200px" />
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="refresh" style="margin-left:8px">刷新行情</el-button>
        <el-tag :type="realtimeStore.serverConnected ? 'success' : 'warning'" size="small" style="margin-left:8px">
          {{ realtimeStore.serverConnected ? '实时推送中' : '实时通道未连接' }}
        </el-tag>
      </div>
    </div>

    <!-- 自选品种统计 -->
    <el-card shadow="never" class="watch-card" style="margin-top:16px">
      <div class="watch-header">
        <span class="watch-title">自选品种统计</span>
        <instrument-select
          v-model="watchIds"
          multiple
          allow-create
          collapse-tags
          placeholder="搜索并添加品种（可多选）"
          width="420px"
          @change="onWatchChange"
        />
      </div>

      <!-- 汇总统计 -->
      <div v-if="watchIds.length" class="watch-summary">
        <span class="sum-item">品种数 <b>{{ watchIds.length }}</b></span>
        <span class="sum-item up">上涨 <b>{{ upCount }}</b></span>
        <span class="sum-item down">下跌 <b>{{ downCount }}</b></span>
        <span class="sum-item">平均涨跌 <b :class="avgChange >= 0 ? 'up' : 'down'">{{ avgChange >= 0 ? '+' : '' }}{{ avgChange }}%</b></span>
      </div>

      <!-- 品种统计卡片 -->
      <div v-if="watchIds.length" class="watch-grid">
        <div v-for="t in selectedTickers" :key="t.inst_id" class="watch-item">
          <div class="wi-head">
            <span class="wi-name">{{ t.inst_id }}</span>
            <el-tag size="small" :type="changePct(t) >= 0 ? 'success' : 'danger'">
              {{ changePct(t) >= 0 ? '+' : '' }}{{ changePct(t) }}%
            </el-tag>
          </div>
          <div class="wi-last" :style="{ color: changePct(t) >= 0 ? '#f56c6c' : '#26a69a' }">{{ t.last || '--' }}</div>
          <div class="wi-sub">高 {{ t.high_24h || '--' }} / 低 {{ t.low_24h || '--' }}</div>
          <div class="wi-vol">24h量 {{ t.vol_24h || '--' }}</div>
        </div>
      </div>
      <el-empty v-else description="在上方搜索并选择品种，即可实时跟踪统计" :image-size="60" />
    </el-card>

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
defineOptions({ name: 'Tickers' })
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { getTickers, refreshTicker } from '@/api/market'
import InstrumentSelect from '@/components/InstrumentSelect.vue'
import { useRealtimeStore } from '@/stores/realtime'
import { ElMessage } from 'element-plus'

const realtimeStore = useRealtimeStore()
const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const instId = ref('')
const unsubscribers = []

// ---------- 自选品种统计 ----------
const WATCH_KEY = 'tickers_watch_list'
const watchIds = ref(JSON.parse(localStorage.getItem(WATCH_KEY) || '[]'))
const selectedTickers = ref([])
const watchSubscribers = []

const changePct = (row) => {
  const last = parseFloat(row?.last)
  const open = parseFloat(row?.open_24h)
  if (!last || !open) return 0
  return parseFloat(((last - open) / open * 100).toFixed(2))
}

const upCount = computed(() => selectedTickers.value.filter(t => changePct(t) > 0).length)
const downCount = computed(() => selectedTickers.value.filter(t => changePct(t) < 0).length)
const avgChange = computed(() => {
  const arr = selectedTickers.value.map(t => changePct(t))
  if (!arr.length) return 0
  return parseFloat((arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(2))
})

const onWatchChange = (val) => {
  localStorage.setItem(WATCH_KEY, JSON.stringify(val))
  loadWatchTickers()
}

const loadWatchTickers = async () => {
  if (!watchIds.value.length) {
    selectedTickers.value = []
    return
  }
  try {
    const res = await getTickers({ inst_ids: watchIds.value.join(','), page_size: watchIds.value.length })
    const rows = res.results || res || []
    // 按 watchIds 顺序排列，缺失的品种补空对象
    selectedTickers.value = watchIds.value.map(id =>
      rows.find(r => r.inst_id === id) || { inst_id: id }
    )
  } catch (e) { ElMessage.error(e.message) }
  subscribeWatch()
}

const subscribeWatch = () => {
  watchSubscribers.forEach(fn => fn())
  watchSubscribers.length = 0
  for (const t of selectedTickers.value) {
    if (!t?.inst_id) continue
    watchSubscribers.push(
      realtimeStore.subscribe(`tickers:${t.inst_id}`, (p) => {
        const target = selectedTickers.value.find(r => r.inst_id === p.inst_id)
        if (!target) return
        Object.assign(target, {
          last: p.last,
          open_24h: p.open_24h,
          high_24h: p.high_24h,
          low_24h: p.low_24h,
          vol_24h: p.vol_24h,
          bid_px: p.bid_px,
          bid_sz: p.bid_sz,
          ask_px: p.ask_px,
          ask_sz: p.ask_sz,
        })
      })
    )
  }
}

// ---------- 实时订阅当前页所有品种 ----------
const subscribeCurrentPage = () => {
  unsubscribers.forEach((fn) => fn())
  unsubscribers.length = 0
  for (const row of tableData.value) {
    if (!row?.inst_id) continue
    unsubscribers.push(
      realtimeStore.subscribe(`tickers:${row.inst_id}`, (p) => {
        const target = tableData.value.find((r) => r.inst_id === p.inst_id)
        if (!target) return
        Object.assign(target, {
          last: p.last,
          open_24h: p.open_24h,
          high_24h: p.high_24h,
          low_24h: p.low_24h,
          vol_24h: p.vol_24h,
          bid_px: p.bid_px,
          bid_sz: p.bid_sz,
          ask_px: p.ask_px,
          ask_sz: p.ask_sz,
        })
      })
    )
  }
}

const load = async () => {
  loading.value = true
  try {
    const params = { page: page.value }
    if (instId.value) params.instrument__inst_id = instId.value
    const res = await getTickers(params)
    tableData.value = res.results || res
    total.value = res.count || 0
    subscribeCurrentPage()
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

onMounted(() => {
  load()
  if (watchIds.value.length) {
    loadWatchTickers()
  }
})
onBeforeUnmount(() => {
  unsubscribers.forEach((fn) => fn())
  watchSubscribers.forEach((fn) => fn())
  watchSubscribers.length = 0
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }

.watch-card :deep(.el-card__body) { padding: 14px 16px; }
.watch-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.watch-title { font-size: 15px; font-weight: 600; }

.watch-summary {
  display: flex; align-items: center; gap: 20px;
  margin-top: 12px; padding: 8px 12px;
  background: #fafafa; border: 1px solid #ebeef5; border-radius: 6px;
}
.sum-item { font-size: 13px; color: #606266; }
.sum-item b { font-size: 14px; margin-left: 2px; }
.sum-item.up b { color: #f56c6c; }
.sum-item.down b { color: #26a69a; }

.watch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.watch-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fff;
  transition: box-shadow .2s;
}
.watch-item:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); }
.wi-head { display: flex; align-items: center; justify-content: space-between; }
.wi-name { font-size: 13px; font-weight: 600; color: #303133; }
.wi-last {
  font-size: 20px; font-weight: bold; margin-top: 6px;
  font-family: 'Consolas', 'Monaco', monospace;
}
.wi-sub { margin-top: 4px; font-size: 12px; color: #909399; }
.wi-vol { margin-top: 2px; font-size: 12px; color: #909399; }
</style>
