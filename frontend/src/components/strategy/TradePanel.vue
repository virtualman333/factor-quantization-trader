<template>
  <div class="trade-panel">
    <div class="tp-header">
      <span>快捷交易</span>
      <span class="tp-env">{{ envLabel }}</span>
    </div>

    <!-- 当前价格 -->
    <div class="tp-price">
      <span class="price-label">现价</span>
      <span class="price-value" :class="lastPriceChange >= 0 ? 'up' : 'down'">
        {{ lastPrice || '--' }}
      </span>
    </div>

    <!-- 持仓信息 -->
    <div v-if="positionInfo" class="tp-position">
      <div class="pos-row">
        <span>持仓方向</span>
        <span>
          <el-tag size="small" :type="positionInfo.side === 'long' ? 'danger' : 'success'" effect="plain">
            {{ positionInfo.side === 'long' ? '多' : '空' }}
          </el-tag>
        </span>
      </div>
      <div class="pos-row">
        <span>持仓量</span>
        <span>{{ positionInfo.pos }}</span>
      </div>
      <div class="pos-row">
        <span>可用</span>
        <span>{{ positionInfo.avail ?? '--' }}</span>
      </div>
    </div>
    <div v-else class="tp-position empty">当前无持仓</div>

    <el-divider style="margin:10px 0" />

    <!-- 模式切换：现货 / 合约 -->
    <el-radio-group v-model="mode" size="small" class="tp-mode">
      <el-radio-button value="spot">现货</el-radio-button>
      <el-radio-button value="swap">合约</el-radio-button>
    </el-radio-group>

    <!-- 合约参数 -->
    <template v-if="mode === 'swap'">
      <div class="tp-row">
        <span class="tp-label">方向</span>
        <el-radio-group v-model="side" size="small">
          <el-radio-button value="buy">开多</el-radio-button>
          <el-radio-button value="sell">开空</el-radio-button>
          <el-radio-button value="close" :disabled="!positionInfo">平仓</el-radio-button>
        </el-radio-group>
      </div>
      <div class="tp-row">
        <span class="tp-label">保证金</span>
        <el-select v-model="tdMode" size="small" style="width:110px">
          <el-option label="全仓" value="cross" />
          <el-option label="逐仓" value="isolated" />
        </el-select>
      </div>
      <div class="tp-row">
        <span class="tp-label">杠杆</span>
        <el-input-number v-model="leverage" :min="1" :max="125" size="small" controls-position="right" style="width:110px" />
      </div>
    </template>

    <!-- 现货方向 -->
    <div v-else class="tp-row">
      <span class="tp-label">方向</span>
      <el-radio-group v-model="side" size="small">
        <el-radio-button value="buy">买入</el-radio-button>
        <el-radio-button value="sell" :disabled="!positionInfo">卖出</el-radio-button>
      </el-radio-group>
      <span v-if="mode === 'spot' && side === 'sell' && !positionInfo" class="tp-warn">无持仓</span>
    </div>

    <!-- 数量/金额 -->
    <div class="tp-row">
      <span class="tp-label">数量</span>
      <el-input v-model="sz" size="small" placeholder="0.01" />
    </div>
    <div class="tp-row" v-if="mode === 'spot' && side === 'buy'">
      <span class="tp-label">买入额</span>
      <span class="tp-value">{{ buyAmountText }}</span>
      <el-button size="small" text type="primary" @click="fillSpotSz">按余额25%</el-button>
    </div>

    <!-- 快捷比例 -->
    <div class="tp-row tp-pct">
      <el-button size="small" v-for="p in [0.1, 0.25, 0.5, 1]" :key="p" @click="setPct(p)">
        {{ p * 100 }}%
      </el-button>
    </div>

    <!-- 提交 -->
    <el-button
      class="tp-submit"
      :type="submitBtnType"
      :loading="submitting"
      @click="submit"
    >{{ submitText }}</el-button>

    <el-alert v-if="error" :title="error" type="error" :closable="true" show-icon style="margin-top:8px" @close="error = ''" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { createOrder, closePosition } from '@/api/orders'
import { getLiveBalance, getLivePositions } from '@/api/account'
import { useConnectionStore } from '@/stores/connection'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  instId: { type: String, default: '' },
  lastPrice: { type: Number, default: 0 },
})
const emit = defineEmits(['traded'])

const connectionStore = useConnectionStore()
const envLabel = computed(() => connectionStore.envLabel)

const mode = ref('spot')
const side = ref('buy')
const tdMode = ref('cross')
const leverage = ref(3)
const sz = ref('')
const submitting = ref(false)
const error = ref('')

// 实时价格方向（用于颜色）
const lastPriceChange = ref(0)
watch(() => props.lastPrice, (v, old) => {
  lastPriceChange.value = v > old ? 1 : v < old ? -1 : 0
}, { immediate: true })

// 持仓与余额
const positionInfo = ref(null)
const balanceMap = ref({})

const isSwap = computed(() => mode.value === 'swap')

// 从 instId 解析基础币（如 BTC-USDT -> BTC）
const baseCcy = computed(() => (props.instId || '').split('-')[0])

