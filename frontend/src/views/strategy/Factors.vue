<template>
  <div>
    <div class="page-header">
      <h2>因子定义</h2>
      <div>
        <instrument-select v-model="instId" placeholder="搜索品种" width="200px" />
        <el-select v-model="bar" style="width:100px;margin-left:8px">
          <el-option v-for="b in bars" :key="b" :label="b" :value="b" />
        </el-select>
        <el-button type="primary" :icon="Cpu" :loading="calcLoading" @click="calculate" style="margin-left:8px">计算因子</el-button>
        <el-button type="success" :icon="Plus" @click="openCustomDialog" style="margin-left:8px">自定义因子</el-button>
      </div>
    </div>

    <el-table :data="tableData" v-loading="loading" border stripe style="margin-top:16px">
      <el-table-column prop="display_name" label="名称" width="150" />
      <el-table-column prop="name" label="标识" width="120" />
      <el-table-column prop="factor_type_display" label="类型" width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ row.factor_type_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
    </el-table>

    <!-- 计算结果 -->
    <el-card v-if="calcResults.length" style="margin-top:20px">
      <template #header>因子计算结果 - {{ instId }} ({{ bar }})</template>
      <el-table :data="calcResults" size="small" border stripe>
        <el-table-column prop="factor" label="因子" width="120" />
        <el-table-column prop="value" label="数值" width="140" />
        <el-table-column prop="score" label="得分" width="100">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.score * 100)" :color="row.score >= 0.5 ? '#67c23a' : '#e6a23c'" />
          </template>
        </el-table-column>
        <el-table-column prop="signal" label="信号" width="80">
          <template #default="{ row }">
            <el-tag :type="row.signal === 'buy' ? 'success' : row.signal === 'sell' ? 'danger' : 'info'" size="small">
              {{ row.signal }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="详情" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- 自定义因子弹窗 -->
    <el-dialog v-model="customVisible" title="自定义因子" width="560px">
      <el-form label-width="80px">
        <el-form-item label="因子名称">
          <el-input v-model="customForm.name" placeholder="如: my_momentum" />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="customForm.display_name" placeholder="如: 自定义动量" />
        </el-form-item>
        <el-form-item label="计算公式">
          <el-input v-model="customForm.formula" type="textarea" :rows="3"
            placeholder="pandas表达式，基于列 close/high/low/open/volume&#10;示例: close/close.rolling(20).mean()-1" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="customForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="customVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCustom">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getFactors, calculateFactor, createFactor, updateFactor } from '@/api/strategy'
import InstrumentSelect from '@/components/InstrumentSelect.vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

const tableData = ref([])
const loading = ref(false)
const calcLoading = ref(false)
const calcResults = ref([])
const instId = ref('BTC-USDT')
const bar = ref('1H')

const customVisible = ref(false)
const saving = ref(false)
const customForm = ref({ name: '', display_name: '', formula: '', description: '' })
const bars = ['1m', '5m', '15m', '30m', '1H', '4H', '1D']

const load = async () => {
  loading.value = true
  try {
    const res = await getFactors()
    tableData.value = res.results || res
  } catch (e) { ElMessage.error(e.message) }
  loading.value = false
}

const calculate = async () => {
  if (!instId.value) { ElMessage.warning('请输入品种ID'); return }
  calcLoading.value = true
  try {
    const res = await calculateFactor({ inst_id: instId.value, bar: bar.value })
    calcResults.value = res.results || res.factors || res || []
  } catch (e) { ElMessage.error(e.message) }
  calcLoading.value = false
}

const openCustomDialog = () => {
  customForm.value = { name: '', display_name: '', formula: '', description: '' }
  customVisible.value = true
}

const saveCustom = async () => {
  if (!customForm.value.name || !customForm.value.formula) {
    ElMessage.warning('请填写因子名称和计算公式'); return
  }
  saving.value = true
  try {
    await createFactor({
      name: customForm.value.name,
      display_name: customForm.value.display_name || customForm.value.name,
      factor_type: 'custom',
      formula: customForm.value.formula,
      description: customForm.value.description,
      is_custom: true,
      is_active: true,
    })
    ElMessage.success('自定义因子已保存')
    customVisible.value = false
    load()
  } catch (e) { ElMessage.error(e.message) }
  saving.value = false
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
</style>
