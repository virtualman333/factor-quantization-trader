<template>
  <div class="kline-page">
    <!-- 顶部工具栏 -->
    <div class="page-header">
      <h2>
        K线数据
        <el-tag v-if="envLabel" :type="envType" size="small" effect="dark" style="margin-left:8px;vertical-align:middle">
          {{ envLabel }}
        </el-tag>
      </h2>
      <div class="header-right">
        <instrument-select v-model="instId" placeholder="搜索品种" width="180px" />
        <el-select v-model="bar" style="width:90px;margin-left:8px">
          <el-option v-for="b in bars" :key="b" :label="b" :value="b" />
        </el-select>
        <el-button-group style="margin-left:8px">
          <el-button :type="preloadSize === 500 ? 'primary' : ''" size="small" @click="switchPreload(500)">500条</el-button>
          <el-button :type="preloadSize === 1000 ? 'primary' : ''" size="small" @click="switchPreload(1000)">1000条</el-button>
          <el-button :type="preloadSize === 3000 ? 'primary' : ''" size="small" @click="switchPreload(3000)">3000条</el-button>
        </el-button-group>
        <el-button type="primary" :icon="Download" @click="fetchHistory" :loading="fetchLoading" style="margin-left:8px">拉取</el-button>
        <el-button :icon="Refresh" @click="reload" :loading="loading" style="margin-left:8px">刷新</el-button>
      </div>
    </div>

    <!-- 图表区域 -->
    <el-card style="margin-top:12px">
      <!-- 数据摘要栏 -->
      <div v-if="dataSummary" class="chart-toolbar">
        <div class="data-summary">
          <span class="summary-item">
            <span class="label">O</span>
            <span class="value">{{ dataSummary.open }}</span>
          </span>
          <span class="summary-item">
            <span class="label">H</span>
            <span class="value up">{{ dataSummary.high }}</span>
          </span>
          <span class="summary-item">
            <span class="label">L</span>
            <span class="value down">{{ dataSummary.low }}</span>
          </span>
          <span class="summary-item">
            <span class="label">C</span>
            <span class="value" :class="dataSummary.change >= 0 ? 'up' : 'down'">{{ dataSummary.close }}</span>
          </span>
          <span class="summary-item">
            <span class="label">涨跌</span>
            <span class="value" :class="dataSummary.change >= 0 ? 'up' : 'down'">
              {{ dataSummary.change >= 0 ? '+' : '' }}{{ dataSummary.changePercent }}%
            </span>
          </span>
          <span class="summary-item">
            <span class="label">振幅</span>
            <span class="value">{{ dataSummary.amplitude }}%</span>
          </span>
          <span class="summary-item">
            <span class="label">数据</span>
            <span class="value">{{ dataSummary.count }}条</span>
          </span>
        </div>
        <div class="chart-hint">
          <el-icon><Mouse /></el-icon>
          <span>滚轮缩放 | 拖拽滑动查看更多</span>
        </div>
      </div>
      <div class="chart-container">
        <div ref="chartRef" class="chart-box"></div>
        <!-- 加载状态 -->
        <div v-if="loading && !dataSummary" class="chart-loading-mask">
          <el-icon class="is-loading" :size="32"><Loading /></el-icon>
          <span>加载K线数据...</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { scrollKlines, fetchKlines as fetchApi } from '@/api/market'
import InstrumentSelect from '@/components/InstrumentSelect.vue'
import { useConnectionStore } from '@/stores/connection'
import { useRealtimeStore } from '@/stores/realtime'
import { ElMessage } from 'element-plus'
import { Download, Refresh, Mouse, Loading } from '@element-plus/icons-vue'
import { init, dispose } from 'klinecharts'

const connectionStore = useConnectionStore()
const realtimeStore = useRealtimeStore()
const envLabel = computed(() => connectionStore.envLabel)
const envType = computed(() => (connectionStore.environment === 'live' ? 'danger' : 'primary'))

const chartRef = ref(null)
const loading = ref(false)
const fetchLoading = ref(false)
const instId = ref('BTC-USDT')
const bar = ref('1H')
const preloadSize = ref(1000)
const bars = ['1m', '3m', '5m', '15m', '30m', '1H', '2H', '4H', '6H', '12H', '1D', '1W', '1M']

let chart = null
let resizeObserver = null
let realtimeUnsubscribe = null

const dataSummary = ref(null)

// ---------- 实时 K 线订阅 ----------
const candleKey = computed(() =>
  instId.value && bar.value ? `candle${bar.value}:${instId.value}` : ''
)

