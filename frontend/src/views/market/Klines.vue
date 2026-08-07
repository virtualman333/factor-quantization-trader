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
        <!-- 主题切换 -->
        <el-tooltip content="切换主题" placement="bottom">
          <el-button :icon="chartTheme === 'dark' ? Sunny : Moon" circle @click="toggleTheme" style="margin-left:8px" />
        </el-tooltip>
        <el-button type="primary" text @click="showInsights = !showInsights">多周期/对比</el-button>
        <el-button type="primary" :icon="Download" @click="fetchHistory" :loading="fetchLoading" style="margin-left:8px">拉取</el-button>
        <el-button :icon="Refresh" @click="reload" :loading="loading" style="margin-left:8px">刷新</el-button>
      </div>
    </div>

    <!-- 回测买卖点标记信息栏 -->
    <el-alert v-if="backtestInfo" class="backtest-banner" type="warning" :closable="false" show-icon>
      <template #title>
        <div class="backtest-banner-content">
          <span class="backtest-label">
            <el-icon><DataLine /></el-icon>
            回测标记：{{ backtestInfo.strategy_name }}
          </span>
          <span class="backtest-stat">收益
            <b :style="{ color: parseFloat(backtestInfo.total_return) >= 0 ? '#67c23a' : '#f56c6c' }">
              {{ (backtestInfo.total_return * 100).toFixed(2) }}%
            </b>
          </span>
          <span class="backtest-stat">交易 {{ backtestInfo.total_trades }}次</span>
          <span class="backtest-stat">胜率 {{ (backtestInfo.win_rate * 100).toFixed(1) }}%</span>
          <span class="backtest-stat" v-if="backtestTrades.length">当前品种 {{ backtestTrades.length }}个标记</span>
          <el-button size="small" text type="danger" :icon="Close" @click="clearBacktest">清除标记</el-button>
        </div>
      </template>
    </el-alert>

    <!-- 多周期联动 / 品种对比面板 -->
    <el-card v-if="showInsights" style="margin-top:12px">
      <template #header>
        <div class="insights-header">
          <span>多周期联动</span>
          <el-radio-group v-model="insightMode" size="small">
            <el-radio-button value="periods">多周期</el-radio-button>
            <el-radio-button value="compare">品种对比</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <template v-if="insightMode === 'periods'">
        <el-row :gutter="12">
          <el-col :span="6" v-for="p in insightPeriods" :key="p">
            <div class="mini-chart-title">{{ p }}</div>
            <div :ref="el => setMiniChartRef(p, el)" class="mini-chart" @click="switchBar(p)"></div>
          </el-col>
        </el-row>
      </template>
      <template v-else>
        <div class="compare-bar">
          <instrument-select v-model="compareInst" placeholder="选择对比品种" width="220px" />
          <el-button size="small" type="primary" @click="loadCompare" :loading="compareLoading">对比</el-button>
        </div>
        <div ref="compareChartRef" class="compare-chart"></div>
      </template>
    </el-card>

    <!-- 指标/画线工具条 -->
    <el-card style="margin-top:12px">
      <div class="toolbar-row">
        <div class="toolbar-group">
          <span class="toolbar-label">主图指标</span>
          <term-tip :term-key="mainIndicator === 'none' ? 'ma' : mainIndicator" />
          <el-radio-group v-model="mainIndicator" size="small" @change="applyMainIndicator">
            <el-radio-button value="none">无</el-radio-button>
            <el-radio-button value="ma">MA</el-radio-button>
            <el-radio-button value="ema">EMA</el-radio-button>
            <el-radio-button value="boll">BOLL</el-radio-button>
          </el-radio-group>
        </div>
        <div class="toolbar-group">
          <span class="toolbar-label">副图指标</span>
          <term-tip :term-key="subIndicator === 'none' ? 'macd' : subIndicator" />
          <el-radio-group v-model="subIndicator" size="small" @change="applySubIndicator">
            <el-radio-button value="none">无</el-radio-button>
            <el-radio-button value="macd">MACD</el-radio-button>
            <el-radio-button value="kdj">KDJ</el-radio-button>
            <el-radio-button value="rsi">RSI</el-radio-button>
            <el-radio-button value="wr">WR</el-radio-button>
          </el-radio-group>
        </div>
        <div class="toolbar-group">
          <span class="toolbar-label">画线</span>
          <el-radio-group v-model="drawMode" size="small" @change="applyDrawMode">
            <el-radio-button value="none">关闭</el-radio-button>
            <el-radio-button value="segment">趋势线</el-radio-button>
            <el-radio-button value="horizontalStraightLine">水平线</el-radio-button>
            <el-radio-button value="fibonacciLine">斐波那契</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </el-card>

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
          <span class="desktop-only">滚轮缩放 | 拖拽滑动查看更多</span>
          <span class="mobile-only">双指缩放 | 单指拖动查看更多</span>
        </div>
      </div>
      <div class="chart-container">
        <div ref="chartRef" class="chart-box touch-action-none"></div>
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
import { useRoute, useRouter } from 'vue-router'
import { scrollKlines, fetchKlines as fetchApi } from '@/api/market'
import { getBacktestDetail } from '@/api/strategy'
import InstrumentSelect from '@/components/InstrumentSelect.vue'
import { useConnectionStore } from '@/stores/connection'
import { useRealtimeStore } from '@/stores/realtime'
import { ElMessage } from 'element-plus'
import { Download, Refresh, Mouse, Loading, Sunny, Moon, Close, DataLine } from '@element-plus/icons-vue'
import { init, dispose, registerOverlay } from 'klinecharts'
import * as echarts from 'echarts'

