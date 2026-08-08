<template>
  <div>
    <div class="page-header">
      <h2>创建订单</h2>
    </div>
    <el-card style="margin-top:16px">
      <el-tabs v-model="activeTab">
        <!-- 普通下单 -->
        <el-tab-pane label="普通下单" name="normal">
          <el-form :model="form" label-width="100px" style="max-width:600px">
            <el-form-item label="交易品种">
              <instrument-select v-model="form.inst_id" placeholder="搜索品种" width="100%" />
            </el-form-item>
            <el-form-item label="方向">
              <el-radio-group v-model="form.side">
                <el-radio-button value="buy">买入</el-radio-button>
                <el-radio-button value="sell">卖出</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="订单类型">
              <el-select v-model="form.ord_type">
                <el-option label="市价" value="market" />
                <el-option label="限价" value="limit" />
                <el-option label="只挂单" value="post_only" />
                <el-option label="全部成交或取消" value="fok" />
                <el-option label="立即成交或取消" value="ioc" />
              </el-select>
            </el-form-item>
            <el-form-item label="数量">
              <el-input v-model="form.sz" placeholder="0.01" />
            </el-form-item>
            <el-form-item v-if="form.ord_type !== 'market'" label="价格">
              <el-input v-model="form.px" placeholder="限价价格" />
            </el-form-item>
            <el-form-item label="交易模式">
              <el-select v-model="form.td_mode">
                <el-option label="现金" value="cash" />
                <el-option label="全仓" value="cross" />
                <el-option label="逐仓" value="isolated" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="submit">下单</el-button>
              <el-button @click="reset">重置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 批量下单 -->
        <el-tab-pane label="批量下单" name="batch">
          <div v-for="(row, idx) in batchOrders" :key="idx" class="batch-row">
            <instrument-select v-model="row.inst_id" placeholder="品种" width="150px" />
            <el-select v-model="row.side" style="width:80px">
              <el-option label="买" value="buy" />
              <el-option label="卖" value="sell" />
            </el-select>
            <el-input v-model="row.sz" placeholder="数量" style="width:110px" />
            <el-button type="danger" text @click="batchOrders.splice(idx, 1)">移除</el-button>
          </div>
          <el-button size="small" type="primary" text @click="addBatchRow">+ 添加订单</el-button>
          <div style="margin-top:16px">
            <el-button type="primary" :loading="batchLoading" @click="submitBatch">批量提交</el-button>
          </div>
          <el-alert v-if="batchResult" :title="`提交 ${batchResult.total} 笔，成功 ${batchResult.success} 笔`" type="success" style="margin-top:12px" />
        </el-tab-pane>

        <!-- 条件单 -->
        <el-tab-pane label="条件单/止盈止损" name="algo">
          <el-form :model="algoForm" label-width="100px" style="max-width:600px">
            <el-form-item label="交易品种">
              <instrument-select v-model="algoForm.inst_id" placeholder="搜索品种" width="100%" />
            </el-form-item>
            <el-form-item label="方向">
              <el-radio-group v-model="algoForm.side">
                <el-radio-button value="buy">买入</el-radio-button>
                <el-radio-button value="sell">卖出</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="数量">
              <el-input v-model="algoForm.sz" placeholder="0.01" />
            </el-form-item>
            <el-form-item label="触发价">
              <el-input v-model="algoForm.trigger_px" placeholder="条件单触发价（可选）" />
            </el-form-item>
            <el-form-item label="止盈触发价">
              <el-input v-model="algoForm.tp_trigger_px" placeholder="可选" />
            </el-form-item>
            <el-form-item label="止损触发价">
              <el-input v-model="algoForm.sl_trigger_px" placeholder="可选" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="algoLoading" @click="submitAlgo">提交条件单</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 算法单 -->
        <el-tab-pane label="算法单" name="algo2">
          <el-form :model="twapForm" label-width="100px" style="max-width:600px">
            <el-form-item label="交易品种">
              <instrument-select v-model="twapForm.inst_id" placeholder="搜索品种" width="100%" />
            </el-form-item>
            <el-form-item label="方向">
              <el-radio-group v-model="twapForm.side">
                <el-radio-button value="buy">买入</el-radio-button>
                <el-radio-button value="sell">卖出</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="总数量">
              <el-input v-model="twapForm.total_sz" placeholder="总数量" />
            </el-form-item>
            <el-form-item label="算法类型">
              <el-radio-group v-model="twapForm.type">
                <el-radio-button value="twap">TWAP</el-radio-button>
                <el-radio-button value="iceberg">冰山</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="切片数">
              <el-input-number v-model="twapForm.slices" :min="2" :max="20" />
            </el-form-item>
            <el-form-item label="间隔(秒)" v-if="twapForm.type === 'twap'">
              <el-input-number v-model="twapForm.interval" :min="10" :max="3600" />
            </el-form-item>
            <el-form-item label="限价" v-if="twapForm.type === 'iceberg'">
              <el-input v-model="twapForm.px" placeholder="冰山单限价（可选）" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="twapLoading" @click="submitAlgo2">提交算法单</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 订单模板 -->
    <el-card style="margin-top:16px">
      <template #header>
        <div class="card-header">
          <span>订单模板</span>
          <el-button size="small" type="primary" @click="tplDialog = true">新建模板</el-button>
        </div>
      </template>
      <el-table :data="templates" size="small" border>
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="inst_id" label="品种" width="130">
          <template #default="{ row }">{{ row.inst_id || '任意' }}</template>
        </el-table-column>
        <el-table-column prop="side" label="方向" width="80">
          <template #default="{ row }">{{ row.side === 'buy' ? '买入' : '卖出' }}</template>
        </el-table-column>
        <el-table-column prop="sz" label="数量" width="100" />
        <el-table-column prop="px" label="价格" width="100">
          <template #default="{ row }">{{ row.px || '市价' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="placeTemplate(row)">下单</el-button>
            <el-button size="small" type="danger" text @click="removeTemplate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!templates.length" description="暂无模板" :image-size="60" />
    </el-card>

    <!-- 新建模板弹窗 -->
    <el-dialog v-model="tplDialog" title="新建订单模板" width="520px">
      <el-form label-width="100px">
        <el-form-item label="模板名称"><el-input v-model="tplForm.name" /></el-form-item>
        <el-form-item label="品种"><instrument-select v-model="tplForm.inst_id" placeholder="留空则任意" width="100%" /></el-form-item>
        <el-form-item label="方向">
          <el-radio-group v-model="tplForm.side">
            <el-radio-button value="buy">买入</el-radio-button>
            <el-radio-button value="sell">卖出</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="数量"><el-input v-model="tplForm.sz" /></el-form-item>
        <el-form-item label="限价"><el-input v-model="tplForm.px" placeholder="留空为市价" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tplDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTemplate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'OrderCreate' })
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { createOrder, batchCreateOrders, placeAlgoOrder, placeTwapOrder, placeIcebergOrder, getOrderTemplates, createOrderTemplate, deleteOrderTemplate, placeOrderByTemplate } from '@/api/orders'
import InstrumentSelect from '@/components/InstrumentSelect.vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()

