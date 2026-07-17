import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { credentialApi, systemConfigApi } from '@/api/credential.js'
import { ElMessage } from 'element-plus'

export const useConnectionStore = defineStore('connection', () => {
  const environment = ref('demo')
  const connected = ref(false)
  const loading = ref(false)
  const lastError = ref('')
  const lastCheckTime = ref(null)

  const envLabel = computed(() => (environment.value === 'live' ? '实盘' : '模拟盘'))
  const statusType = computed(() => (connected.value ? 'success' : 'danger'))
  const statusText = computed(() => (connected.value ? '已连接' : '未连接'))

  async function loadConfig() {
    try {
      const config = await systemConfigApi.get()
      environment.value = config.active_environment || 'demo'
    } catch (err) {
      console.warn('加载系统配置失败', err.message)
    }
  }

  async function switchEnv(env) {
    if (env === environment.value) return
    try {
      loading.value = true
      const res = await credentialApi.switchEnv(env)
      environment.value = env
      lastError.value = ''
      ElMessage.success(`已切换至${env === 'live' ? '实盘' : '模拟盘'}`)
      await checkConnection()
      return res
    } catch (err) {
      ElMessage.error(err.message)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function checkConnection() {
    try {
      loading.value = true
      const res = await credentialApi.testConnection()
      connected.value = res.connected === true
      lastError.value = res.connected ? '' : res.error || '连接失败'
      lastCheckTime.value = new Date()
      return res
    } catch (err) {
      connected.value = false
      lastError.value = err.message || '连接失败'
      lastCheckTime.value = new Date()
      throw err
    } finally {
      loading.value = false
    }
  }

  async function init() {
    await loadConfig()
    await checkConnection().catch(() => {})
  }

  return {
    environment,
    connected,
    loading,
    lastError,
    lastCheckTime,
    envLabel,
    statusType,
    statusText,
    loadConfig,
    switchEnv,
    checkConnection,
    init,
  }
})
