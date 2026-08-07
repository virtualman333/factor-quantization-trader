<template>
  <div>
    <div class="page-header">
      <h2>策略组合</h2>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建组合</el-button>
    </div>

    <el-row :gutter="16">
      <el-col v-for="p in portfolios" :key="p.id" :span="8" style="margin-bottom:16px">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ p.name }}</span>
              <div>
                <el-button size="small" type="primary" text @click="runPortfolioBt(p)">组合回测</el-button>
                <el-button size="small" text @click="openEdit(p)">编辑</el-button>
                <el-button size="small" type="danger" text @click="remove(p)">删除</el-button>
              </div>
            </div>
          </template>
          <div class="members">
            <div v-for="m in p.strategies" :key="m.strategy_id" class="member-row">
              <span>{{ strategyName(m.strategy_id) }}</span>
              <el-tag size="small" type="warning">{{ (m.weight * 100).toFixed(0) }}%</el-tag>
            </div>
          </div>
          <div class="meta">初始资金: <b>${{ p.initial_capital }}</b></div>
        </el-card>
      </el-col>
      <el-col v-if="!portfolios.length" :span="24">
        <el-empty description="暂无策略组合，点击「新建组合」创建" />
      </el-col>
    </el-row>

    <!-- 组合回测结果 -->
    <el-dialog v-model="resultVisible" title="组合回测结果" width="70%">
      <template v-if="portfolioResult">
        <el-descriptions :column="4" border size="small" style="margin-bottom:16px">
          <el-descriptions-item label="初始资金">{{ portfolioResult.initial_capital }}</el-descriptions-item>
          <el-descriptions-item label="最终资金">{{ portfolioResult.final_capital }}</el-descriptions-item>
          <el-descriptions-item label="总收益率">
            <span :style="{ color: portfolioResult.total_return >= 0 ? '#67c23a' : '#f56c6c' }">
              {{ (portfolioResult.total_return * 100).toFixed(2) }}%
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="成员数">{{ portfolioResult.members.length }}</el-descriptions-item>
        </el-descriptions>
        <v-chart :option="aggChartOption" style="height: 320px" autoresize />
        <h4 style="margin-top:16px">成员明细</h4>
        <el-table :data="portfolioResult.members" border stripe size="small">
          <el-table-column prop="name" label="策略" />
          <el-table-column label="权重">
            <template #default="{ row }">{{ (row.weight * 100).toFixed(0) }}%</template>
          </el-table-column>
          <el-table-column label="收益">
            <template #default="{ row }">
              <span :style="{ color: row.total_return >= 0 ? '#67c23a' : '#f56c6c' }">
                {{ (row.total_return * 100).toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="夏普">
            <template #default="{ row }">{{ row.sharpe_ratio?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="最大回撤">
            <template #default="{ row }">{{ (row.max_drawdown * 100).toFixed(2) }}%</template>
          </el-table-column>
        </el-table>
      </template>
    </el-dialog>

    <!-- 新建/编辑组合 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑组合' : '新建组合'" width="600px">
      <el-form label-width="100px">
        <el-form-item label="组合名称">
          <el-input v-model="form.name" placeholder="如：稳健多策略组合" />
        </el-form-item>
        <el-form-item label="初始资金">
          <el-input-number v-model="form.initial_capital" :min="0" :step="100" />
        </el-form-item>
        <el-form-item label="策略权重">
          <div v-for="(row, idx) in form.strategies" :key="row.strategy_id || idx" class="weight-row">
            <el-select v-model="row.strategy_id" placeholder="选择策略" style="flex:1">
              <el-option v-for="s in strategies" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
            <el-input-number v-model="row.weight" :min="0" :max="1" :step="0.1" style="width:120px" />
            <el-button type="danger" text @click="removeWeight(idx)">移除</el-button>
          </div>
          <el-button size="small" type="primary" text @click="addWeight">+ 添加策略</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import {
  getPortfolios, createPortfolio, updatePortfolio, deletePortfolio,
  runPortfolioBacktest, getStrategies,
} from '@/api/strategy'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const portfolios = ref([])
const strategies = ref([])
const dialogVisible = ref(false)
const resultVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)
const portfolioResult = ref(null)

const form = ref({ name: '', initial_capital: 1000, strategies: [] })

const load = async () => {
  const res = await getPortfolios()
  portfolios.value = res.results || res || []
}
const loadStrategies = async () => {
  const res = await getStrategies({ page_size: 100 })
  strategies.value = res.results || res || []
}

const strategyName = (id) => strategies.value.find(s => s.id === id)?.name || `策略#${id}`

const aggChartOption = computed(() => {
  const curve = portfolioResult.value?.equity_curve || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['组合权益'] },
    grid: { left: 50, right: 20, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: curve.map(c => c[0]?.slice(0, 10)) },
    yAxis: { type: 'value', scale: true },
    series: [{
      name: '组合权益', type: 'line', data: curve.map(c => c[1]),
      smooth: true, showSymbol: false,
      areaStyle: { opacity: 0.15 },
    }],
  }
})

const openCreate = () => {
  editingId.value = null
  form.value = { name: '', initial_capital: 1000, strategies: [] }
  addWeight()
  dialogVisible.value = true
}
const openEdit = (p) => {
  editingId.value = p.id
  form.value = {
    name: p.name,
    initial_capital: Number(p.initial_capital),
    strategies: (p.strategies || []).map(s => ({ strategy_id: s.strategy_id, weight: s.weight })),
  }
  if (!form.value.strategies.length) addWeight()
  dialogVisible.value = true
}
const addWeight = () => { form.value.strategies.push({ strategy_id: null, weight: 0.5 }) }
const removeWeight = (idx) => { form.value.strategies.splice(idx, 1) }

const save = async () => {
  if (!form.value.name) { ElMessage.warning('请输入组合名称'); return }
  const validItems = form.value.strategies.filter(s => s.strategy_id)
  if (!validItems.length) { ElMessage.warning('请至少添加一个策略'); return }
  saving.value = true
  try {
    const data = { ...form.value, strategies: validItems }
    if (editingId.value) await updatePortfolio(editingId.value, data)
    else await createPortfolio(data)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e) { ElMessage.error(e.message) }
  saving.value = false
}

const remove = async (p) => {
  await ElMessageBox.confirm(`确认删除组合「${p.name}」？`, '提示', { type: 'warning' })
  await deletePortfolio(p.id)
  ElMessage.success('已删除')
  load()
}

const runPortfolioBt = async (p) => {
  try {
    const res = await runPortfolioBacktest(p.id, {})
    portfolioResult.value = res
    resultVisible.value = true
  } catch (e) { ElMessage.error(e.message) }
}

onMounted(() => { load(); loadStrategies() })
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.members { min-height: 60px; }
.member-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; font-size: 13px; }
.meta { margin-top: 8px; font-size: 12px; color: #909399; }
.weight-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
</style>
