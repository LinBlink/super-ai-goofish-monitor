<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useSettings } from '@/composables/useSettings'
import type { NotificationSettingsUpdate, NotificationTestResponse, AIModelConfig } from '@/api/settings'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/components/ui/toast'
import Badge from '@/components/ui/badge/Badge.vue'
import { getPromptContent, listPrompts, updatePrompt } from '@/api/prompts'
import NotificationSettingsPanel from '@/components/settings/NotificationSettingsPanel.vue'
import RotationSettingsPanel from '@/components/settings/RotationSettingsPanel.vue'
import BrowserSettingsPanel from '@/components/settings/BrowserSettingsPanel.vue'
import SchedulerSettingsPanel from '@/components/settings/SchedulerSettingsPanel.vue'
import GlobalBlacklistPanel from '@/components/settings/GlobalBlacklistPanel.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { Settings2 } from 'lucide-vue-next'
const { t } = useI18n()

const {
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
  refreshStatus,
  saveNotificationSettings,
  testNotification,
  saveAiSettings,
  saveRotationSettings,
  saveBrowserSettings,
  saveSchedulerSettings,
  saveGlobalBlacklist,
  testAiConnection
} = useSettings()

const activeTab = ref('ai')
const route = useRoute()
const validTabs = new Set(['notifications', 'ai', 'rotation', 'browser', 'scheduler', 'blacklist', 'status', 'prompts'])

const testingIndex = ref(-1)
const testMessages = ref<Record<number, { success: boolean; message: string }>>({})

const promptFiles = ref<string[]>([])
const selectedPrompt = ref<string | null>(null)
const promptContent = ref('')
const isPromptLoading = ref(false)
const isPromptSaving = ref(false)
const promptError = ref<string | null>(null)

function notifySuccess(title: string, description?: string) {
  toast({ title, description })
}

function notifyError(title: string, description?: string) {
  toast({ title, description, variant: 'destructive' })
}

async function handleSaveNotifications(payload: NotificationSettingsUpdate) {
  try {
    await saveNotificationSettings(payload)
    notifySuccess(t('settings.notifications.saved'))
  } catch (e) {
    notifyError(t('settings.notifications.saveFailed'), (e as Error).message)
  }
}

async function handleTestNotification(payload: {
  channel?: string
  settings: NotificationSettingsUpdate
}): Promise<NotificationTestResponse> {
  try {
    const result = await testNotification(payload)
    return result
  } catch (e) {
    notifyError(t('settings.notifications.testFailed'), (e as Error).message)
    throw e
  }
}

async function handleSaveAi() {
  try {
    await saveAiSettings()
    notifySuccess(t('settings.ai.saved'))
  } catch (e) {
    notifyError(t('settings.ai.saveFailed'), (e as Error).message)
  }
}

async function handleSaveRotation() {
  try {
    await saveRotationSettings()
    notifySuccess(t('settings.rotation.saved'))
  } catch (e) {
    notifyError(t('settings.rotation.saveFailed'), (e as Error).message)
  }
}

async function handleSaveBrowser() {
  try {
    await saveBrowserSettings()
    notifySuccess(t('settings.browser.saved'))
  } catch (e) {
    notifyError(t('settings.browser.saveFailed'), (e as Error).message)
  }
}

async function handleSaveScheduler(paused: boolean) {
  try {
    await saveSchedulerSettings(paused)
    notifySuccess(paused ? t('scheduler.paused') : t('scheduler.resumed'))
  } catch (e) {
    notifyError(t('scheduler.saveFailed'), (e as Error).message)
  }
}

async function handleSaveGlobalBlacklist(keywords: string[]) {
  try {
    await saveGlobalBlacklist(keywords)
    notifySuccess(t('settings.blacklist.saved'))
  } catch (e) {
    notifyError(t('settings.blacklist.saveFailed'), (e as Error).message)
  }
}

async function handleTestAi(model: AIModelConfig, idx: number) {
  testingIndex.value = idx
  testMessages.value[idx] = { success: false, message: t('settings.ai.testing') }
  try {
    const res = await testAiConnection(model)
    testMessages.value[idx] = { success: res.success, message: res.message }
    if (res.success) notifySuccess(t('settings.ai.testSuccess'), res.message)
    else notifyError(t('settings.ai.testFailed'), res.message)
  } catch (e) {
    testMessages.value[idx] = { success: false, message: (e as Error).message }
    notifyError(t('settings.ai.testFailed'), (e as Error).message)
  } finally {
    testingIndex.value = -1
  }
}