const loadPosition = async () => {
  if (!props.instId) return
  try {
    if (isSwap.value) {
      const res = await getLivePositions({ inst_type: 'SWAP' })
      const rows = res.results || res || []
      const pos = rows.find((p) => p.instId === props.instId)
      positionInfo.value = pos ? { side: pos.posSide, pos: pos.pos, avail: undefined } : null
    } else {
      const res = await getLiveBalance()
      const details = res.details || []
      const coin = details.find((d) => d.ccy === baseCcy.value)
      const usdt = details.find((d) => d.ccy === 'USDT')
      if (usdt) balanceMap.value.usdt = usdt.avail_eq || usdt.cashBal || 0
      if (coin) {
        const avail = parseFloat(coin.avail_eq || coin.cashBal || 0)
        const frozen = parseFloat(coin.frozen_bal || 0)
        positionInfo.value = { side: 'long', pos: avail + frozen, avail }
      } else {
        positionInfo.value = null
      }
    }
  } catch {
    positionInfo.value = null
  }
}

const buyAmountText = computed(() => {
  if (!props.lastPrice || !sz.value) return '--'
  return (parseFloat(sz.value) * props.lastPrice).toFixed(2)
})

const fillSpotSz = () => {
  const usdt = parseFloat(balanceMap.value.usdt || 0)
  if (!usdt || !props.lastPrice) return
  sz.value = ((usdt * 0.25) / props.lastPrice).toFixed(4)
}

const setPct = (p) => {
  if (isSwap.value) {
    // 合约：按杠杆后的可用资金估算
    const usdt = parseFloat(balanceMap.value.usdt || 1000)
    if (!props.lastPrice) return
    sz.value = ((usdt * p * leverage.value) / props.lastPrice).toFixed(6)
  } else if (side.value === 'buy') {
    const usdt = parseFloat(balanceMap.value.usdt || 0)
    if (!usdt || !props.lastPrice) return
    sz.value = ((usdt * p) / props.lastPrice).toFixed(4)
  } else {
    // 卖出：按持仓量
    const pos = parseFloat(positionInfo.value?.pos || 0)
    if (!pos) return
    sz.value = (pos * p).toFixed(6)
  }
}

// 方向变化时重置数量
watch([mode, side, () => props.instId], () => {
  sz.value = ''
  error.value = ''
  loadPosition()
})

const submitBtnType = computed(() => {
  if (side.value === 'buy') return 'danger'
  if (side.value === 'close') return 'warning'
  return 'success'
})

const submitText = computed(() => {
  if (isSwap.value) {
    return side.value === 'buy' ? '开多' : side.value === 'sell' ? '开空' : '平仓'
  }
  return side.value === 'buy' ? '买入' : '卖出'
})

const submit = async () => {
  if (!props.instId) { error.value = '请先选择品种'; return }
  if (!sz.value || parseFloat(sz.value) <= 0) { error.value = '请输入有效数量'; return }

  const instId = isSwap.value && !props.instId.includes('-SWAP')
    ? `${props.instId}-SWAP`
    : props.instId

  submitting.value = true
  error.value = ''
  try {
    if (isSwap.value && side.value === 'close') {
      // 合约平仓：使用 close_position 接口
      await closePosition({
        inst_id: instId,
        pos_side: positionInfo.value?.side,
        sz: sz.value,
      })
      ElMessage.success('平仓成功')
    } else {
      const payload = {
        inst_id: instId,
        side: side.value,
        ord_type: 'market',
        sz: sz.value,
      }
      if (isSwap.value) {
        payload.td_mode = tdMode.value
        payload.pos_side = side.value === 'buy' ? 'long' : 'short'
        payload.leverage = leverage.value
      } else {
        payload.td_mode = 'cash'
      }
      await createOrder(payload)
      ElMessage.success('下单成功')
    }
    emit('traded')
    sz.value = ''
    setTimeout(loadPosition, 1500)
  } catch (e) {
    const msg = e.message || ''
    if (msg.includes('凭证')) {
      ElMessageBox.confirm(
        '当前账号尚未配置 OKX API 凭证，无法下单。是否前往「系统设置-API凭证」配置？',
        '需要配置凭证',
        { confirmButtonText: '去配置', cancelButtonText: '取消', type: 'warning' }
      ).then(() => {
        window.location.hash = '#/settings'
      }).catch(() => {})
    } else {
      error.value = msg
    }
  }
  submitting.value = false
}

onMounted(loadPosition)
</script>

<style scoped>
.trade-panel {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 14px;
  background: #fff;
  font-size: 13px;
}
.tp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  margin-bottom: 8px;
}
.tp-env {
  font-size: 11px;
  color: #909399;
  background: #f4f4f5;
  border-radius: 4px;
  padding: 1px 6px;
}
.tp-price {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 10px;
}
.price-label { color: #909399; font-size: 12px; }
.price-value { font-size: 20px; font-weight: 700; font-family: 'Consolas', monospace; }
.up { color: #f56c6c; }
.down { color: #67c23a; }
.tp-position {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 12px;
}
.tp-position.empty { color: #909399; }
.pos-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
  color: #606266;
}
.tp-mode { margin-bottom: 10px; }
.tp-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.tp-label {
  color: #606266;
  min-width: 34px;
}
.tp-warn { color: #e6a23c; font-size: 11px; }
.tp-value { color: #909399; font-size: 12px; }
.tp-pct {
  justify-content: space-between;
}
.tp-pct .el-button {
  flex: 1;
  margin-left: 0;
}
.tp-submit {
  width: 100%;
  margin-top: 4px;
}
</style>