const onCandleUpdate = (payload) => {
  if (!chart) return
  const data = {
    timestamp: payload.timestamp,
    open: parseFloat(payload.open),
    high: parseFloat(payload.high),
    low: parseFloat(payload.low),
    close: parseFloat(payload.close),
    volume: parseFloat(payload.vol) || 0,
  }
  // timestamp 与最后一根相同则合并更新，更大则追加新 K 线
  chart.updateData(data)
  updateSummary()
}

const setupRealtime = () => {
  if (realtimeUnsubscribe) {
    realtimeUnsubscribe()
    realtimeUnsubscribe = null
  }
  if (!candleKey.value) return
  realtimeUnsubscribe = realtimeStore.subscribe(candleKey.value, onCandleUpdate)
}

const teardownRealtime = () => {
  if (realtimeUnsubscribe) {
    realtimeUnsubscribe()
    realtimeUnsubscribe = null
  }
}

// ---------- 数据摘要 ----------
const updateSummary = () => {
  if (!chart) return
  const list = chart.getDataList()
  if (!list || list.length === 0) {
    dataSummary.value = null
    return
  }
  const first = list[0]
  const last = list[list.length - 1]
  const highs = list.map(d => d.high)
  const lows = list.map(d => d.low)

  const open = first.open
  const high = Math.max(...highs)
  const low = Math.min(...lows)
  const close = last.close
  const change = close - open
  const changePercent = open !== 0 ? ((change / open) * 100).toFixed(2) : '0.00'
  const amplitude = low !== 0 ? (((high - low) / low) * 100).toFixed(2) : '0.00'

  dataSummary.value = {
    open: open.toFixed(2),
    high: high.toFixed(2),
    low: low.toFixed(2),
    close: close.toFixed(2),
    change,
    changePercent,
    amplitude,
    count: list.length,
  }
}

// ---------- 将后端数据转为 klinecharts 格式 ----------
const toChartData = (items) => {
  return items
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    .map(d => ({
      timestamp: new Date(d.timestamp).getTime(),
      open: parseFloat(d.open),
      high: parseFloat(d.high),
      low: parseFloat(d.low),
      close: parseFloat(d.close),
      volume: parseFloat(d.vol) || 0,
    }))
}

