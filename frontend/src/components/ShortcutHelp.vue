<template>
  <el-dialog v-model="visible" title="使用帮助" width="640px" append-to-body class="help-dialog">
    <el-tabs v-model="activeTab">
      <!-- 快捷键 -->
      <el-tab-pane label="快捷键" name="shortcuts">
        <div class="shortcut-list">
          <div v-for="item in shortcuts" :key="item.key + (item.ctrl ? '-ctrl' : '')" class="shortcut-row">
            <span class="shortcut-desc">{{ item.description || '未命名操作' }}</span>
            <div class="shortcut-keys">
              <kbd v-if="item.ctrl" class="key">{{ isMac ? '⌘' : 'Ctrl' }}</kbd>
              <kbd v-if="item.shift" class="key">Shift</kbd>
              <kbd v-if="item.alt" class="key">Alt</kbd>
              <kbd class="key">{{ displayKey(item.key) }}</kbd>
            </div>
          </div>
          <div v-if="!shortcuts.length" class="empty">暂无已注册快捷键</div>
        </div>
      </el-tab-pane>

      <!-- 新手引导 -->
      <el-tab-pane label="新手引导" name="guide">
        <el-timeline>
          <el-timeline-item
            v-for="(step, idx) in guideSteps"
            :key="idx"
            :timestamp="`第 ${idx + 1} 步`"
            placement="top"
            type="primary"
          >
            <h4 class="step-title">{{ step.title }}</h4>
            <p class="step-desc">{{ step.desc }}</p>
          </el-timeline-item>
        </el-timeline>
        <el-alert
          title="温馨提示"
          type="warning"
          :closable="false"
          show-icon
        >
          新手请先在「模拟盘」完成至少 2 周策略验证，再考虑切换实盘。实盘交易使用真实资金，请务必谨慎。
        </el-alert>
      </el-tab-pane>

      <!-- 术语速查 -->
      <el-tab-pane label="术语速查" name="terms">
        <el-input
          v-model="termSearch"
          placeholder="搜索术语..."
          clearable
          :prefix-icon="Search"
          style="margin-bottom: 12px"
        />
        <div class="term-list">
          <div v-for="t in filteredTerms" :key="t.key" class="term-card">
            <div class="term-card-title">
              <span>{{ t.value.title }}</span>
              <el-tag size="small" type="info">{{ t.group }}</el-tag>
            </div>
            <p class="term-card-short">{{ t.value.short }}</p>
            <p class="term-card-detail">{{ t.value.detail }}</p>
            <el-alert
              v-if="t.value.tip"
              :title="t.value.tip"
              type="warning"
              :closable="false"
              show-icon
            />
          </div>
          <div v-if="!filteredTerms.length" class="empty">未找到匹配术语</div>
        </div>
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <el-button type="primary" @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { listShortcuts } from '@/composables/useKeyboard'
import { terms } from '@/utils/terms'

const visible = ref(false)
const activeTab = ref('shortcuts')
const termSearch = ref('')

const isMac = computed(() => /Mac|iPhone|iPad/.test(navigator.userAgent))

const shortcuts = ref([])
function refresh() {
  shortcuts.value = listShortcuts().filter((s) => s.description)
}
function open() {
  refresh()
  visible.value = true
}
defineExpose({ open })

function displayKey(k) {
  if (k === '/' || k === '?') return k
  if (k.length === 1) return k.toUpperCase()
  return k
}

const guideSteps = [
  { title: '配置 OKX 凭证', desc: '在「系统设置」中填入 OKX API Key（先从模拟盘开始，Type 选 Demo）。系统会用它连接交易所拉取行情和下单。' },
  { title: '同步交易品种', desc: '在「行情数据-交易品种」点击同步，把 OKX 的合约/现货品种导入系统，后续选品种时才有数据。' },
  { title: '拉取 K 线数据', desc: '在「K线数据」选择品种和周期，点击「拉取」从 OKX 下载历史 K 线，策略和回测都依赖这些数据。' },
  { title: '创建并回测策略', desc: '在「策略管理」新建策略，选择类型和参数后先「回测」看历史表现，重点关注最大回撤和夏普比率。' },
  { title: '激活策略生成信号', desc: '回测满意后「激活」策略，系统会按 K 线周期自动运行并生成买卖信号。' },
  { title: '执行信号下单', desc: '在「交易信号」查看策略产生的信号，确认后手动执行，或配置自动执行。订单可在「订单管理」查看。' },
  { title: '持续监控与风控', desc: '通过「仪表盘」和「净值曲线」监控账户，确保止损参数合理。出现异常及时暂停策略。' },
]

// 术语分组
const groupNames = {
  demo: '通用', live: '通用', leverage: '通用', td_mode: '通用', position: '通用',
  stop_loss: '通用', take_profit: '通用',
  strategy: '策略', factor_composite: '策略', trend_follow: '策略', volume_breakout: '策略',
  factor: '策略', backtest: '策略', sharpe: '策略', max_drawdown: '策略', win_rate: '策略',
  signal: '策略', params_optimize: '策略', risk_per_trade: '策略',
  kline: 'K线', ma: 'K线', ema: 'K线', boll: 'K线', macd: 'K线', kdj: 'K线', rsi: 'K线', wr: 'K线', atr: 'K线',
  ord_type: '订单', iceberg: '订单', twap: '订单', state_live: '订单', state_filled: '订单',
  net_value: '账户', funding_rate: '账户',
}

const allTerms = computed(() =>
  Object.entries(terms).map(([key, value]) => ({
    key,
    value,
    group: groupNames[key] || '其他',
  })),
)

const filteredTerms = computed(() => {
  const kw = termSearch.value.trim().toLowerCase()
  if (!kw) return allTerms.value
  return allTerms.value.filter(
    (t) =>
      t.value.title.toLowerCase().includes(kw) ||
      t.value.short.toLowerCase().includes(kw) ||
      t.value.detail.toLowerCase().includes(kw),
  )
})
</script>

<style scoped>
.shortcut-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.shortcut-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light, #f5f7fa);
}

.shortcut-keys {
  display: flex;
  gap: 4px;
  align-items: center;
}

.key {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 24px;
  padding: 0 6px;
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-bottom-width: 2px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--el-text-color-primary, #303133);
}

.shortcut-desc {
  font-size: 14px;
  color: var(--el-text-color-regular, #606266);
}

.step-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--el-text-color-primary, #303133);
}

.step-desc {
  font-size: 13px;
  color: var(--el-text-color-regular, #606266);
  line-height: 1.6;
}

.term-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 460px;
  overflow-y: auto;
  padding-right: 4px;
}

.term-card {
  padding: 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light, #f5f7fa);
}

.term-card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--el-text-color-primary, #303133);
}

.term-card-short {
  font-size: 13px;
  color: var(--el-color-primary, #409eff);
  margin-bottom: 6px;
}

.term-card-detail {
  font-size: 13px;
  color: var(--el-text-color-regular, #606266);
  line-height: 1.6;
  white-space: pre-line;
  margin-bottom: 8px;
}

.empty {
  text-align: center;
  color: var(--el-text-color-secondary, #909399);
  padding: 24px 0;
}
</style>