const activeTab = ref('normal')

const form = reactive({
  inst_id: '', side: 'buy', ord_type: 'market', sz: '', px: '',
  td_mode: 'cash', strategy_id: '',
})
const submitting = ref(false)

/** 清洗提交 payload：空字符串字段（除保留用）置 null，防止后端字段类型报错 */
function cleanPayload(obj, keepEmptyKeys = ['px', 'pos_side']) {
  const out = { ...obj }
  for (const k of Object.keys(out)) {
    if (keepEmptyKeys.includes(k)) continue
    if (out[k] === '' || out[k] == null || out[k] === 0) {
      if (k === 'strategy_id' || k === 'signal_id') {
        out[k] = null
      }
    }
  }
  return out
}

const submit = async () => {
  if (!form.inst_id || !form.sz) { ElMessage.warning('请填写品种和数量'); return }
  submitting.value = true
  try {
    await createOrder(cleanPayload(form))
    ElMessage.success('下单成功')
    reset()
  } catch (e) {
    const msg = e.message || ''
    if (msg.includes('凭证')) {
      ElMessageBox.confirm(
        '当前账号尚未配置 OKX API 凭证，无法下单。是否前往「系统设置-API凭证」配置？',
        '需要配置凭证',
        { confirmButtonText: '去配置', cancelButtonText: '取消', type: 'warning' }
      ).then(() => {
        router.push('/settings')
      }).catch(() => {})
    } else {
      ElMessage.error(msg)
    }
  }
  submitting.value = false
}

