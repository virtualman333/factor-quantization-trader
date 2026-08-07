<template>
  <div>
    <div class="page-header">
      <h2>创建订单</h2>
    </div>
    <el-card style="margin-top:16px;max-width:600px">
      <el-form :model="form" label-width="100px">
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
        <el-form-item label="关联策略">
          <el-input v-model="form.strategy_id" placeholder="可选" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submit">下单</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { createOrder } from '@/api/orders'
import InstrumentSelect from '@/components/InstrumentSelect.vue'
import { ElMessage } from 'element-plus'

const form = reactive({
  inst_id: '', side: 'buy', ord_type: 'market', sz: '', px: '',
  td_mode: 'cash', strategy_id: '',
})
const submitting = ref(false)

const submit = async () => {
  if (!form.inst_id || !form.sz) { ElMessage.warning('请填写品种和数量'); return }
  submitting.value = true
  try {
    await createOrder({ ...form })
    ElMessage.success('下单成功')
    reset()
  } catch (e) { ElMessage.error(e.message) }
  submitting.value = false
}

const reset = () => {
  form.inst_id = ''; form.side = 'buy'; form.ord_type = 'market'
  form.sz = ''; form.px = ''; form.td_mode = 'cash'; form.strategy_id = ''
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
</style>