function addModel() {
  if (!aiSettings.value.models) aiSettings.value.models = []
  aiSettings.value.models.push({
    base_url: '',
    model_name: '',
    api_key: '',
    proxy_url: '',
    enable_response_format: true,
  })
}

function removeModel(idx: number) {
  if (aiSettings.value.models) aiSettings.value.models.splice(idx, 1)
}

async function fetchPrompts() {
  isPromptLoading.value = true
  promptError.value = null
  try {
    const files = await listPrompts()
    promptFiles.value = files

    if (selectedPrompt.value && files.includes(selectedPrompt.value)) {
      return
    }

    const lastSelected = localStorage.getItem('lastSelectedPrompt')
    if (lastSelected && files.includes(lastSelected)) {
      selectedPrompt.value = lastSelected
      return
    }

    selectedPrompt.value = files[0] || null
  } catch (e) {
    promptError.value = (e as Error).message || t('settings.prompts.promptListFailed')
  } finally {
    isPromptLoading.value = false
  }
}

async function handleSavePrompt() {
  if (!selectedPrompt.value) {
    notifyError(t('settings.prompts.selectPromptFile'))
    return
  }
  isPromptSaving.value = true
  try {
    const res = await updatePrompt(selectedPrompt.value, promptContent.value)
    notifySuccess(t('settings.prompts.saveSuccess'), res.message)
  } catch (e) {
    notifyError(t('settings.prompts.saveFailed'), (e as Error).message)
  } finally {
    isPromptSaving.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'prompts') {
    fetchPrompts()
  }
})

watch(
  () => route.query.tab,
  (tab) => {
    if (typeof tab === 'string' && validTabs.has(tab)) {
      activeTab.value = tab
    }
  },
  { immediate: true }
)

watch(selectedPrompt, async (value) => {
  if (!value) {
    promptContent.value = ''
    return
  }
  localStorage.setItem('lastSelectedPrompt', value)
  isPromptLoading.value = true
  promptError.value = null
  try {
    const data = await getPromptContent(value)
    promptContent.value = data.content
  } catch (e) {
    promptError.value = (e as Error).message || t('settings.prompts.promptContentFailed')
  } finally {
    isPromptLoading.value = false
  }
})
</script>