// ===== 注册买卖点标记 overlay（全局只注册一次） =====
let tradeMarkerRegistered = false
function ensureTradeMarkerRegistered() {
  if (tradeMarkerRegistered) return
  tradeMarkerRegistered = true
  registerOverlay({
    name: 'tradeMarker',
    totalStep: 1,
    needDefaultPointFigure: false,
    createPointFigures: ({ overlay, coordinates }) => {
      if (!coordinates || !coordinates.length) return []
      const figures = []
      const trades = overlay.extendData || []
      coordinates.forEach((coord, i) => {
        const trade = trades[i] || {}
        const isBuy = trade.action === 'buy'
        const color = isBuy ? '#26a69a' : '#ef5350'
        // 买入标记在 K 线下方，卖出标记在上方
        const y = isBuy ? coord.y + 22 : coord.y - 22
        figures.push({
          key: `marker_${i}`,
          type: 'text',
          attrs: { x: coord.x, y, text: isBuy ? '买' : '卖' },
          styles: {
            color: '#fff', size: 11, family: 'Arial', weight: 'bold',
            backgroundColor: color, borderRadius: 3,
            paddingLeft: 4, paddingTop: 2, paddingRight: 4, paddingBottom: 2,
          },
        })
      })
      return figures
    },
  })
}

const route = useRoute()
const router = useRouter()
const connectionStore = useConnectionStore()
const realtimeStore = useRealtimeStore()
const envLabel = computed(() => connectionStore.envLabel)
const envType = computed(() => (connectionStore.environment === 'live' ? 'danger' : 'primary'))

const chartRef = ref(null)
const loading = ref(false)
const fetchLoading = ref(false)
const instId = ref(route.query.inst_id || 'BTC-USDT')
const bar = ref('1H')
const preloadSize = ref(1000)
const bars = ['1m', '3m', '5m', '15m', '30m', '1H', '2H', '4H', '6H', '12H', '1D', '1W', '1M']

// 主题与指标状态
const chartTheme = ref(localStorage.getItem('kline_theme') || 'dark')
const mainIndicator = ref('ma')
const subIndicator = ref('macd')
const drawMode = ref('none')

