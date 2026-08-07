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
    @focus="onFocus"
    @update:model-value="onSelect"
  >
    <!-- 非搜索态：按 自选 > 常用 > 全部 分组展示 -->
    <template v-if="!searching">
      <el-option-group v-if="selfOptions.length" label="自选">
        <el-option
          v-for="item in selfOptions"
          :key="`self-${item.inst_id}`"
          :label="item.inst_id"
          :value="item.inst_id"
        >
          <span>{{ item.inst_id }}</span>
          <span class="inst-type-tag">{{ item.inst_type_display || item.inst_type }}</span>
        </el-option>
      </el-option-group>
      <el-option-group v-if="favOptions.length" label="常用">
        <el-option
          v-for="item in favOptions"
          :key="`fav-${item.inst_id}`"
          :label="item.inst_id"
          :value="item.inst_id"
        >
          <span>{{ item.inst_id }}</span>
          <span class="inst-type-tag">{{ item.inst_type_display || item.inst_type }}</span>
        </el-option>
      </el-option-group>
      <el-option-group v-if="otherOptions.length" label="全部">
        <el-option
          v-for="item in otherOptions"
          :key="`all-${item.inst_id}`"
          :label="item.inst_id"
          :value="item.inst_id"
        >
          <span>{{ item.inst_id }}</span>
          <span class="inst-type-tag">{{ item.inst_type_display || item.inst_type }}</span>
        </el-option>
      </el-option-group>
    </template>
    <!-- 搜索态：按 自选/常用 命中优先排序 -->
    <template v-else>
      <el-option
        v-for="item in options"
        :key="item.inst_id"
        :label="item.inst_id"
        :value="item.inst_id"
      >
        <span>{{ item.inst_id }}</span>
        <span class="inst-type-tag">{{ item.inst_type_display || item.inst_type }}</span>
      </el-option>
    </template>
  </el-select>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getInstruments } from '@/api/market'

// 常用品种（硬编码主流交易对）
const FAVORITES = [
  'BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'BNB-USDT', 'XRP-USDT',
  'DOGE-USDT', 'ADA-USDT', 'AVAX-USDT', 'LINK-USDT', 'TON-USDT',
]
const SELF_KEY = 'instrument_self_picks'

const props = defineProps({
  modelValue: { type: String, default: '' },
  instType: { type: String, default: '' },
  placeholder: { type: String, default: '搜索品种' },
  width: { type: String, default: '200px' },
})

const emit = defineEmits(['update:modelValue', 'change'])

const allOptions = ref([])   // 非搜索态完整列表
const options = ref([])      // 搜索态结果
const loading = ref(false)
const searching = ref(false)

// 自选品种（localStorage 持久化）
const selfPicks = ref(JSON.parse(localStorage.getItem(SELF_KEY) || '[]'))

// ---------- 分组 ----------
const selfOptions = computed(() =>
  selfPicks.value.map(id => allOptions.value.find(o => o.inst_id === id)).filter(Boolean)
)
const favOptions = computed(() =>
  FAVORITES.map(id => allOptions.value.find(o => o.inst_id === id))
    .filter(o => o && !selfPicks.value.includes(o.inst_id))
)
const otherOptions = computed(() =>
  allOptions.value.filter(o =>
    !selfPicks.value.includes(o.inst_id) && !FAVORITES.includes(o.inst_id)
  )
)

// ---------- 加载 ----------
const ensureExtra = async () => {
  // 补齐 常用/自选 中不在基础列表里的品种信息
  const need = [...FAVORITES, ...selfPicks.value]
    .filter(id => !allOptions.value.some(o => o.inst_id === id))
  for (const id of need.slice(0, 15)) {
    try {
      const params = { keyword: id, page_size: 1 }
      if (props.instType) params.inst_type = props.instType
      const res = await getInstruments(params)
      const rows = res.results || res || []
      const hit = rows.find(o => o.inst_id === id)
      if (hit) allOptions.value.push(hit)
    } catch { /* 忽略单条失败 */ }
  }
}

const loadAll = async () => {
  loading.value = true
  try {
    const params = { page_size: 100 }
    if (props.instType) params.inst_type = props.instType
    const res = await getInstruments(params)
    allOptions.value = res.results || res || []
    await ensureExtra()
  } catch {
    allOptions.value = []
  } finally {
    loading.value = false
  }
}

const loadOptions = async (keyword = '') => {
  loading.value = true
  try {
    const params = { page_size: 50 }
    if (props.instType) params.inst_type = props.instType
    if (keyword) params.keyword = keyword
    const res = await getInstruments(params)
    options.value = res.results || res || []
  } catch {
    options.value = []
  } finally {
    loading.value = false
  }
}

const remoteSearch = async (query) => {
  searching.value = !!query
  if (query) {
    await loadOptions(query)
    // 自选/常用命中优先
    const selfHit = options.value.filter(o => selfPicks.value.includes(o.inst_id))
    const favHit = options.value.filter(o =>
      FAVORITES.includes(o.inst_id) && !selfPicks.value.includes(o.inst_id))
    const rest = options.value.filter(o =>
      !selfPicks.value.includes(o.inst_id) && !FAVORITES.includes(o.inst_id))
    options.value = [...selfHit, ...favHit, ...rest]
  } else {
    await loadAll()
  }
}

// 下拉聚焦时首次加载
const onFocus = () => {
  if (!searching.value && !allOptions.value.length) loadAll()
}

// ---------- 选择 / 自选记录 ----------
const onSelect = (val) => {
  if (val && !selfPicks.value.includes(val)) {
    selfPicks.value = [val, ...selfPicks.value].slice(0, 20)
    localStorage.setItem(SELF_KEY, JSON.stringify(selfPicks.value))
  }
  emit('update:modelValue', val)
  emit('change', val)
}

// ---------- 回显 / 响应变化 ----------
watch(
  () => props.modelValue,
  async (val) => {
    if (val && !allOptions.value.some(o => o.inst_id === val)) {
      await loadAll()
    }
  },
  { immediate: true }
)

watch(
  () => props.instType,
  () => {
    searching.value = false
    loadAll()
  }
)

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.inst-type-tag {
  float: right;
  color: #909399;
  font-size: 12px;
}
</style>