<template>
  <div>
    <PageHeader :title="t('settings.title')" :description="t('settings.description')" :icon="Settings2" />
    
    <div v-if="error" class="app-alert-error mb-4" role="alert">
      {{ error.message }}
    </div>

    <Tabs v-model="activeTab" class="w-full">
      <TabsList class="mb-4 flex w-full flex-nowrap justify-start gap-1 overflow-x-auto rounded-xl bg-slate-100 p-1">
        <TabsTrigger class="shrink-0" value="ai">{{ t('settings.tabs.ai') }}</TabsTrigger>
      <TabsTrigger class="shrink-0" value="rotation">{{ t('settings.tabs.rotation') }}</TabsTrigger>
      <TabsTrigger class="shrink-0" value="browser">{{ t('settings.tabs.browser') }}</TabsTrigger>
      <TabsTrigger class="shrink-0" value="scheduler">{{ t('scheduler.tab') }}</TabsTrigger>
      <TabsTrigger class="shrink-0" value="blacklist">{{ t('settings.tabs.blacklist') }}</TabsTrigger>
        <TabsTrigger class="shrink-0" value="notifications">{{ t('settings.tabs.notifications') }}</TabsTrigger>
        <TabsTrigger class="shrink-0" value="status">{{ t('settings.tabs.status') }}</TabsTrigger>
        <TabsTrigger class="shrink-0" value="prompts">{{ t('settings.tabs.prompts') }}</TabsTrigger>
      </TabsList>

      <!-- AI Tab -->
      <TabsContent value="ai">
        <Card>
          <CardHeader>
            <CardTitle>{{ t('settings.ai.title') }}</CardTitle>
            <CardDescription>{{ t('settings.ai.description') }}</CardDescription>
          </CardHeader>
          <CardContent v-if="isReady" class="space-y-4">
            <p class="text-xs text-gray-500">{{ t('settings.ai.orderHint') }}</p>
            <div
              v-for="(model, idx) in (aiSettings.models || [])"
              :key="idx"
              class="rounded-lg border p-3 space-y-3"
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium">{{ t('settings.ai.modelIndex', { n: idx + 1 }) }}</span>
                  <Badge v-if="idx === 0" variant="success">{{ t('settings.ai.primary') }}</Badge>
                  <Badge v-else variant="secondary">{{ t('settings.ai.fallback') }}</Badge>
                </div>
                <Button
                  v-if="(aiSettings.models || []).length > 1"
                  variant="ghost"
                  size="sm"
                  @click="removeModel(idx)"
                >{{ t('settings.ai.remove') }}</Button>
              </div>
              <div class="grid gap-2">
                <Label>API Base URL</Label>
                <Input v-model="model.base_url" placeholder="https://api.openai.com/v1" />
              </div>
              <div class="grid gap-2">
                <Label>API Key</Label>
                <Input v-model="model.api_key" type="password" :placeholder="t('settings.ai.keyPlaceholder')" />
              </div>
              <div class="grid gap-2">
                <Label>{{ t('settings.ai.modelName') }}</Label>
                <Input v-model="model.model_name" placeholder="gpt-3.5-turbo" />
              </div>
              <div class="grid gap-2">
                <Label>{{ t('settings.ai.proxy') }}</Label>
                <Input v-model="model.proxy_url" placeholder="http://127.0.0.1:7890" />
              </div>
              <div class="flex flex-wrap items-center gap-4">
                <label class="flex items-center gap-2 text-sm">
                  <input type="checkbox" v-model="model.enable_response_format" />
                  {{ t('settings.ai.enableResponseFormat') }}
                </label>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="isSaving || testingIndex === idx"
                  @click="handleTestAi(model, idx)"
                >{{ testingIndex === idx ? t('settings.ai.testing') : t('settings.ai.testConnection') }}</Button>
              </div>
              <p
                v-if="testMessages[idx]"
                :class="testMessages[idx].success ? 'text-xs text-green-600' : 'text-xs text-red-600'"
              >{{ testMessages[idx].message }}</p>
            </div>
            <Button variant="outline" @click="addModel">+ {{ t('settings.ai.addModel') }}</Button>

            <div class="flex items-center gap-2 pt-2">
              <input type="checkbox" v-model="aiSettings.SKIP_AI_ANALYSIS" id="skip-ai" />
              <Label for="skip-ai">{{ t('settings.ai.skipAnalysis') }}</Label>
            </div>
          </CardContent>
          <CardContent v-else class="py-8 text-sm text-gray-500">
            {{ t('settings.ai.loading') }}
          </CardContent>
          <CardFooter v-if="isReady" class="flex gap-2">
            <Button @click="handleSaveAi" :disabled="isSaving">{{ t('settings.ai.save') }}</Button>
          </CardFooter>
        </Card>
      </TabsContent>

      <!-- Rotation Tab -->
      <TabsContent value="rotation">
        <RotationSettingsPanel
          :settings="rotationSettings"
          :is-ready="isReady"
          :is-saving="isSaving"
          @save="handleSaveRotation"
        />
      </TabsContent>

      <!-- Browser Tab -->
      <TabsContent value="browser">
        <BrowserSettingsPanel
          :settings="browserSettings"
          :is-ready="isReady"
          :is-saving="isSaving"
          @save="handleSaveBrowser"
        />
      </TabsContent>

      <!-- Scheduler Tab -->
      <TabsContent value="scheduler">
        <SchedulerSettingsPanel
          :paused="schedulerSettings.paused"
          :is-ready="isReady"
          :is-saving="isSaving"
          @save="handleSaveScheduler"
        />
      </TabsContent>

      <!-- Global Blacklist Tab -->
      <TabsContent value="blacklist">
        <GlobalBlacklistPanel
          :keywords="globalBlacklistKeywords"
          :is-ready="isReady"
          :is-saving="isSaving"
          @save="handleSaveGlobalBlacklist"
        />
      </TabsContent>

      <!-- Notifications Tab -->
      <TabsContent value="notifications">
        <NotificationSettingsPanel
          :settings="notificationSettings"
          :is-ready="isReady"
          :is-saving="isSaving"
          :save-settings="handleSaveNotifications"
          :test-settings="handleTestNotification"
        />
      </TabsContent>

      <!-- Status Tab -->
      <TabsContent value="status">
        <Card>
          <CardHeader>
            <CardTitle>{{ t('settings.status.title') }}</CardTitle>
            <div class="flex justify-end">
                <Button variant="outline" size="sm" @click="refreshStatus" :disabled="isLoading">{{ t('settings.status.refresh') }}</Button>
            </div>
          </CardHeader>
          <CardContent>
            <div v-if="systemStatus" class="space-y-6">
              <!-- Scraper Process Status -->
              <div class="flex items-center justify-between border-b pb-4">
                <div>
                  <h3 class="font-medium">{{ t('settings.status.scraper') }}</h3>
                  <p class="text-sm text-gray-500">{{ t('settings.status.scraperDescription') }}</p>
                </div>
                <span :class="systemStatus.scraper_running ? 'text-green-600 font-bold bg-green-50 px-3 py-1 rounded-full' : 'text-gray-500 bg-gray-100 px-3 py-1 rounded-full'">
                  {{ systemStatus.scraper_running ? t('common.running') : t('common.idle') }}
                </span>
              </div>

              <!-- Env Config Status -->
              <div>
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="font-medium">{{ t('settings.status.env') }}</h3>
                        <p class="text-sm text-gray-500">{{ t('settings.status.envDescription') }}</p>
                    </div>
                    <span :class="systemStatus.env_file.exists ? 'text-green-600 font-bold bg-green-50 px-3 py-1 rounded-full' : 'text-red-600 font-bold bg-red-50 px-3 py-1 rounded-full'">
                        {{ systemStatus.env_file.exists ? t('settings.status.loaded') : t('settings.status.missing') }}
                    </span>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="p-3 border rounded-lg" :class="systemStatus.env_file.openai_api_key_set ? 'bg-green-50 border-green-200' : 'bg-yellow-50 border-yellow-200'">
                        <div class="flex justify-between items-center">
                            <span class="font-medium text-sm">OpenAI API Key</span>
                            <span class="text-xs font-bold" :class="systemStatus.env_file.openai_api_key_set ? 'text-green-700' : 'text-yellow-700'">
                                {{ systemStatus.env_file.openai_api_key_set ? t('common.active') : t('common.inactive') }}
                            </span>
                        </div>
                    </div>
                    
                    <div class="p-3 border rounded-lg" :class="systemStatus.configured_notification_channels?.length ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'">
                         <div class="flex justify-between items-center">
                            <span class="font-medium text-sm">{{ t('settings.status.channels') }}</span>
                             <span class="text-xs font-bold" :class="systemStatus.configured_notification_channels?.length ? 'text-green-700' : 'text-gray-500'">
                                {{ systemStatus.configured_notification_channels?.length ? t('common.active') : t('common.inactive') }}
                            </span>
                        </div>
                         <div class="text-xs text-gray-500 mt-1">
                            {{ systemStatus.configured_notification_channels?.join(', ') || t('settings.status.none') }}
                        </div>
                    </div>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-8 text-gray-500">
                {{ t('settings.status.fetching') }}
            </div>
          </CardContent>
        </Card>
      </TabsContent>

      <!-- Prompt Tab -->
      <TabsContent value="prompts">
        <Card>
          <CardHeader>
            <CardTitle>{{ t('settings.prompts.title') }}</CardTitle>
            <CardDescription>{{ t('settings.prompts.description') }}</CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <div v-if="promptError" class="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded">
              {{ promptError }}
            </div>

            <div class="grid gap-2">
              <Label>{{ t('settings.prompts.selectFile') }}</Label>
              <Select
                :model-value="selectedPrompt || undefined"
                @update:model-value="(value) => selectedPrompt = value as string"
              >
                <SelectTrigger>
                  <SelectValue :placeholder="t('settings.prompts.placeholder')" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="file in promptFiles" :key="file" :value="file">
                    {{ file }}
                  </SelectItem>
                </SelectContent>
              </Select>
              <p v-if="!promptFiles.length && !isPromptLoading" class="text-sm text-gray-500">
                {{ t('settings.prompts.none') }}
              </p>
            </div>

            <div class="grid gap-2">
              <Label>{{ t('settings.prompts.content') }}</Label>
              <Textarea
                v-model="promptContent"
                class="min-h-[240px]"
                :disabled="!selectedPrompt || isPromptLoading"
                :placeholder="t('settings.prompts.contentPlaceholder')"
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button :disabled="isPromptSaving || !selectedPrompt" @click="handleSavePrompt">
              {{ isPromptSaving ? t('common.saving') : t('settings.prompts.save') }}
            </Button>
          </CardFooter>
        </Card>
      </TabsContent>
    </Tabs>
  </div>
</template>