// ---------- 初始化图表 ----------
const initChart = () => {
  if (!chartRef.value) return

  chart = init(chartRef.value, {
    locale: 'zh-CN',
    thousandsSeparator: ',',
    timezone: 'Asia/Shanghai',
    styles: {
      grid: {
        show: true,
        horizontal: {
          show: true, style: 'dashed', size: 1, color: '#e8e8e8', dashedValue: [4, 4],
        },
        vertical: {
          show: true, style: 'dashed', size: 1, color: '#e8e8e8', dashedValue: [4, 4],
        },
      },
      candle: {
        type: 'candle_solid',
        bar: {
          upColor: '#26a69a', downColor: '#ef5350', noChangeColor: '#888888',
          upBorderColor: '#26a69a', downBorderColor: '#ef5350', noChangeBorderColor: '#888888',
          upWickColor: '#26a69a', downWickColor: '#ef5350', noChangeWickColor: '#888888',
        },
        priceMark: {
          show: true,
          high: { show: true, color: '#ef5350', textOffset: 4, textSize: 12, textFamily: 'Arial', textWeight: 'normal' },
          low: { show: true, color: '#26a69a', textOffset: 4, textSize: 12, textFamily: 'Arial', textWeight: 'normal' },
          last: {
            show: true, upColor: '#26a69a', downColor: '#ef5350', noChangeColor: '#888888',
            line: { show: true, size: 1, style: 'dashed', dashedValue: [6, 4] },
            text: { show: true, color: '#ffffff', size: 12, family: 'Arial', weight: 'bold', paddingLeft: 6, paddingTop: 2, paddingRight: 6, paddingBottom: 2, borderRadius: 4 },
          },
        },
        tooltip: {
          showRule: 'always', showType: 'standard', defaultValue: 'N/A',
          text: { color: '#333333', size: 12, family: 'Arial', weight: 'normal', marginLeft: 8, marginTop: 4, marginRight: 8, marginBottom: 4 },
        },
      },
      indicator: {
        lines: [
          { smooth: false, size: 1, color: '#f5a623' },
          { smooth: false, size: 1, color: '#7b68ee' },
          { smooth: false, size: 1, color: '#00bcd4' },
          { smooth: false, size: 1, color: '#2196f3' },
          { smooth: false, size: 1, color: '#e040fb' },
          { smooth: false, size: 1, color: '#ff7043' },
        ],
        ohlc: { upColor: '#26a69a', downColor: '#ef5350', noChangeColor: '#888888' },
        bars: [
          { style: 'fill', upColor: '#26a69a50', downColor: '#ef535050', noChangeColor: '#88888850', borderColor: 'transparent', borderSize: 0, borderStyle: 'solid', borderDashedValue: [] },
          { style: 'fill', upColor: '#26a69a50', downColor: '#ef535050', noChangeColor: '#88888850', borderColor: 'transparent', borderSize: 0, borderStyle: 'solid', borderDashedValue: [] },
        ],
        lastValueMark: {
          show: true,
          text: { show: true, color: '#ffffff', size: 11, family: 'Arial', weight: 'normal', paddingLeft: 4, paddingTop: 1, paddingRight: 4, paddingBottom: 1, borderRadius: 3 },
        },
        tooltip: {
          showRule: 'always', showName: true, showParams: true,
          text: { color: '#333333', size: 11, family: 'Arial', weight: 'normal', marginLeft: 6, marginTop: 2, marginRight: 6, marginBottom: 2 },
        },
      },
      xAxis: {
        show: true,
        axisLine: { show: true, size: 1, color: '#cccccc' },
        tickLine: { show: true, size: 1, color: '#cccccc', length: 4 },
        tickText: { show: true, color: '#666666', size: 11, family: 'Arial', weight: 'normal', marginStart: 4, marginEnd: 4 },
      },
      yAxis: {
        show: true, type: 'normal', position: 'right', inside: false, reverse: false,
        axisLine: { show: true, size: 1, color: '#cccccc' },
        tickLine: { show: true, size: 1, color: '#cccccc', length: 4 },
        tickText: { show: true, color: '#666666', size: 11, family: 'Arial', weight: 'normal', marginStart: 4, marginEnd: 4 },
      },
      separator: { size: 1, color: '#d0d0d0', fill: false, activeBackgroundColor: 'rgba(230, 230, 230, 0.3)' },
      crosshair: {
        show: true,
        horizontal: {
          show: true,
          line: { show: true, size: 1, color: '#999999', style: 'dashed', dashedValue: [4, 4] },
          text: { show: true, color: '#ffffff', size: 11, family: 'Arial', weight: 'normal', paddingLeft: 4, paddingTop: 2, paddingRight: 4, paddingBottom: 2, borderRadius: 3, backgroundColor: '#333333' },
        },
        vertical: {
          show: true,
          line: { show: true, size: 1, color: '#999999', style: 'dashed', dashedValue: [4, 4] },
          text: { show: true, color: '#ffffff', size: 11, family: 'Arial', weight: 'normal', paddingLeft: 4, paddingTop: 2, paddingRight: 4, paddingBottom: 2, borderRadius: 3, backgroundColor: '#333333' },
        },
      },
      overlay: {
        point: { color: '#ffffff', borderColor: '#2196f3', borderSize: 2, radius: 4, activeColor: '#2196f3', activeBorderColor: '#2196f3', activeBorderSize: 2, activeRadius: 6 },
        line: { smooth: false, size: 2, color: '#2196f3', style: 'solid', dashedValue: [] },
        rect: { style: 'stroke_fill', color: '#2196f315', borderColor: '#2196f3', borderSize: 1, borderStyle: 'solid', borderDashedValue: [], borderRadius: 0 },
        polygon: { style: 'stroke_fill', color: '#2196f315', borderColor: '#2196f3', borderSize: 1, borderStyle: 'solid', borderDashedValue: [] },
        circle: { style: 'stroke_fill', color: '#2196f315', borderColor: '#2196f3', borderSize: 1, borderStyle: 'solid', borderDashedValue: [] },
        arc: { style: 'solid', size: 2, color: '#2196f3', dashedValue: [] },
        text: { style: 'fill', color: '#ffffff', size: 13, family: 'Arial', weight: 'normal', borderStyle: 'solid', borderDashedValue: [], borderSize: 0, borderColor: 'transparent', borderRadius: 3, backgroundColor: '#2196f3' },
      },
    },
  })

  if (chart) {
    // MA 均线叠在主图上
    chart.createIndicator(
      { name: 'MA', calcParams: [5, 10, 20, 60], shortName: 'MA' },
      true,
      { id: 'candle_pane' }
    )
    // MACD 副图
    chart.createIndicator('MACD', false, { height: 180, minHeight: 60 })
    // RSI 副图
    chart.createIndicator('RSI', false, { height: 160, minHeight: 50 })

    // 设置滑动加载回调
    chart.setLoadDataCallback(loadDataCallback)
  }
}

