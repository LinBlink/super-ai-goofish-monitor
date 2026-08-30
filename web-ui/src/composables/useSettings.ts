import { ref, onMounted } from 'vue'
import * as settingsApi from '@/api/settings'
import type {
  NotificationSettings,
  NotificationSettingsUpdate,
  NotificationTestResponse,
  AiSettings,
  AIModelConfig,
  RotationSettings,
  BrowserSettings,
  SchedulerSettings,
  SystemStatus
} from '@/api/settings'

export function useSettings() {
  const notificationSettings = ref<NotificationSettings>({})
  const aiSettings = ref<AiSettings>({ models: [] })
  const rotationSettings = ref<RotationSettings>({})
  const browserSettings = ref<BrowserSettings>({})
  const schedulerSettings = ref<SchedulerSettings>({ paused: false, scheduler_running: false })
  const systemStatus = ref<SystemStatus | null>(null)
  const globalBlacklistKeywords = ref<string[]>([])
  const isReady = ref(false)
  
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<Error | null>(null)

  async function fetchAll() {
    isLoading.value = true
    error.value = null
    try {
      const [notif, ai, rotation, browser, status, blacklist, scheduler] = await Promise.all([
        settingsApi.getNotificationSettings(),
        settingsApi.getAiSettings(),
        settingsApi.getRotationSettings(),
        settingsApi.getBrowserSettings(),
        settingsApi.getSystemStatus(),
        settingsApi.getGlobalBlacklist(),
        settingsApi.getSchedulerSettings()
      ])
      notificationSettings.value = notif
      aiSettings.value = {
        models: (ai.models || []).map((m) => ({
          ...m,
          api_key: m.api_key ?? '',
          proxy_url: m.proxy_url ?? '',
        })),
        SKIP_AI_ANALYSIS: ai.SKIP_AI_ANALYSIS,
      }
      rotationSettings.value = rotation
      browserSettings.value = browser
      systemStatus.value = status
      globalBlacklistKeywords.value = blacklist.keywords
      schedulerSettings.value = scheduler
    } catch (e) {
      if (e instanceof Error) error.value = e
    } finally {
      isLoading.value = false
      isReady.value = true
    }
  }

  async function refreshStatus() {
    isLoading.value = true
    error.value = null
    try {
      systemStatus.value = await settingsApi.getSystemStatus()
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function saveNotificationSettings(payload: NotificationSettingsUpdate) {
    isSaving.value = true
    try {
      await settingsApi.updateNotificationSettings(payload)
      const [notif, status] = await Promise.all([
        settingsApi.getNotificationSettings(),
        settingsApi.getSystemStatus()
      ])
      notificationSettings.value = notif
      systemStatus.value = status
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function testNotification(payload: {
    channel?: string
    settings: NotificationSettingsUpdate
  }): Promise<NotificationTestResponse> {
    isSaving.value = true
    try {
      return await settingsApi.testNotificationSettings(payload)
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function saveAiSettings() {
    isSaving.value = true
    try {
      const models = (aiSettings.value.models || []).map((m) => ({
        ...m,
        api_key: (m.api_key || '').trim() ? (m.api_key || '').trim() : undefined,
        base_url: (m.base_url || '').trim(),
        model_name: (m.model_name || '').trim(),
        proxy_url: m.proxy_url ? m.proxy_url.trim() : undefined,
        enable_response_format: m.enable_response_format !== false,
      }))
      const payload: AiSettings = {
        models,
        SKIP_AI_ANALYSIS: aiSettings.value.SKIP_AI_ANALYSIS,
      }
      await settingsApi.updateAiSettings(payload)
      // 保存后清空本地明文密钥，避免误留存
      aiSettings.value.models = models.map((m) => ({ ...m, api_key: '' }))
      systemStatus.value = await settingsApi.getSystemStatus()
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function saveRotationSettings() {
    isSaving.value = true
    try {
      await settingsApi.updateRotationSettings(rotationSettings.value)
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function saveBrowserSettings() {
    isSaving.value = true
    try {
      await settingsApi.updateBrowserSettings(browserSettings.value)
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function saveSchedulerSettings(paused: boolean) {
    isSaving.value = true
    try {
      const result = await settingsApi.updateSchedulerSettings(paused)
      schedulerSettings.value = { ...schedulerSettings.value, paused: result.paused }
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function saveGlobalBlacklist(keywords: string[]) {
    isSaving.value = true
    try {
      const result = await settingsApi.updateGlobalBlacklist(keywords)
      globalBlacklistKeywords.value = result.keywords
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function testAiConnection(model: AIModelConfig) {
    isSaving.value = true
    try {
      const payload: AIModelConfig = {
        ...model,
        api_key: (model.api_key || '').trim() ? (model.api_key || '').trim() : undefined,
        base_url: (model.base_url || '').trim(),
        model_name: (model.model_name || '').trim(),
        proxy_url: model.proxy_url ? model.proxy_url.trim() : undefined,
      }
      const res = await settingsApi.testAiSettings(payload)
      return res
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  onMounted(fetchAll)

  return {
    notificationSettings,
    aiSettings,
    rotationSettings,
    browserSettings,
    schedulerSettings,
    systemStatus,
    globalBlacklistKeywords,
    isLoading,
    isSaving,
    isReady,
    error,
    fetchAll,
    saveNotificationSettings,
    testNotification,
    saveAiSettings,
    saveRotationSettings,
    saveBrowserSettings,
    saveSchedulerSettings,
    saveGlobalBlacklist,
    testAiConnection,
    refreshStatus,
  }
}
