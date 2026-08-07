<template>
  <div class="admin-page">
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="用户管理" name="users">
        <div class="toolbar">
          <el-input
            v-model="userSearch"
            placeholder="搜索用户名"
            clearable
            style="width: 200px"
            @input="onUserSearch"
          />
          <el-button type="primary" @click="loadUsers">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>
        <el-table :data="users" v-loading="loading" stripe border style="margin-top: 12px">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="username" label="用户名" min-width="120" />
          <el-table-column label="角色" width="180">
            <template #default="{ row }">
              <el-tag v-if="row.is_superuser" type="danger" size="small">超级管理员</el-tag>
              <el-tag v-else-if="row.is_staff" type="warning" size="small">管理员</el-tag>
              <el-tag v-else type="info" size="small">普通用户</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="strategy_count" label="策略数" width="80" align="center" />
          <el-table-column prop="order_count" label="订单数" width="80" align="center" />
          <el-table-column label="配额" min-width="200">
            <template #default="{ row }">
              <div v-if="row.quota" class="quota-info">
                <span>策略{{ row.quota.max_strategies }}个</span>
                <el-divider direction="vertical" />
                <span>下单{{ row.quota.max_orders_per_day }}次/日</span>
                <el-divider direction="vertical" />
                <span>API {{ row.quota.max_api_calls_per_minute }}次/分</span>
                <el-divider direction="vertical" />
                <el-tag v-if="row.quota.is_trading_enabled" type="success" size="small">可交易</el-tag>
                <el-tag v-else type="danger" size="small">禁止交易</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="注册时间" width="170">
            <template #default="{ row }">{{ formatDate(row.date_joined) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="toggleUserActive(row)">
                {{ row.is_active ? '禁用' : '启用' }}
              </el-button>
              <el-button v-if="!row.is_superuser" size="small" type="warning" @click="toggleUserStaff(row)">
                {{ row.is_staff ? '取消管理' : '设为管理' }}
              </el-button>
              <el-button size="small" type="primary" @click="editQuota(row)">配额</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="统计面板" name="stats">
        <el-row :gutter="20">
          <el-col :xs="12" :md="6" v-for="card in statCards" :key="card.key">
            <el-card shadow="hover">
              <el-statistic :title="card.title" :value="card.value" />
            </el-card>
          </el-col>
        </el-row>
        <el-card shadow="never" style="margin-top: 20px">
          <template #header><span>用户活跃度概览</span></template>
          <el-table :data="statsUsers" stripe>
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="strategy_count" label="策略数" />
            <el-table-column prop="order_count" label="订单数" />
            <el-table-column label="最后登录">
              <template #default="{ row }">{{ formatDate(row.last_login) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="全局配置" name="global">
        <el-form :model="globalConfig" label-width="180px" label-position="right">
          <el-divider content-position="left">注册控制</el-divider>
          <el-form-item label="允许新用户注册">
            <el-switch v-model="globalConfig.allow_registration" />
          </el-form-item>

          <el-divider content-position="left">行情数据同步</el-divider>
          <el-form-item label="同步间隔(秒)">
            <el-input-number v-model="globalConfig.market_sync_interval" :min="10" :max="3600" />
          </el-form-item>
          <el-form-item label="同步交易品种">
            <el-switch v-model="globalConfig.market_sync_instruments" />
          </el-form-item>
          <el-form-item label="同步行情快照">
            <el-switch v-model="globalConfig.market_sync_tickers" />
          </el-form-item>
          <el-form-item label="同步K线数据">
            <el-switch v-model="globalConfig.market_sync_klines" />
          </el-form-item>
          <el-form-item label="行情快照最大品种数">
            <el-input-number v-model="globalConfig.max_tickers_sync_count" :min="10" :max="200" />
          </el-form-item>

          <el-divider content-position="left">全局风控参数</el-divider>
          <el-form-item label="最大持仓比例">
            <el-input-number v-model="globalConfig.global_max_position_pct" :min="0.01" :max="1" :step="0.01" :precision="4" />
          </el-form-item>
          <el-form-item label="最大订单价值(USD)">
            <el-input-number v-model="globalConfig.global_max_order_value" :min="100" :max="1000000" :step="100" />
          </el-form-item>
          <el-form-item label="最大日亏损(USD)">
            <el-input-number v-model="globalConfig.global_max_daily_loss" :min="10" :max="100000" :step="10" />
          </el-form-item>
          <el-form-item label="止损比例">
            <el-input-number v-model="globalConfig.global_stop_loss_pct" :min="0.01" :max="0.5" :step="0.01" :precision="4" />
          </el-form-item>
          <el-form-item label="最小下单间隔(秒)">
            <el-input-number v-model="globalConfig.global_min_order_interval" :min="0.1" :max="10" :step="0.1" :precision="2" />
          </el-form-item>
          <el-form-item label="默认杠杆倍数">
            <el-input-number v-model="globalConfig.global_default_leverage" :min="1" :max="125" />
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="savingGlobal" @click="saveGlobalConfig">
              保存全局配置
            </el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <!-- 配额编辑对话框 -->
    <el-dialog v-model="quotaDialogVisible" title="编辑用户配额" width="500px">
      <el-form v-if="editingQuota" :model="editingQuota" label-width="160px">
        <el-form-item label="用户">
          <el-input :model-value="editingQuota.username" disabled />
        </el-form-item>
        <el-form-item label="最大策略数">
          <el-input-number v-model="editingQuota.max_strategies" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="每日最大下单次数">
          <el-input-number v-model="editingQuota.max_orders_per_day" :min="1" :max="10000" />
        </el-form-item>
        <el-form-item label="每分钟最大API调用">
          <el-input-number v-model="editingQuota.max_api_calls_per_minute" :min="10" :max="600" />
        </el-form-item>
        <el-form-item label="单次K线查询上限">
          <el-input-number v-model="editingQuota.max_klines_per_request" :min="100" :max="2000" />
        </el-form-item>
        <el-form-item label="允许交易">
          <el-switch v-model="editingQuota.is_trading_enabled" />
        </el-form-item>
        <el-form-item label="允许数据同步">
          <el-switch v-model="editingQuota.is_data_sync_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quotaDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingQuota" @click="saveQuota">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { adminApi } from '@/api/admin.js'
