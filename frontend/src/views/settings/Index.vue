<template>
  <div class="settings-page">
    <el-row :gutter="20">
      <el-col :xs="24" :md="16">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>OKX API 凭证配置</span>
              <el-radio-group v-model="activeEnv" size="small" @change="onEnvChange">
                <el-radio-button label="demo">模拟盘</el-radio-button>
                <el-radio-button label="live">实盘</el-radio-button>
              </el-radio-group>
            </div>
          </template>

          <el-alert
            v-if="activeEnv === 'live'"
            title="当前为实盘环境，请确认 API Key 具有正确权限"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom: 20px;"
          />

          <el-form
            ref="formRef"
            :model="forms[activeEnv]"
            :rules="rules"
            label-width="120px"
            label-position="right"
          >
            <el-form-item label="API Key" prop="api_key">
              <el-input
                v-model="forms[activeEnv].api_key"
                placeholder="请输入 OKX API Key"
                show-password
                clearable
              />
            </el-form-item>

            <el-form-item label="Secret Key" prop="api_secret">
              <el-input
                v-model="forms[activeEnv].api_secret"
                placeholder="请输入 OKX Secret Key"
                show-password
                clearable
              />
            </el-form-item>

            <el-form-item label="Passphrase" prop="passphrase">
              <el-input
                v-model="forms[activeEnv].passphrase"
                placeholder="请输入 API Key 的 Passphrase"
                show-password
                clearable
              />
            </el-form-item>

            <el-form-item label="启用状态">
              <el-switch
                v-model="forms[activeEnv].is_active"
                active-text="启用"
                inactive-text="禁用"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="saving" @click="onSubmit">
                <el-icon><Check /></el-icon>
                保存凭证
              </el-button>
              <el-button :loading="testing" @click="onTestConnection">
                <el-icon><Connection /></el-icon>
                测试连接
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="8">
        <el-card shadow="never">
          <template #header>
            <span>连接状态</span>
          </template>
          <div class="connection-status">
            <el-result
              :icon="connectionStatus.icon"
              :title="connectionStatus.title"
              :sub-title="connectionStatus.subTitle"
            />
          </div>
        </el-card>

        <el-card shadow="never" style="margin-top: 20px;">
          <template #header>
            <span>安全提示</span>
          </template>
          <el-alert
            title="凭证存储说明"
            type="warning"
            :closable="false"
            show-icon
          >
            <div class="tips">
              <p>1. 模拟盘和实盘使用不同的 API Key，请分开配置。</p>
              <p>2. API 凭证保存在 MySQL 数据库中。</p>
              <p>3. 建议仅配置带读取/交易权限的 Key，避免使用提现权限。</p>
              <p>4. 切换环境或修改凭证后系统会自动重置 OKX 客户端。</p>
            </div>
          </el-alert>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, Connection } from '@element-plus/icons-vue'
import { credentialApi } from '@/api/credential.js'
import { useConnectionStore } from '@/stores/connection.js'

const connectionStore = useConnectionStore()
const formRef = ref(null)
const activeEnv = ref('demo')
const saving = ref(false)
const testing = ref(false)
const connectionResult = ref(null)

const forms = reactive({
  demo: { api_key: '', api_secret: '', passphrase: '', is_active: true },
  live: { api_key: '', api_secret: '', passphrase: '', is_active: true },
})

const rules = {
  api_key: [{ required: true, message: '请输入 API Key', trigger: 'blur' }],
  api_secret: [{ required: true, message: '请输入 Secret Key', trigger: 'blur' }],
  passphrase: [{ required: true, message: '请输入 Passphrase', trigger: 'blur' }],
}

const connectionStatus = computed(() => {
  if (testing.value) {
    return { icon: 'info', title: '检测中...', subTitle: '正在连接 OKX API' }
  }
  if (!connectionResult.value) {
    return { icon: 'info', title: '未测试', subTitle: '保存后可点击测试连接' }
  }
  if (connectionResult.value.connected) {
    return { icon: 'success', title: '连接成功', subTitle: '凭证可正常调用 OKX API' }
  }
  return { icon: 'error', title: '连接失败', subTitle: connectionResult.value.error || '请检查凭证配置' }
})

async function loadCredentials() {
  try {
    const [demo, live] = await Promise.all([
      credentialApi.byEnv('demo').catch(() => null),
      credentialApi.byEnv('live').catch(() => null),
    ])
    if (demo) Object.assign(forms.demo, demo)
    if (live) Object.assign(forms.live, live)
  } catch (err) {
    ElMessage.warning(err.message)
  }
}

function onEnvChange() {
  connectionResult.value = null
  formRef.value?.clearValidate()
}

async function onSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const payload = {
      ...forms[activeEnv.value],
      name: activeEnv.value,
      flag: activeEnv.value === 'demo' ? '1' : '0',
    }
    await credentialApi.update(activeEnv.value, payload)
    ElMessage.success(`${activeEnv.value === 'demo' ? '模拟盘' : '实盘'}凭证保存成功`)
    // 如果保存的是当前全局环境，更新连接状态
    if (activeEnv.value === connectionStore.environment) {
      await connectionStore.checkConnection().catch(() => {})
    }
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    saving.value = false
  }
}

async function onTestConnection() {
  testing.value = true
  try {
    connectionResult.value = await credentialApi.testConnection(activeEnv.value)
    if (connectionResult.value.connected) {
      ElMessage.success(`${activeEnv.value === 'demo' ? '模拟盘' : '实盘'}凭证连接成功`)
    } else {
      ElMessage.error(connectionResult.value.error || '连接失败')
    }
    // 如果测试的是当前全局环境，同步 store 状态
    if (activeEnv.value === connectionStore.environment) {
      connectionStore.connected = connectionResult.value.connected
      connectionStore.lastError = connectionResult.value.error || ''
    }
  } catch (err) {
    connectionResult.value = { connected: false, error: err.message }
    if (activeEnv.value === connectionStore.environment) {
      connectionStore.connected = false
      connectionStore.lastError = err.message
    }
    ElMessage.error(err.message)
  } finally {
    testing.value = false
  }
}

onMounted(async () => {
  await loadCredentials()
  activeEnv.value = connectionStore.environment
})

</script>

<style scoped>
.settings-page { padding-bottom: 40px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.connection-status :deep(.el-result) { padding: 20px 0; }
.tips p { margin: 6px 0; line-height: 1.6; }
</style>
