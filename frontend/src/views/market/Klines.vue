<template>
  <div class="kline-page">
    <!-- 顶部工具栏 -->
    <div class="page-header">
      <h2>K线数据</h2>
      <div class="header-right">
        <el-input v-model="instId" placeholder="品种 (BTC-USDT)" style="width:180px" clearable />
        <el-select v-model="bar" style="width:90px;margin-left:8px">
          <el-option v-for="b in bars" :key="b" :label="b" :value="b" />
        </el-select>
        <el-button-group style="margin-left:8px">
          <el-button :type="timeRange === 'page1' ? 'primary' : ''" size="small" @click="switchRange('page1')">近300条</el-button>
          <el-button :type="timeRange === 'full' ? 'primary' : ''" size="small" @click="switchRange('full')">全部</el-button>
        </el-button-group>
        <el-button type="primary" :icon="Download" @click="fetchKlines" style="margin-left:8px">拉取</el-button>
        <el-button :icon="Refresh" @click="load" style="margin-left:8px">刷新</el-button>
      </div>
    </div>

    <!-- 图表区域 -->
    <el-card style="margin-top:12px">
      <!-- 加载/状态栏 -->
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
      </div>
      <div v-loading="loading" class="chart-container">
        <div ref="chartRef" class="chart-box"></div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { getKlines, fetchKlines as fetchApi } from '@/api/market'
import { ElMessage } from 'element-plus'
import { Download, Refresh } from '@element-plus/icons-vue'
import { init, dispose } from 'klinecharts'

const chartRef = ref(null)
const loading = ref(false)
const instId = ref('BTC-USDT')
const bar = ref('1H')
const timeRange = ref('page1') // page1 | full
const bars = ['1m', '3m', '5m', '15m', '30m', '1H', '2H', '4H', '6H', '12H', '1D', '1W', '1M']

let chart = null
let resizeObserver = null
let isFirstLoad = true

const dataSummary = ref(null)

// ---------- 计算 OHLC 摘要 ----------
const computeSummary = (list) => {
  if (!list || list.length === 0) return null
  const first = list[0]
  const last = list[list.length - 1]
  const opens = list.map(d => parseFloat(d.open))
  const highs = list.map(d => parseFloat(d.high))
  const lows = list.map(d => parseFloat(d.low))
  const closes = list.map(d => parseFloat(d.close))

  const open = parseFloat(first.open)
  const high = Math.max(...highs)
  const low = Math.min(...lows)
  const close = parseFloat(last.close)
  const change = close - open
  const changePercent = open !== 0 ? ((change / open) * 100).toFixed(2) : '0.00'
  const amplitude = low !== 0 ? (((high - low) / low) * 100).toFixed(2) : '0.00'

  return {
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

// ---------- 图表初始化 ----------
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
          show: true,
          style: 'dashed',
          size: 1,
          color: '#e8e8e8',
          dashedValue: [4, 4],
        },
        vertical: {
          show: true,
          style: 'dashed',
          size: 1,
          color: '#e8e8e8',
          dashedValue: [4, 4],
        },
      },
      candle: {
        type: 'candle_solid',
        bar: {
          upColor: '#26a69a',
          downColor: '#ef5350',
          noChangeColor: '#888888',
          upBorderColor: '#26a69a',
          downBorderColor: '#ef5350',
          noChangeBorderColor: '#888888',
          upWickColor: '#26a69a',
          downWickColor: '#ef5350',
          noChangeWickColor: '#888888',
        },
        priceMark: {
          show: true,
          high: { show: true, color: '#ef5350', textOffset: 4, textSize: 12, textFamily: 'Arial', textWeight: 'normal' },
          low: { show: true, color: '#26a69a', textOffset: 4, textSize: 12, textFamily: 'Arial', textWeight: 'normal' },
          last: {
            show: true,
            upColor: '#26a69a',
            downColor: '#ef5350',
            noChangeColor: '#888888',
            line: { show: true, size: 1, style: 'dashed', dashedValue: [6, 4] },
            text: { show: true, color: '#ffffff', size: 12, family: 'Arial', weight: 'bold', paddingLeft: 6, paddingTop: 2, paddingRight: 6, paddingBottom: 2, borderRadius: 4 },
          },
        },
        tooltip: {
          showRule: 'always',
          showType: 'standard',
          defaultValue: 'N/A',
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
          showRule: 'always',
          showName: true,
          showParams: true,
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
        show: true,
        type: 'normal',
        position: 'right',
        inside: false,
        reverse: false,
        axisLine: { show: true, size: 1, color: '#cccccc' },
        tickLine: { show: true, size: 1, color: '#cccccc', length: 4 },
        tickText: { show: true, color: '#666666', size: 11, family: 'Arial', weight: 'normal', marginStart: 4, marginEnd: 4 },
      },
      separator: {
        size: 1,
        color: '#d0d0d0',
        fill: false,
        activeBackgroundColor: 'rgba(230, 230, 230, 0.3)',
      },
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
        point: {
          color: '#ffffff',
          borderColor: '#2196f3',
          borderSize: 2,
          radius: 4,
          activeColor: '#2196f3',
          activeBorderColor: '#2196f3',
          activeBorderSize: 2,
          activeRadius: 6,
        },
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
    // 第一行：在 K 线主图上叠加 MA5/MA10/MA20/MA60 均线
    chart.createIndicator(
      { name: 'MA', calcParams: [5, 10, 20, 60], shortName: 'MA' },
      true,
      { id: 'candle_pane' }
    )
    // 成交量：klinecharts 默认已带成交量副图，无需额外创建
    // 第二行：MACD
    chart.createIndicator('MACD', false, { height: 180, minHeight: 60 })
    // 第三行：RSI
    chart.createIndicator('RSI', false, { height: 160, minHeight: 50 })
  }
}

