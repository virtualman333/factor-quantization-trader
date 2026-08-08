<template>
  <el-dialog
    :model-value="modelValue"
    title="运行回测"
    width="520px"
    @update:model-value="$emit('update:modelValue', $event)"
    @open="onOpen"
  >
    <el-alert type="info" :closable="false" show-icon style="margin-bottom:16px">
      回测通过历史行情模拟策略表现，异步执行。提交后可查看任务进度与结果。
    </el-alert>
    <el-form label-width="100px" @submit.prevent>
      <el-form-item label="策略">
        <span style="font-weight:600">{{ strategyName }}</span>
      </el-form-item>
      <el-form-item label="开始日期">
        <el-date-picker v-model="startDate" type="date" value-format="YYYY-MM-DD" style="width:100%" />
      </el-form-item>
      <el-form-item label="结束日期">
        <el-date-picker v-model="endDate" type="date" value-format="YYYY-MM-DD" style="width:100%" />
      </el-form-item>
      <el-form-item label="手续费率">
        <el-input-number v-model="feeRate" :min="0" :max="0.01" :step="0.0005" :precision="4" style="width:160px" />
        <span class="hint">单边比例，默认 0.1%</span>
      </el-form-item>
      <el-form-item label="滑点">
        <el-input-number v-model="slippage" :min="0" :max="0.01" :step="0.0005" :precision="4" style="width:160px" />
        <span class="hint">成交价偏移，默认 0.1%</span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submit">开始回测</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  strategyId: { type: [Number, String], default: null },
  strategyName: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'submit'])

const startDate = ref('')
const endDate = ref('')
const feeRate = ref(0.001)
const slippage = ref(0.001)
const loading = ref(false)

const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

const onOpen = () => {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 30)
  startDate.value = fmt(start)
  endDate.value = fmt(end)
}

const submit = async () => {
  if (!startDate.value || !endDate.value) return
  loading.value = true
  try {
    await emit('submit', {
      start_date: startDate.value,
      end_date: endDate.value,
      fee_rate: feeRate.value,
      slippage: slippage.value,
    })
    emit('update:modelValue', false)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.hint { color: #909399; font-size: 12px; margin-left: 8px; }
</style>
