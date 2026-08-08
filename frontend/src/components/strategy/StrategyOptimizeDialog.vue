<template>
  <el-dialog
    :model-value="modelValue"
    title="策略优化"
    width="720px"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-tabs v-model="optTab">
      <!-- 参数网格搜索 -->
      <el-tab-pane label="参数优化（网格搜索）" name="params">
        <el-form label-width="110px" @submit.prevent>
          <el-form-item label="参数网格">
            <div style="width:100%">
              <div v-for="(g, idx) in gridRows" :key="idx" class="grid-row">
                <el-input v-model="g.key" placeholder="参数名，如 vol_ratio" style="width:180px" />
                <el-input v-model="g.values" placeholder="取值，逗号分隔，如 1.5,1.8,2.0" style="flex:1" />
                <el-button type="danger" text @click="gridRows.splice(idx, 1)">移除</el-button>
              </div>
              <el-button size="small" type="primary" text @click="addGridRow">+ 添加参数</el-button>
            </div>
          </el-form-item>
          <el-form-item label="开始日期">
            <el-date-picker v-model="startDate" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="结束日期">
            <el-date-picker v-model="endDate" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="runParamOptimize">开始网格搜索</el-button>
          </el-form-item>
        </el-form>
        <el-alert v-if="submitted" type="success" :closable="false" show-icon style="margin-bottom:12px">
          网格搜索任务已提交后台执行，可在「回测任务」列表中查看进度与结果。
        </el-alert>
        <el-table v-if="results.length" :data="results" border stripe size="small" max-height="260">
          <el-table-column label="参数" min-width="160">
            <template #default="{ row }">
              <el-tag v-for="(v, k) in row.params" :key="k" size="small" style="margin-right:4px">{{ k }}={{ v }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="收益" width="90">
            <template #default="{ row }">
              <span :style="{ color: row.total_return >= 0 ? '#67c23a' : '#f56c6c' }">{{ (row.total_return * 100).toFixed(2) }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="夏普" width="80">
            <template #default="{ row }">{{ (row.sharpe_ratio || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="胜率" width="80">
            <template #default="{ row }">{{ ((row.win_rate || 0) * 100).toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="交易数" width="80">
            <template #default="{ row }">{{ row.total_trades }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 因子权重优化 -->
      <el-tab-pane label="因子权重优化" name="weights">
        <el-form label-width="110px" @submit.prevent>
          <el-form-item label="开始日期">
            <el-date-picker v-model="wtStartDate" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="结束日期">
            <el-date-picker v-model="wtEndDate" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="迭代次数">
            <el-input-number v-model="iterations" :min="5" :max="50" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="wtLoading" @click="runWeightOptimize">开始权重优化</el-button>
          </el-form-item>
        </el-form>
        <el-alert v-if="wtSubmitted" type="success" :closable="false" show-icon style="margin-bottom:12px">
          权重优化任务已提交后台执行，完成后会自动保存到策略。
        </el-alert>
        <div v-if="weightResult" class="wt-result">
          <el-tag v-for="(v, k) in weightResult.weights" :key="k" size="small" style="margin:4px">
            {{ k }}: {{ v }}
          </el-tag>
        </div>
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  strategyId: { type: [Number, String], default: null },
  strategyType: { type: String, default: '' },
})
const emit = defineEmits(['submit-params', 'submit-weights'])

const optTab = ref('params')

// 参数网格
const gridRows = ref([])
const startDate = ref('')
const endDate = ref('')
const loading = ref(false)
const results = ref([])
const submitted = ref(false)

// 权重优化
const wtStartDate = ref('')
const wtEndDate = ref('')
const iterations = ref(10)
const wtLoading = ref(false)
const weightResult = ref(null)
const wtSubmitted = ref(false)

const addGridRow = () => { gridRows.value.push({ key: '', values: '' }) }

const buildParamGrid = () => {
  const grid = {}
  for (const g of gridRows.value) {
    if (!g.key || !g.values) continue
    grid[g.key] = g.values.split(',').map(s => s.trim()).filter(Boolean).map(s => {
      const n = Number(s)
      return isNaN(n) ? s : n
    })
  }
  return grid
}

const runParamOptimize = async () => {
  const grid = buildParamGrid()
  if (!Object.keys(grid).length) return
  loading.value = true
  try {
    const res = await emit('submit-params', {
      param_grid: grid,
      start_date: startDate.value || undefined,
      end_date: endDate.value || undefined,
    })
    if (res?.submitted) {
      submitted.value = true
      results.value = []
    } else if (res?.results) {
      results.value = res.results
    }
  } finally {
    loading.value = false
  }
}

const runWeightOptimize = async () => {
  wtLoading.value = true
  try {
    const res = await emit('submit-weights', {
      start_date: wtStartDate.value || undefined,
      end_date: wtEndDate.value || undefined,
      iterations: iterations.value,
    })
    if (res?.submitted) {
      wtSubmitted.value = true
      weightResult.value = null
    } else if (res?.weights) {
      weightResult.value = res
    }
  } finally {
    wtLoading.value = false
  }
}
</script>

<style scoped>
.grid-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; width: 100%; }
.wt-result { margin-top: 16px; padding: 12px; background: var(--app-bg); border-radius: 6px; }
</style>
