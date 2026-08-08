<template>
  <el-select
    :model-value="modelValue"
    :multiple="multiple"
    filterable
    remote
    :remote-method="remoteSearch"
    :loading="loading"
    :clearable="clearable"
    :collapse-tags="multiple && collapseTags"
    :collapse-tags-tooltip="multiple && collapseTags"
    :placeholder="placeholder"
    :disabled="disabled"
    :size="size || undefined"
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
          <div class="inst-row">
            <span class="inst-id">{{ item.inst_id }}</span>
            <span class="inst-right">
              <span class="inst-type-tag">{{ item.inst_type_display || item.inst_type }}</span>
              <span
                class="inst-star on"
                title="取消收藏"
                @click.stop.prevent="toggleSelf(item.inst_id)"
              >★</span>
            </span>
          </div>
        </el-option>
      </el-option-group>
      <el-option-group v-if="favOptions.length" label="常用">
        <el-option
          v-for="item in favOptions"
          :key="`fav-${item.inst_id}`"
          :label="item.inst_id"
          :value="item.inst_id"
        >
          <div class="inst-row">
            <span class="inst-id">{{ item.inst_id }}</span>
            <span class="inst-right">
              <span class="inst-type-tag">{{ item.inst_type_display || item.inst_type }}</span>
              <span
                class="inst-star"
                title="收藏"
                @click.stop.prevent="toggleSelf(item.inst_id)"
              >☆</span>
            </span>
          </div>
        </el-option>
      </el-option-group>
      <el-option-group v-if="otherOptions.length" label="全部">
        <el-option
          v-for="item in otherOptions"
          :key="`all-${item.inst_id}`"
          :label="item.inst_id"
          :value="item.inst_id"
        >
          <div class="inst-row">
            <span class="inst-id">{{ item.inst_id }}</span>
            <span class="inst-right">
              <span class="inst-type-tag">{{ item.inst_type_display || item.inst_type }}</span>
              <span
                class="inst-star"
                title="收藏"
                @click.stop.prevent="toggleSelf(item.inst_id)"
              >☆</span>
            </span>
          </div>
        </el-option>
      </el-option-group>
    </template>
    <!-- 搜索态：自选/常用命中优先，支持自定义创建 -->
    <template v-else>
      <el-option
        v-for="item in displayOptions"
        :key="item.inst_id"
        :label="item.inst_id"
        :value="item.inst_id"
      >
        <div class="inst-row">
          <span class="inst-id" v-html="highlightInstId(item.inst_id)"></span>
          <span class="inst-right">
            <span class="inst-type-tag">
              {{ item.__create ? '直接使用' : (item.inst_type_display || item.inst_type) }}
            </span>
            <span
              v-if="!item.__create"
              class="inst-star"
              :class="{ on: isSelf(item.inst_id) }"
              :title="isSelf(item.inst_id) ? '取消收藏' : '收藏'"
              @click.stop.prevent="toggleSelf(item.inst_id)"
            >{{ isSelf(item.inst_id) ? '★' : '☆' }}</span>
          </span>
        </div>
      </el-option>
    </template>
    <!-- 空状态 -->
    <template #empty>
      <div class="inst-empty">
        <span v-if="loading">加载中…</span>
        <span v-else-if="searching && allowCreate">按回车可直接使用「{{ keyword }}」</span>
        <span v-else-if="searching">未找到匹配品种</span>
        <span v-else>暂无品种数据，可先在「品种管理」中同步</span>
      </div>
    </template>
  </el-select>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getInstruments } from '@/api/market'

// 常用品种（硬编码主流交易对）
const FAVORITES = [
  'BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'BNB-USDT', 'XRP-USDT',
  'DOGE-USDT', 'ADA-USDT', 'AVAX-USDT', 'LINK-USDT', 'TON-USDT',
]
const SELF_KEY = 'instrument_self_picks'
const CACHE_TTL = 5 * 60 * 1000 // 品种列表缓存 5 分钟

const props = defineProps({
  modelValue: { type: [String, Array], default: '' },
  instType: { type: String, default: '' },
  placeholder: { type: String, default: '搜索品种' },
  width: { type: String, default: '200px' },
  multiple: { type: Boolean, default: false },
  allowCreate: { type: Boolean, default: false },
  collapseTags: { type: Boolean, default: false },
  clearable: { type: Boolean, default: true },
  disabled: { type: Boolean, default: false },
  size: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'change'])

const allOptions = ref([])   // 非搜索态完整列表
const options = ref([])      // 搜索态结果
const loading = ref(false)
const searching = ref(false)
const keyword = ref('')

// 自选品种（localStorage 持久化）
const selfPicks = ref(JSON.parse(localStorage.getItem(SELF_KEY) || '[]'))

// ---------- 缓存 ----------
const listCache = new Map() // key -> { data, ts }

const cacheKey = () => `all::${props.instType}`

const getCached = () => {
  const hit = listCache.get(cacheKey())
  if (hit && Date.now() - hit.ts < CACHE_TTL) return hit.data
  return null
}

