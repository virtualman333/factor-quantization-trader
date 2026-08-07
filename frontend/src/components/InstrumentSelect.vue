<template>
  <el-select
    :model-value="modelValue"
    filterable
    remote
    clearable
    :remote-method="remoteSearch"
    :loading="loading"
    :placeholder="placeholder"
    :style="width ? `width:${width}` : ''"
    @update:model-value="onSelect"
  >
    <el-option
      v-for="item in options"
      :key="item.inst_id"
      :label="item.inst_id"
      :value="item.inst_id"
    >
      <span>{{ item.inst_id }}</span>
      <span class="inst-type-tag">{{ item.inst_type_display || item.inst_type }}</span>
    </el-option>
  </el-select>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { getInstruments } from '@/api/market'

const props = defineProps({
  modelValue: { type: String, default: '' },
  instType: { type: String, default: '' },
  placeholder: { type: String, default: '搜索品种' },
  width: { type: String, default: '200px' },
})

const emit = defineEmits(['update:modelValue', 'change'])

const options = ref([])
const loading = ref(false)

const loadOptions = async (keyword = '') => {
  loading.value = true
  try {
    const params = {}
    if (props.instType) params.inst_type = props.instType
    if (keyword) params.keyword = keyword
    params.page_size = 50
    const res = await getInstruments(params)
    options.value = res.results || res || []
  } catch {
    options.value = []
  } finally {
    loading.value = false
  }
}

const remoteSearch = (query) => {
  loadOptions(query)
}

const onSelect = (val) => {
  emit('update:modelValue', val)
  emit('change', val)
}

// 当外部初始有值时，加载对应选项（保证回显 label）
watch(
  () => props.modelValue,
  (val) => {
    if (val && !options.value.some((o) => o.inst_id === val)) {
      loadOptions(val)
    }
  },
  { immediate: true }
)

onMounted(() => {
  if (props.modelValue) loadOptions(props.modelValue)
  else loadOptions()
})
</script>

<style scoped>
.inst-type-tag {
  float: right;
  color: #909399;
  font-size: 12px;
}
</style>