// ---------- 滑动加载回调：核心逻辑 ----------
const loadDataCallback = async (params) => {
  const { type, data, callback } = params
  const scrollParams = {
    inst_id: instId.value,
    bar: bar.value,
    limit: 500,
    auto_fetch: 'true',
  }

  try {
    let res
    if (type === 'forward') {
      scrollParams.before = String(data.timestamp)
      res = await scrollKlines(scrollParams)
    } else if (type === 'backward') {
      scrollParams.after = String(data.timestamp)
      res = await scrollKlines(scrollParams)
    } else {
      scrollParams.limit = preloadSize.value
      res = await scrollKlines(scrollParams)
    }

    const items = res?.results || []
    const hasMore = res?.has_more ?? false
    const fetching = res?.fetching ?? false

    if (fetching && items.length === 0) {
      // 后台正在从 OKX 拉取，暂时无数据，提示稍后滑动
      ElMessage.info('正在从交易所拉取数据，请稍后再滑动加载')
      callback([], false)
    } else if (items.length > 0) {
      callback(toChartData(items), hasMore)
    } else {
      callback([], false)
    }

    await nextTick()
    updateSummary()
  } catch (e) {
    ElMessage.error(`加载失败: ${e.message}`)
    callback([], false)
  }
}

// ---------- 重建图表（品种/周期切换时） ----------
const recreateChart = () => {
  if (chart) {
    dispose(chart)
    chart = null
  }
  dataSummary.value = null
  initChart()
  setupRealtime()
}

// ---------- 切换预加载数量 ----------
const switchPreload = (size) => {
  preloadSize.value = size
  recreateChart()
}

// ---------- 手动拉取更多历史数据 ----------
const fetchHistory = async () => {
  if (!instId.value) { ElMessage.warning('请输入品种ID'); return }
  fetchLoading.value = true
  try {
    const res = await fetchApi({
      inst_id: instId.value,
      bar: bar.value,
      limit: 1000,
      is_history: true,
    })
    ElMessage.success(`已从 OKX 拉取 ${res.data?.count || ''} 条数据并存入数据库`)
    recreateChart()
  } catch (e) {
    ElMessage.error(`拉取失败: ${e.message}`)
  }
  fetchLoading.value = false
}

// ---------- 刷新（重建图表） ----------
const reload = () => {
  recreateChart()
}

// ---------- ResizeObserver ----------
const setupResizeObserver = () => {
  if (!chartRef.value) return
  resizeObserver = new ResizeObserver(() => {
    if (chart) {
      requestAnimationFrame(() => chart.resize())
    }
  })
  resizeObserver.observe(chartRef.value)
}

// ---------- 品种/周期/环境变化时重建 ----------
watch([instId, bar, () => connectionStore.environment], () => {
  recreateChart()
})

// ---------- 生命周期 ----------
onMounted(async () => {
  await nextTick()
  initChart()
  setupResizeObserver()
  setupRealtime()
})

onBeforeUnmount(() => {
  teardownRealtime()
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (chart) {
    dispose(chart)
    chart = null
  }
})
</script>

<style scoped>
.kline-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
}

.chart-container {
  position: relative;
  min-height: 400px;
}

.chart-box {
  width: 100%;
  height: calc(100vh - 220px);
  min-height: 600px;
}

.chart-loading-mask {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.85);
  z-index: 10;
  gap: 12px;
  color: #909399;
  font-size: 14px;
}

.chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #fafafa;
  border-bottom: 1px solid #ebeef5;
  flex-wrap: wrap;
  gap: 4px;
}

.data-summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
}

.summary-item {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
  border: 1px solid #ebeef5;
}

.summary-item .label {
  color: #909399;
  font-weight: 600;
  margin-right: 6px;
  min-width: 20px;
}

.summary-item .value {
  color: #303133;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-weight: 500;
}

.summary-item .value.up { color: #26a69a; }
.summary-item .value.down { color: #ef5350; }

.chart-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #b0b0b0;
  font-size: 12px;
}

:deep(.el-card__body) {
  padding: 0;
}

:deep(.el-button-group .el-button) {
  margin-left: 0;
}
</style>