import { formatDateTime } from '@/utils/time'

const activeTab = ref('users')
const loading = ref(false)
const savingGlobal = ref(false)
const savingQuota = ref(false)
const users = ref([])
const userSearch = ref('')

const globalConfig = reactive({
  allow_registration: true,
  market_sync_interval: 60,
  market_sync_instruments: true,
  market_sync_tickers: true,
  market_sync_klines: true,
  max_tickers_sync_count: 50,
  global_max_position_pct: 0.2,
  global_max_order_value: 10000,
  global_max_daily_loss: 500,
  global_stop_loss_pct: 0.05,
  global_min_order_interval: 1.0,
  global_default_leverage: 3,
})

const quotaDialogVisible = ref(false)
const editingQuota = ref(null)

const statsUsers = ref([])
const statCards = computed(() => [
  { key: 'total_users', title: '总用户数', value: users.value.length },
  { key: 'active_users', title: '活跃用户', value: users.value.filter(u => u.is_active).length },
  { key: 'total_strategies', title: '总策略数', value: users.value.reduce((s, u) => s + (u.strategy_count || 0), 0) },
  { key: 'total_orders', title: '总订单数', value: users.value.reduce((s, u) => s + (u.order_count || 0), 0) },
])

function formatDate(dateStr) {
  // 统一按北京时间显示
  return formatDateTime(dateStr)
}

async function loadUsers() {
  loading.value = true
  try {
    const params = {}
    if (userSearch.value) params.search = userSearch.value
    const res = await adminApi.listUsers(params)
    users.value = Array.isArray(res.results) ? res.results : (res.data || res)
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    loading.value = false
  }
}

async function loadGlobalConfig() {
  try {
    const res = await adminApi.getGlobalConfig()
    if (res) Object.assign(globalConfig, res)
  } catch (err) {
    // 非管理员会报 403，忽略
  }
}

async function saveGlobalConfig() {
  savingGlobal.value = true
  try {
    await adminApi.updateGlobalConfig({ ...globalConfig })
    ElMessage.success('全局配置保存成功')
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    savingGlobal.value = false
  }
}

async function toggleUserActive(user) {
  try {
    await adminApi.toggleUserActive(user.id)
    user.is_active = !user.is_active
    ElMessage.success(`${user.username} ${user.is_active ? '已启用' : '已禁用'}`)
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function toggleUserStaff(user) {
  try {
    await adminApi.toggleUserStaff(user.id)
    user.is_staff = !user.is_staff
    ElMessage.success(`${user.username} ${user.is_staff ? '已设为管理员' : '已取消管理员'}`)
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function editQuota(user) {
  try {
    const res = await adminApi.getQuotaByUser(user.id)
    editingQuota.value = { ...res, username: user.username }
    quotaDialogVisible.value = true
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function saveQuota() {
  if (!editingQuota.value) return
  savingQuota.value = true
  try {
    await adminApi.updateQuota(editingQuota.value.id, editingQuota.value)
    ElMessage.success('配额保存成功')
    quotaDialogVisible.value = false
    await loadUsers()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    savingQuota.value = false
  }
}

function onUserSearch() {
  loadUsers()
}

onMounted(() => {
  loadUsers()
  loadGlobalConfig()
  statsUsers.value = users.value
})
</script>

<style scoped>
.admin-page { padding-bottom: 40px; }
.toolbar { display: flex; gap: 12px; align-items: center; }
.quota-info { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; font-size: 12px; }
</style>
