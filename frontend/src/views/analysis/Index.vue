<template>
  <div>
    <div class="page-header">
      <h2>数据分析</h2>
    </div>

    <!-- 市场状态 -->
    <el-card style="margin-top:16px">
      <template #header>
        <div class="card-header">
          <span>市场状态分类</span>
          <div>
            <instrument-select v-model="stateInst" placeholder="选择品种" width="200px" />
            <el-select v-model="stateBar" style="width:100px;margin-left:8px">
              <el-option v-for="b in bars" :key="b" :label="b" :value="b" />
            </el-select>
            <el-button size="small" type="primary" @click="loadState" :loading="stateLoading" style="margin-left:8px">分析</el-button>
          </div>
        </div>
      </template>
      <template v-if="marketState">
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item label="市场状态">
            <el-tag :type="stateTagType" size="large">{{ marketState.state_label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="ADX 趋势强度">{{ marketState.adx }}</el-descriptions-item>
          <el-descriptions-item label="ATR 相对波动">{{ marketState.atr_ratio }}</el-descriptions-item>
          <el-descriptions-item label="建议">
            <span style="color:#409eff">{{ marketState.suggest }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else description="选择品种点击分析" :image-size="60" />
    </el-card>

    <el-row :gutter="16" style="margin-top:16px">
      <!-- 相关性矩阵 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>相关性分析矩阵</span>
              <el-button size="small" type="primary" @click="loadCorrelation" :loading="corrLoading">计算</el-button>
            </div>
          </template>
          <el-input v-model="corrSymbols" placeholder="品种列表，逗号分隔，如 BTC-USDT,ETH-USDT,SOL-USDT" style="margin-bottom:12px" />
          <v-chart v-if="corrMatrix.length" :option="corrOption" style="height:360px" autoresize />
          <el-empty v-else description="输入品种点击计算" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 因子 IC -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>因子有效性统计 (IC)</span>
              <el-button size="small" type="primary" @click="loadFactorIC" :loading="icLoading">分析</el-button>
            </div>
          </template>
          <el-select v-model="icStrategyId" placeholder="选择策略" style="margin-bottom:12px;width:100%">
            <el-option v-for="s in strategies" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
          <template v-if="icData">
            <div v-for="(factors, sym) in icData.factors" :key="sym" class="ic-symbol">
              <div class="ic-sym-title">{{ sym }}</div>
              <el-table :data="Object.entries(factors).map(([name, v]) => ({ name, ...v }))" size="small" border>
                <el-table-column prop="name" label="因子" />
                <el-table-column label="IC" width="100">
                  <template #default="{ row }">
                    <span :style="{ color: row.ic >= 0.03 ? '#67c23a' : row.ic <= -0.03 ? '#f56c6c' : '#909399' }">
                      {{ row.ic }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="samples" label="样本数" width="90" />
              </el-table>
            </div>
          </template>
          <el-empty v-else description="选择策略点击分析" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getCorrelationMatrix, getFactorIC, getMarketState } from '@/api/dashboard'
import { getStrategies } from '@/api/strategy'
import InstrumentSelect from '@/components/InstrumentSelect.vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { HeatmapChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([HeatmapChart, TitleComponent, TooltipComponent, GridComponent, VisualMapComponent, CanvasRenderer])

const bars = ['15m', '1H', '4H', '1D', '1W']

// 市场状态
const stateInst = ref('BTC-USDT')
const stateBar = ref('1D')
const stateLoading = ref(false)
const marketState = ref(null)

const stateTagType = computed(() => {
  const s = marketState.value?.state
  return s === 'range' ? 'info' : s === 'trend' || s === 'high_trend' ? 'success' : 'warning'
})

// 相关性
const corrSymbols = ref('BTC-USDT,ETH-USDT,SOL-USDT')
const corrLoading = ref(false)
const corrMatrix = ref([])
const corrSymbolList = ref([])

const corrOption = computed(() => {
  const data = []
  corrMatrix.value.forEach((row, i) => {
    row.forEach((val, j) => data.push([j, i, val]))
  })
  return {
    tooltip: {
      position: 'top',
      formatter: (p) => `${corrSymbolList.value[p.value[0]]} / ${corrSymbolList.value[p.value[1]]}<br/>相关系数: ${p.value[2]}`,
    },
    grid: { left: 80, right: 20, top: 20, bottom: 80 },
    xAxis: { type: 'category', data: corrSymbolList.value, splitArea: { show: true } },
    yAxis: { type: 'category', data: corrSymbolList.value, splitArea: { show: true } },
    visualMap: {
      min: -1, max: 1, calculable: true, orient: 'horizontal',
      left: 'center', bottom: 0,
      inRange: { color: ['#f56c6c', '#fff', '#67c23a'] },
    },
    series: [{
      type: 'heatmap', data,
      label: { show: true, formatter: (p) => p.value[2].toFixed(2) },
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
    }],
  }
})

// 因子 IC
const strategies = ref([])
const icStrategyId = ref(null)
const icLoading = ref(false)
const icData = ref(null)

const loadState = async () => {
  stateLoading.value = true
  try { marketState.value = await getMarketState({ inst_id: stateInst.value, bar: stateBar.value }) }
  catch (e) { ElMessage.error(e.message) }
  stateLoading.value = false
}

const loadCorrelation = async () => {
  corrLoading.value = true
  try {
    const res = await getCorrelationMatrix({ symbols: corrSymbols.value, bar: '1D' })
    corrSymbolList.value = res.symbols || []
    corrMatrix.value = res.matrix || []
  } catch (e) { ElMessage.error(e.message) }
  corrLoading.value = false
}

const loadFactorIC = async () => {
  if (!icStrategyId.value) { ElMessage.warning('请选择策略'); return }
  icLoading.value = true
  try { icData.value = await getFactorIC({ strategy_id: icStrategyId.value }) }
  catch (e) { ElMessage.error(e.message) }
  icLoading.value = false
}

onMounted(async () => {
  try {
    const res = await getStrategies({ page_size: 100 })
    strategies.value = res.results || res || []
  } catch {}
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.ic-symbol { margin-bottom: 12px; }
.ic-sym-title { font-size: 13px; font-weight: 600; color: #409eff; margin-bottom: 4px; }
</style>