const reset = () => {
  form.inst_id = ''; form.side = 'buy'; form.ord_type = 'market'
  form.sz = ''; form.px = ''; form.td_mode = 'cash'; form.strategy_id = ''
}

// ---------- 批量下单 ----------
const batchOrders = ref([{ inst_id: '', side: 'buy', sz: '' }])
const batchLoading = ref(false)
const batchResult = ref(null)
const addBatchRow = () => batchOrders.value.push({ inst_id: '', side: 'buy', sz: '' })
const submitBatch = async () => {
  const valid = batchOrders.value.filter(o => o.inst_id && o.sz).map(o => cleanPayload(o))
  if (!valid.length) { ElMessage.warning('请填写批量订单'); return }
  batchLoading.value = true
  try {
    batchResult.value = await batchCreateOrders({ orders: valid })
    ElMessage.success(`批量提交完成，成功 ${batchResult.value.success} 笔`)
  } catch (e) { ElMessage.error(e.message) }
  batchLoading.value = false
}

// ---------- 条件单 ----------
const algoForm = reactive({ inst_id: '', side: 'buy', sz: '', trigger_px: '', tp_trigger_px: '', sl_trigger_px: '' })
const algoLoading = ref(false)
const submitAlgo = async () => {
  if (!algoForm.inst_id || !algoForm.sz) { ElMessage.warning('请填写品种和数量'); return }
  algoLoading.value = true
  try {
    await placeAlgoOrder({ ...algoForm })
    ElMessage.success('条件单已提交')
  } catch (e) { ElMessage.error(e.message) }
  algoLoading.value = false
}

// ---------- 算法单 ----------
const twapForm = reactive({ inst_id: '', side: 'buy', total_sz: '', type: 'twap', slices: 5, interval: 60, px: '' })
const twapLoading = ref(false)
const submitAlgo2 = async () => {
  if (!twapForm.inst_id || !twapForm.total_sz) { ElMessage.warning('请填写品种和数量'); return }
  twapLoading.value = true
  try {
    if (twapForm.type === 'twap') {
      await placeTwapOrder({ inst_id: twapForm.inst_id, side: twapForm.side, total_sz: twapForm.total_sz, slices: twapForm.slices, interval: twapForm.interval })
    } else {
      await placeIcebergOrder({ inst_id: twapForm.inst_id, side: twapForm.side, total_sz: twapForm.total_sz, display_sz: twapForm.total_sz, slices: twapForm.slices, px: twapForm.px })
    }
    ElMessage.success('算法单已提交')
  } catch (e) { ElMessage.error(e.message) }
  twapLoading.value = false
}

// ---------- 模板 ----------
const templates = ref([])
const tplDialog = ref(false)
const tplForm = reactive({ name: '', inst_id: '', side: 'buy', sz: '', px: '' })
const loadTemplates = async () => {
  try {
    const res = await getOrderTemplates()
    templates.value = res.results || res || []
  } catch {}
}
const saveTemplate = async () => {
  if (!tplForm.name) { ElMessage.warning('请输入模板名称'); return }
  try {
    await createOrderTemplate({ ...tplForm })
    ElMessage.success('模板已保存')
    tplDialog.value = false
    tplForm.name = ''; tplForm.inst_id = ''; tplForm.sz = ''; tplForm.px = ''
    loadTemplates()
  } catch (e) { ElMessage.error(e.message) }
}
const placeTemplate = async (row) => {
  try {
    await placeOrderByTemplate(row.id, {})
    ElMessage.success('已按模板下单')
  } catch (e) { ElMessage.error(e.message) }
}
const removeTemplate = async (row) => {
  await ElMessageBox.confirm(`确认删除模板「${row.name}」？`, '提示', { type: 'warning' })
  await deleteOrderTemplate(row.id)
  loadTemplates()
}

onMounted(loadTemplates)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.batch-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