// 多周期/对比
const showInsights = ref(false)
const insightMode = ref('periods')
const insightPeriods = ['1m', '15m', '1H', '1D']
const miniCharts = {}
const miniChartEls = {}
const compareInst = ref('ETH-USDT')
const compareLoading = ref(false)
let compareChart = null

let chart = null
let resizeObserver = null
let realtimeUnsubscribe = null
let subIndicatorPaneId = null

// 回测买卖点标记状态
const backtestId = ref(route.query.backtest_id ? Number(route.query.backtest_id) : null)
const backtestInfo = ref(null)
const backtestTrades = ref([])

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

// ---------- 回测买卖点标记 ----------
const fetchBacktestDetail = async () => {
  if (!backtestId.value) return
  try {
    const data = await getBacktestDetail(backtestId.value)
    backtestInfo.value = data
    // 按当前品种过滤交易明细
    const allTrades = data.trade_detail || []
    backtestTrades.value = allTrades.filter(t => t.symbol === instId.value)
    if (backtestTrades.value.length === 0 && allTrades.length > 0) {
      ElMessage.info(`回测共 ${allTrades.length} 笔交易，当前品种 ${instId.value} 无匹配`)
    }
  } catch (e) {
    ElMessage.error(`加载回测数据失败: ${e.message}`)
  }
}

const applyBacktestOverlay = () => {
  if (!chart) return
  // 先移除已有的买卖点标记
  chart.removeOverlay({ name: 'tradeMarker' })
  if (!backtestTrades.value.length) return
  // 创建单个 overlay，points 为所有交易点，extendData 为交易明细数组
  const points = backtestTrades.value.map(t => ({
    timestamp: new Date(t.timestamp).getTime(),
    value: parseFloat(t.price),
  }))
  chart.createOverlay({
    name: 'tradeMarker',
    points,
    extendData: backtestTrades.value,
    zLevel: 10,
  })
}

const clearBacktest = () => {
  if (chart) chart.removeOverlay({ name: 'tradeMarker' })
  backtestId.value = null
  backtestInfo.value = null
  backtestTrades.value = []
  // 清除 URL 中的回测参数
  const query = { ...route.query }
  delete query.backtest_id
  delete query.inst_id
  router.replace({ query })
}

