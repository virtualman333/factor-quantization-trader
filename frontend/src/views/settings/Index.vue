<template>
  <div class="settings-page">
    <el-row :gutter="20">
      <el-col :xs="24" :md="16">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>OKX API 凭证配置</span>
              <el-tag v-if="credential?.id" type="success">已配置</el-tag>
              <el-tag v-else type="info">未配置</el-tag>
            </div>
          </template>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="120px"
            label-position="right"
          >
            <el-form-item label="API Key" prop="api_key">
              <el-input
                v-model="form.api_key"
                placeholder="请输入 OKX API Key"
                show-password
                clearable
              />
            </el-form-item>

            <el-form-item label="Secret Key" prop="api_secret">
              <el-input
                v-model="form.api_secret"
                placeholder="请输入 OKX Secret Key"
                show-password
                clearable
              />
            </el-form-item>

            <el-form-item label="Passphrase" prop="passphrase">
              <el-input
                v-model="form.passphrase"
                placeholder="请输入 API Key 的 Passphrase"
                show-password
                clearable
              />
            </el-form-item>

            <el-form-item label="交易环境" prop="flag">
              <el-radio-group v-model="form.flag">
                <el-radio-button label="1">模拟盘 (Demo)</el-radio-button>
                <el-radio-button label="0">实盘 (Live)</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="启用状态">
              <el-switch
                v-model="form.is_active"
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
              <p>1. API 凭证保存在 MySQL 数据库中。</p>
              <p>2. 建议仅配置带读取/交易权限的 Key，避免使用提现权限。</p>
              <p>3. 首次配置建议先用模拟盘验证。</p>
              <p>4. 修改凭证后系统会自动重置 OKX 客户端。</p>
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

const formRef = ref(null)
const credential = ref(null)
const saving = ref(false)
const testing = ref(false)
const connectionResult = ref(null)

const form = reactive({
  api_key: '',
  api_secret: '',
  passphrase: '',
  flag: '1',
  is_active: true,
})

const rules = {
  api_key: [{ required: true, message: '请输入 API Key', trigger: 'blur' }],
  api_secret: [{ required: true, message: '请输入 Secret Key', trigger: 'blur' }],
  passphrase: [{ required: true, message: '请输入 Passphrase', trigger: 'blur' }],
  flag: [{ required: true, message: '请选择交易环境', trigger: 'change' }],
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

async function loadCredential() {
  try {
    credential.value = await credentialApi.active()
    Object.assign(form, {
      api_key: credential.value.api_key || '',
      api_secret: credential.value.api_secret || '',
      passphrase: credential.value.passphrase || '',
      flag: credential.value.flag || '1',
      is_active: credential.value.is_active !== false,
    })
  } catch (err) {
    if (err.message !== '未配置 OKX 凭证' && !err.message?.includes('404')) {
      ElMessage.warning(err.message)
    }
  }
}

async function onSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const payload = { ...form, name: 'default' }
    if (credential.value?.id) {
      credential.value = await credentialApi.update(credential.value.id, payload)
    } else {
      credential.value = await credentialApi.create(payload)
    }
    ElMessage.success('凭证保存成功')
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    saving.value = false
  }
}

async function onTestConnection() {
  testing.value = true
  try {
    connectionResult.value = await credentialApi.testConnection()
    if (connectionResult.value.connected) {
      ElMessage.success('OKX API 连接成功')
    } else {
      ElMessage.error(connectionResult.value.error || '连接失败')
    }
  } catch (err) {
    connectionResult.value = { connected: false, error: err.message }
    ElMessage.error(err.message)
  } finally {
    testing.value = false
  }
}

onMounted(loadCredential)
</script>

<style scoped>
.settings-page { padding-bottom: 40px; }
.card-header { display: flex; align-items: center; gap: 12px; }
.connection-status :deep(.el-result) { padding: 20px 0; }
.tips p { margin: 6px 0; line-height: 1.6; }
</style>