// ---------- 渲染图表 ----------
const renderChart = (list) => {
  if (!chart) return

  if (!list || list.length === 0) {
    chart.clearData()
    dataSummary.value = null
    ElMessage.warning('暂无 K 线数据，请先拉取数据')
    return
  }

  const data = [...list]
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    .map(d => ({
      timestamp: new Date(d.timestamp).getTime(),
      open: parseFloat(d.open),
      high: parseFloat(d.high),
      low: parseFloat(d.low),
      close: parseFloat(d.close),
      volume: parseFloat(d.vol) || 0,
    }))

  chart.applyNewData(data, false)
  dataSummary.value = computeSummary(list)
}

// ---------- 加载数据 ----------
const load = async () => {
  loading.value = true
  try {
    const params = { page_size: 1000 }
    if (instId.value) params.instrument__inst_id = instId.value
    if (bar.value) params.bar = bar.value

    // 先获取第一页判断数据量
    const page1Res = await getKlines({ ...params, page: 1 })
    const page1List = page1Res.results || page1Res
    const total = page1Res.count || page1List.length

    let allData = page1List

    // 如果需要全部数据且总量超过一页
    if (timeRange.value === 'full' && total > page1List.length) {
      const totalPages = Math.ceil(total / 1000)
      const remainingRequests = []
      for (let page = 2; page <= totalPages; page++) {
        remainingRequests.push(getKlines({ ...params, page }))
      }
      const remainingResults = await Promise.all(remainingRequests)
      remainingResults.forEach(res => {
        allData = allData.concat(res.results || res)
      })
    }

    renderChart(allData)

    if (!isFirstLoad) {
      ElMessage.success(`已加载 ${allData.length} 条 K 线数据`)
    }
    isFirstLoad = false
  } catch (e) {
    ElMessage.error(`加载失败: ${e.message}`)
  }
  loading.value = false
}

// ---------- 切换数据范围 ----------
const switchRange = (range) => {
  timeRange.value = range
  load()
}

// ---------- 手动拉取 ----------
const fetchKlines = async () => {
  if (!instId.value) { ElMessage.warning('请输入品种ID'); return }
  loading.value = true
  try {
    await fetchApi({ inst_id: instId.value, bar: bar.value, limit: 300, is_history: true })
    ElMessage.success('拉取成功，正在刷新数据...')
    await load()
  } catch (e) {
    ElMessage.error(`拉取失败: ${e.message}`)
    loading.value = false
  }
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

// ---------- 品种/周期切换时重新加载 ----------
watch([instId, bar], () => {
  isFirstLoad = true
  load()
})

// ---------- 生命周期 ----------
onMounted(async () => {
  await nextTick()
  initChart()
  setupResizeObserver()
  await load()
})

onBeforeUnmount(() => {
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

.chart-toolbar {
  display: flex;
  align-items: center;
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

.summary-item .value.up {
  color: #26a69a;
}

.summary-item .value.down {
  color: #ef5350;
}

:deep(.el-card__body) {
  padding: 0;
}

:deep(.el-button-group .el-button) {
  margin-left: 0;
}
</style>