// ---------- 主动加载初始数据（klinecharts v9 的 setLoadDataCallback 不会自动触发初次加载） ----------
const initialLoad = async () => {
  try {
    loading.value = true
    const res = await scrollKlines({
      inst_id: instId.value,
      bar: bar.value,
      limit: preloadSize.value,
      auto_fetch: 'true',
    })
    const items = res?.results || []
    if (items.length > 0 && chart) {
      chart.applyNewData(toChartData(items), res?.has_more ?? false)
      await nextTick()
      updateSummary()
      // 应用回测买卖点标记
      applyBacktestOverlay()
    } else if (res?.fetching) {
      ElMessage.info('正在从交易所拉取数据，请稍后再滑动加载')
    }
  } catch (e) {
    ElMessage.error(`加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
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
    // 按主题设置默认配置
    chart.setStyles(getThemeStyles())
    // 主图指标
    if (mainIndicator.value === 'ma') {
      chart.createIndicator(
        { name: 'MA', calcParams: [5, 10, 20, 60], shortName: 'MA' },
        true,
        { id: 'candle_pane' }
      )
    } else if (mainIndicator.value === 'ema') {
      chart.createIndicator(
        { name: 'EMA', calcParams: [7, 25, 99], shortName: 'EMA' },
        true,
        { id: 'candle_pane' }
      )
    } else if (mainIndicator.value === 'boll') {
      chart.createIndicator('BOLL', true, { id: 'candle_pane' })
    }
    // 副图指标
    applySubIndicator()

    // 设置滑动加载回调（仅处理左右滚动的 forward/backward）
    chart.setLoadDataCallback(loadDataCallback)
  }
}

// ---------- 主题与指标 ----------
const getThemeStyles = () => {
  if (chartTheme.value === 'dark') {
    return {
      grid: { horizontal: { color: '#1e222d' }, vertical: { color: '#1e222d' } },
      candle: {
        bar: { upColor: '#26a69a', downColor: '#ef5350', noChangeColor: '#888888' },
      },
      indicator: { lines: [{ color: '#ef5350', size: 1 }] },
    }
  }
  return {
    grid: { horizontal: { color: '#e5e6eb' }, vertical: { color: '#f5f7fa' } },
    candle: {
      bar: { upColor: '#f26d28', downColor: '#2da7ff', noChangeColor: '#888888' },
    },
  }
}

const toggleTheme = () => {
  chartTheme.value = chartTheme.value === 'dark' ? 'light' : 'dark'
  localStorage.setItem('kline_theme', chartTheme.value)
  if (chart) chart.setStyles(getThemeStyles())
}

const applyMainIndicator = (val) => {
  if (!chart) return
  chart.removeIndicator('candle_pane', 'MA')
  chart.removeIndicator('candle_pane', 'EMA')
  chart.removeIndicator('candle_pane', 'BOLL')
  if (val === 'ma') {
    chart.createIndicator({ name: 'MA', calcParams: [5, 10, 20, 60], shortName: 'MA' }, true, { id: 'candle_pane' })
  } else if (val === 'ema') {
    chart.createIndicator({ name: 'EMA', calcParams: [7, 25, 99], shortName: 'EMA' }, true, { id: 'candle_pane' })
  } else if (val === 'boll') {
    chart.createIndicator('BOLL', true, { id: 'candle_pane' })
  }
}

const applySubIndicator = (val) => {
  const target = val || subIndicator.value
  if (!chart) return
  // 移除旧副图指标（v9 没有 getPane/removePane，用 removeIndicator + paneId 管理）
  if (subIndicatorPaneId) {
    chart.removeIndicator(subIndicatorPaneId)
    subIndicatorPaneId = null
  }
  if (target === 'none') return
  const configs = {
    macd: 'MACD', kdj: 'KDJ', rsi: 'RSI', wr: 'WR',
  }
  const name = configs[target]
  if (!name) return
  // 复用固定 paneId，避免切换时创建多个空 pane
  subIndicatorPaneId = 'sub_indicator_pane'
  chart.createIndicator(name, false, { id: subIndicatorPaneId, height: 120, minHeight: 50 })
}

// ---------- 多周期联动 ----------
const setMiniChartRef = (period, el) => {
  if (!el) return
  miniChartEls[period] = el
}

const switchBar = (p) => {
  bar.value = p
  // 触发 watch 重建图表
  recreateChart()
  ElMessage.success(`已切换到 ${p} 周期`)
}

const loadMiniCharts = async () => {
  await nextTick()
  for (const p of insightPeriods) {
    const el = miniChartEls[p]
    if (!el) continue
    try {
      const res = await scrollKlines({ inst_id: instId.value, bar: p, limit: 120, auto_fetch: 'false' })
      const items = res?.results || []
      if (!items.length) continue
      const chart = miniCharts[p] || echarts.init(el)
      miniCharts[p] = chart
      const data = items.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
      chart.setOption({
        animation: false,
        grid: { left: 4, right: 4, top: 4, bottom: 4 },
        xAxis: { type: 'category', show: false, data: data.map(d => d.timestamp) },
        yAxis: { type: 'value', show: false, scale: true },
        tooltip: { trigger: 'axis', formatter: (ps) => `${ps[0].axisValue}<br/>${Number(ps[0].data).toFixed(2)}` },
        series: [{
          type: 'line', data: data.map(d => parseFloat(d.close)),
          showSymbol: false, lineStyle: { width: 1.5, color: '#409eff' },
        }],
      })
    } catch { /* 忽略单周期加载失败 */ }
  }
}

const loadCompare = async () => {
  if (!compareInst.value || compareInst.value === instId.value) {
    ElMessage.warning('请选择不同的对比品种'); return
  }
  compareLoading.value = true
  try {
    await nextTick()
    const el = document.querySelector('.compare-chart')
    if (!el) return
    // 复用 echarts 实例，避免内存泄漏
    if (!compareChart) compareChart = echarts.init(el)
    // 拉取两个品种数据
    const [mainRes, cmpRes] = await Promise.all([
      scrollKlines({ inst_id: instId.value, bar: bar.value, limit: 300, auto_fetch: 'false' }),
      scrollKlines({ inst_id: compareInst.value, bar: bar.value, limit: 300, auto_fetch: 'false' }),
    ])
    const main = (mainRes?.results || []).sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    const cmp = (cmpRes?.results || []).sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    if (!main.length || !cmp.length) { ElMessage.warning('对比数据不足'); return }

    // 归一化到 100 起点
    const baseMain = parseFloat(main[0].close) || 1
    const baseCmp = parseFloat(cmp[0].close) || 1
    const mainNorm = main.map(d => (parseFloat(d.close) / baseMain) * 100)
    const cmpNorm = cmp.map(d => (parseFloat(d.close) / baseCmp) * 100)

    compareChart.setOption({
      animation: false,
      color: ['#409eff', '#f56c6c'],
      tooltip: { trigger: 'axis' },
      legend: { data: [instId.value, compareInst.value] },
      grid: { left: 50, right: 20, top: 30, bottom: 40 },
      xAxis: { type: 'category', data: main.map(d => d.timestamp), boundaryGap: false },
      yAxis: { type: 'value', scale: true, name: '归一化(100)' },
      series: [
        { name: instId.value, type: 'line', data: mainNorm, showSymbol: false, lineStyle: { width: 2 } },
        { name: compareInst.value, type: 'line', data: cmpNorm, showSymbol: false, lineStyle: { width: 2 } },
      ],
    })
  } catch (e) { ElMessage.error(e.message) }
  compareLoading.value = false
}

const drawOverlays = []

const applyDrawMode = (val) => {
  if (!chart) return
  if (val === 'none') {
    // 清除所有画线
    for (const id of drawOverlays) chart.removeOverlay({ id })
    drawOverlays.length = 0
    drawMode.value = 'none'
    return
  }
  // 在图表中段创建一条画线
  const kls = chart.getDataList()
  if (!kls.length) return
  const mid = Math.floor(kls.length / 2)
  const k = kls[mid]
  const k2 = kls[Math.min(mid + 20, kls.length - 1)]
  const id = chart.createOverlay({
    name: val,
    points: [
      { timestamp: k.timestamp, value: k.close },
      { timestamp: k2.timestamp, value: k2.close },
    ],
  })
  if (id) drawOverlays.push(id)
}

// ---------- 滑动加载回调：核心逻辑 ----------
// klinecharts v9 触发规则：
//   - 首次加载会触发 type='forward'，但 data=null（因为 dataList[0] 不存在）
//   - 向左滚动到边缘触发 type='forward'，data 有 timestamp
//   - 向右滚动到边缘触发 type='backward'，data 有 timestamp
const loadDataCallback = async (params) => {
  const { type, data, callback } = params
  if (typeof callback !== 'function') return
  const scrollParams = {
    inst_id: instId.value,
    bar: bar.value,
    auto_fetch: 'true',
  }

  try {
    let res
    if ((type === 'forward' || type === 'backward') && data?.timestamp) {
      // 滚动加载（带游标）
      if (type === 'forward') {
        scrollParams.before = String(data.timestamp)
      } else {
        scrollParams.after = String(data.timestamp)
      }
      scrollParams.limit = 500
      res = await scrollKlines(scrollParams)
    } else {
      // 初始加载 (data 为 null，走默认 limit)
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
    // 数据加载后应用回测买卖点标记
    if (items.length > 0) applyBacktestOverlay()
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
  subIndicatorPaneId = null
  initChart()
  setupRealtime()
  initialLoad()
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
    if (res.submitted) {
      ElMessage.success('已提交后台拉取任务，稍后点击「刷新」查看最新K线')
    } else {
      ElMessage.success(`已从 OKX 拉取 ${res.count || ''} 条数据并存入数据库`)
    }
    // 等待后台写入部分数据后重载图表
    setTimeout(() => {
      recreateChart()
      fetchLoading.value = false
    }, 2000)
  } catch (e) {
    ElMessage.error(`拉取失败: ${e.message}`)
    fetchLoading.value = false
  }
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

// ---------- 品种变化时重新过滤回测交易 ----------
watch(instId, (newVal) => {
  if (backtestInfo.value) {
    const allTrades = backtestInfo.value.trade_detail || []
    backtestTrades.value = allTrades.filter(t => t.symbol === newVal)
  }
})

// ---------- 品种/周期/环境变化时重建 ----------
watch([instId, bar, () => connectionStore.environment], () => {
  recreateChart()
})

// 打开面板时加载多周期迷你图
watch(showInsights, (v) => {
  if (v && insightMode.value === 'periods') {
    setTimeout(() => loadMiniCharts(), 100)
  }
})
watch(insightMode, (v) => {
  if (v === 'periods' && showInsights.value) {
    setTimeout(() => loadMiniCharts(), 100)
  }
})

// ---------- 生命周期 ----------
onMounted(async () => {
  await nextTick()
  ensureTradeMarkerRegistered()
  // 如果从回测详情页跳转过来，先加载回测交易明细
  if (backtestId.value) {
    await fetchBacktestDetail()
  }
  initChart()
  setupResizeObserver()
  setupRealtime()
  // klinecharts v9 不会自动触发 loadDataCallback 初始加载，需主动调用
  await initialLoad()
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
  subIndicatorPaneId = null
  for (const p in miniCharts) {
    miniCharts[p]?.dispose()
    delete miniCharts[p]
  }
  if (compareChart) {
    compareChart.dispose()
    compareChart = null
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

.insights-header { display: flex; justify-content: space-between; align-items: center; }
.mini-chart-title { font-size: 12px; color: #909399; margin-bottom: 4px; }
.mini-chart { height: 90px; cursor: pointer; border: 1px solid #ebeef5; border-radius: 4px; }
.mini-chart:hover { border-color: #409eff; }
.compare-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.compare-chart { height: 260px; }

.toolbar-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 20px;
}
.toolbar-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toolbar-label {
  font-size: 13px;
  color: #909399;
  white-space: nowrap;
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

/* ===== 回测买卖点标记信息栏 ===== */
.backtest-banner {
  margin-top: 12px;
}
.backtest-banner-content {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  width: 100%;
}
.backtest-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
}
.backtest-stat {
  font-size: 13px;
  color: #606266;
}
.backtest-stat b {
  font-size: 14px;
}

:deep(.el-card__body) {
  padding: 0;
}

:deep(.el-button-group .el-button) {
  margin-left: 0;
}

/* ===== 移动端响应式 ===== */
@media (max-width: 768px) {
  .page-header {
    flex-wrap: wrap;
    gap: 8px;
  }
  .header-right {
    flex-wrap: wrap;
    width: 100%;
    gap: 6px;
  }
  .chart-box {
    height: calc(100vh - 360px);
    min-height: 360px;
  }
  .toolbar-row {
    gap: 12px;
  }
  .data-summary {
    gap: 4px;
  }
  .summary-item {
    padding: 2px 6px;
    font-size: 12px;
  }
  .mini-chart {
    height: 70px;
  }
  .backtest-banner-content {
    gap: 8px;
    font-size: 12px;
  }
  .backtest-stat {
    font-size: 12px;
  }
}
</style>
