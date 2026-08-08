<template>
  <el-tag size="small" :type="tagType" effect="light">{{ label }}</el-tag>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ source: { type: String, default: 'api' } })

const label = computed(() => {
  const s = String(props.source || 'api').toLowerCase()
  return {
    api: '手动', manual: '手动', strategy: '策略', signal: '信号',
    template: '模板', batch: '批量', algo: '条件单', twap: 'TWAP', iceberg: '冰山',
    close: '平仓', backtest: '回测',
  }[s] || s
})

const tagType = computed(() => {
  const s = String(props.source || 'api').toLowerCase()
  if (['strategy', 'signal'].includes(s)) return 'primary'
  if (['algo', 'twap', 'iceberg'].includes(s)) return 'warning'
  if (['close', 'manual'].includes(s)) return 'danger'
  if (['template', 'batch'].includes(s)) return 'success'
  return 'info'
})
</script>