const setCache = (data) => {
  listCache.set(cacheKey(), { data, ts: Date.now() })
  // 防止缓存无限增长
  if (listCache.size > 20) {
    const oldest = listCache.keys().next().value
    listCache.delete(oldest)
  }
}

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
  // 补齐 常用/自选/当前值 中不在基础列表里的品种信息（不按类型过滤，避免现货被 SWAP 过滤掉）
  const selected = Array.isArray(props.modelValue) ? props.modelValue : (props.modelValue ? [props.modelValue] : [])
  const need = [...FAVORITES, ...selfPicks.value, ...selected]
    .filter(id => id && !allOptions.value.some(o => o.inst_id === id))
  for (const id of need.slice(0, 15)) {
    try {
      const res = await getInstruments({ keyword: id, page_size: 1 })
      const rows = res.results || res || []
      const hit = rows.find(o => o.inst_id === id)
      if (hit && !allOptions.value.some(o => o.inst_id === hit.inst_id)) {
        allOptions.value.push(hit)
      }
    } catch { /* 忽略单条失败 */ }
  }
}

const loadAll = async (force = false) => {
  if (!force) {
    const cached = getCached()
    if (cached) {
      allOptions.value = cached
      return
    }
  }
  loading.value = true
  try {
    const params = { page_size: 100 }
    if (props.instType) params.inst_type = props.instType
    const res = await getInstruments(params)
    allOptions.value = res.results || res || []
    setCache(allOptions.value)
    await ensureExtra()
  } catch {
    allOptions.value = []
  } finally {
    loading.value = false
  }
}

let searchTimer = null
const loadOptions = async (q = '') => {
  loading.value = true
  try {
    const params = { page_size: 50 }
    if (props.instType) params.inst_type = props.instType
    if (q) params.keyword = q
    const res = await getInstruments(params)
    options.value = res.results || res || []
  } catch {
    options.value = []
  } finally {
    loading.value = false
  }
}

// 搜索防抖 300ms
const remoteSearch = (query) => {
  const q = (query || '').trim()
  keyword.value = q
  searching.value = !!q
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    if (q) {
      loadOptions(q)
    } else {
      loadAll()
    }
  }, 300)
}

// 下拉聚焦时首次加载
const onFocus = () => {
  if (!searching.value && !allOptions.value.length) loadAll()
}

// ---------- 搜索态展示 ----------
const displayOptions = computed(() => {
  const selfHit = options.value.filter(o => selfPicks.value.includes(o.inst_id))
  const favHit = options.value.filter(o =>
    FAVORITES.includes(o.inst_id) && !selfPicks.value.includes(o.inst_id))
  const rest = options.value.filter(o =>
    !selfPicks.value.includes(o.inst_id) && !FAVORITES.includes(o.inst_id))

  let list = [...selfHit, ...favHit, ...rest]

  // 允许创建：输入无精确匹配时置顶一个"直接使用"项
  if (props.allowCreate && keyword.value && !list.some(o => o.inst_id.toUpperCase() === keyword.value.toUpperCase())) {
    list = [
      { inst_id: keyword.value.toUpperCase(), inst_type: '', inst_type_display: '', __create: true },
      ...list,
    ]
  }
  return list
})

const highlightInstId = (id) => {
  if (!keyword.value) return id
  const idx = id.toUpperCase().indexOf(keyword.value.toUpperCase())
  if (idx < 0) return id
  const k = id.slice(idx, idx + keyword.value.length)
  return `${id.slice(0, idx)}<mark class="inst-hl">${k}</mark>${id.slice(idx + keyword.value.length)}`
}

// ---------- 自选管理 ----------
const isSelf = (id) => selfPicks.value.includes(id)

const persistSelf = () => {
  localStorage.setItem(SELF_KEY, JSON.stringify(selfPicks.value))
}

const toggleSelf = (id) => {
  selfPicks.value = isSelf(id)
    ? selfPicks.value.filter(x => x !== id)
    : [id, ...selfPicks.value].slice(0, 20)
  persistSelf()
}

// ---------- 选择 ----------
const onSelect = (val) => {
  // 记录最近选择到自选（上限20）
  const ids = Array.isArray(val) ? val : (val ? [val] : [])
  let changed = false
  for (const id of ids) {
    if (id && !isSelf(id)) {
      selfPicks.value = [id, ...selfPicks.value].slice(0, 20)
      changed = true
    }
  }
  if (changed) persistSelf()
  emit('update:modelValue', val)
  emit('change', val)
}

// ---------- 回显 / 响应变化 ----------
watch(
  () => props.modelValue,
  async (val) => {
    const ids = Array.isArray(val) ? val : (val ? [val] : [])
    const missing = ids.filter(id => !allOptions.value.some(o => o.inst_id === id))
    if (missing.length) {
      if (!allOptions.value.length) await loadAll()
      await ensureExtra()
    }
  },
  { immediate: true }
)

watch(
  () => props.instType,
  () => {
    searching.value = false
    loadAll(true)
  }
)

onMounted(() => {
  loadAll()
})

onBeforeUnmount(() => {
  clearTimeout(searchTimer)
})
</script>

<style scoped>
.inst-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.inst-id {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.inst-right {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.inst-type-tag {
  color: #909399;
  font-size: 12px;
}
.inst-star {
  font-size: 13px;
  cursor: pointer;
  color: #c0c4cc;
  transition: color .15s;
}
.inst-star:hover,
.inst-star.on {
  color: #e6a23c;
}
.inst-empty {
  padding: 8px 0;
  color: #909399;
  font-size: 13px;
  text-align: center;
}
.inst-hl {
  background: #fff3cd;
  color: #e6a23c;
  padding: 0 1px;
  border-radius: 2px;
}
:deep(.el-select-dropdown__item) {
  height: auto;
  line-height: 24px;
  padding: 4px 12px;
}
</style>
