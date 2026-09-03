<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { BellRing, Mail, Radio, ShieldCheck, Send, TestTube2, Trash2, Webhook } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toast'
import type { NotificationSettings, NotificationSettingsUpdate, NotificationTestResponse } from '@/api/settings'

type ChannelKey = 'ntfy' | 'bark' | 'gotify' | 'wecom' | 'telegram' | 'webhook' | 'email'

const props = defineProps<{
  settings: NotificationSettings
  isReady: boolean
  isSaving: boolean
  saveSettings: (payload: NotificationSettingsUpdate) => Promise<void>
  testSettings: (payload: { channel?: string; settings: NotificationSettingsUpdate }) => Promise<NotificationTestResponse>
}>()
const { t } = useI18n()

const initialValues = reactive<NotificationSettingsUpdate>({})
const form = reactive<NotificationSettingsUpdate>({})
const secretConfigured = reactive<Record<string, boolean>>({})
const clearedFields = reactive<Record<string, boolean>>({})
const testResults = reactive<Record<string, { success: boolean; message: string; label: string }>>({})
const testingChannel = ref<string | null>(null)
const WEBHOOK_HEADERS_EXAMPLE = '{"Authorization":"Bearer token"}'
const WEBHOOK_QUERY_EXAMPLE = '{"task":"{{title}}"}'
const WEBHOOK_BODY_EXAMPLE = '{"message":"{{content}}","price":"{{price}}"}'
const WEBHOOK_TEMPLATE_VARIABLES = '{{title}}, {{content}}, {{price}}, {{reason}}, {{desktop_link}}, {{mobile_link}}'
const mutableInitialValues = initialValues as Record<string, string | boolean | null | undefined>
const mutableForm = form as Record<string, string | boolean | null | undefined>
const mutableClearedFields = clearedFields as Record<string, boolean>

const secretFields = ['BARK_URL', 'GOTIFY_TOKEN', 'WX_BOT_URL', 'TELEGRAM_BOT_TOKEN', 'WEBHOOK_URL', 'WEBHOOK_HEADERS', 'SMTP_PASSWORD'] as const
const channelFields: Record<ChannelKey, (keyof NotificationSettingsUpdate)[]> = {
  ntfy: ['NTFY_TOPIC_URL', 'NTFY_ENABLED'],
  bark: ['BARK_URL', 'BARK_ENABLED'],
  gotify: ['GOTIFY_URL', 'GOTIFY_TOKEN', 'GOTIFY_ENABLED'],
  wecom: ['WX_BOT_URL', 'WX_BOT_ENABLED'],
  telegram: ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'TELEGRAM_API_BASE_URL', 'TELEGRAM_ENABLED'],
  webhook: ['WEBHOOK_URL', 'WEBHOOK_METHOD', 'WEBHOOK_CONTENT_TYPE', 'WEBHOOK_HEADERS', 'WEBHOOK_QUERY_PARAMETERS', 'WEBHOOK_BODY', 'WEBHOOK_ENABLED'],
  email: ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'SMTP_FROM_ADDRESS', 'SMTP_TO_ADDRESS', 'SMTP_USE_SSL', 'EMAIL_ENABLED'],
}
const channelEnabledField: Record<ChannelKey, keyof NotificationSettingsUpdate> = {
  ntfy: 'NTFY_ENABLED',
  bark: 'BARK_ENABLED',
  gotify: 'GOTIFY_ENABLED',
  wecom: 'WX_BOT_ENABLED',
  telegram: 'TELEGRAM_ENABLED',
  webhook: 'WEBHOOK_ENABLED',
  email: 'EMAIL_ENABLED',
}

function syncFromSettings(settings: NotificationSettings) {
  initialValues.NTFY_TOPIC_URL = settings.NTFY_TOPIC_URL ?? ''
  initialValues.GOTIFY_URL = settings.GOTIFY_URL ?? ''
  initialValues.TELEGRAM_CHAT_ID = settings.TELEGRAM_CHAT_ID ?? ''
  initialValues.TELEGRAM_API_BASE_URL = settings.TELEGRAM_API_BASE_URL ?? 'https://api.telegram.org'
  initialValues.WEBHOOK_METHOD = settings.WEBHOOK_METHOD ?? 'POST'
  initialValues.WEBHOOK_CONTENT_TYPE = settings.WEBHOOK_CONTENT_TYPE ?? 'JSON'
  initialValues.WEBHOOK_QUERY_PARAMETERS = settings.WEBHOOK_QUERY_PARAMETERS ?? ''
  initialValues.WEBHOOK_BODY = settings.WEBHOOK_BODY ?? ''
  initialValues.SMTP_HOST = settings.SMTP_HOST ?? ''
  initialValues.SMTP_PORT = settings.SMTP_PORT ?? 465
  initialValues.SMTP_USERNAME = settings.SMTP_USERNAME ?? ''
  initialValues.SMTP_FROM_ADDRESS = settings.SMTP_FROM_ADDRESS ?? ''
  initialValues.SMTP_TO_ADDRESS = settings.SMTP_TO_ADDRESS ?? ''
  initialValues.SMTP_USE_SSL = settings.SMTP_USE_SSL ?? true
  initialValues.PCURL_TO_MOBILE = settings.PCURL_TO_MOBILE ?? true
  initialValues.NTFY_ENABLED = settings.NTFY_ENABLED ?? true
  initialValues.GOTIFY_ENABLED = settings.GOTIFY_ENABLED ?? true
  initialValues.BARK_ENABLED = settings.BARK_ENABLED ?? true
  initialValues.WX_BOT_ENABLED = settings.WX_BOT_ENABLED ?? true
  initialValues.TELEGRAM_ENABLED = settings.TELEGRAM_ENABLED ?? true
  initialValues.WEBHOOK_ENABLED = settings.WEBHOOK_ENABLED ?? true
  initialValues.EMAIL_ENABLED = settings.EMAIL_ENABLED ?? true

  Object.assign(form, initialValues, {
    BARK_URL: '',
    GOTIFY_TOKEN: '',
    WX_BOT_URL: '',
    TELEGRAM_BOT_TOKEN: '',
    WEBHOOK_URL: '',
    WEBHOOK_HEADERS: '',
    SMTP_PASSWORD: '',
  })

  secretConfigured.BARK_URL = !!settings.BARK_URL_SET
  secretConfigured.GOTIFY_TOKEN = !!settings.GOTIFY_TOKEN_SET
  secretConfigured.WX_BOT_URL = !!settings.WX_BOT_URL_SET
  secretConfigured.TELEGRAM_BOT_TOKEN = !!settings.TELEGRAM_BOT_TOKEN_SET
  secretConfigured.WEBHOOK_URL = !!settings.WEBHOOK_URL_SET
  secretConfigured.WEBHOOK_HEADERS = !!settings.WEBHOOK_HEADERS_SET
  secretConfigured.SMTP_PASSWORD = !!settings.SMTP_PASSWORD_SET

  for (const field of Object.keys(clearedFields)) {
    clearedFields[field] = false
  }
}

watch(() => props.settings, syncFromSettings, { immediate: true, deep: true })

const activeChannels = computed(() => props.settings.CONFIGURED_CHANNELS ?? [])
const summaryText = computed(() => (
  activeChannels.value.length ? activeChannels.value.join(' / ') : t('notifyPanel.noActiveChannels')
))
const webhookHeadersPlaceholder = computed(() => `${t('notifyPanel.webhook.headersPlaceholder')}${WEBHOOK_HEADERS_EXAMPLE}`)
const webhookQueryPlaceholder = computed(() => `${t('notifyPanel.webhook.queryPlaceholder')}${WEBHOOK_QUERY_EXAMPLE}`)
const webhookBodyPlaceholder = computed(() => `${t('notifyPanel.webhook.bodyPlaceholder')}${WEBHOOK_BODY_EXAMPLE}`)
const webhookTemplateVariables = WEBHOOK_TEMPLATE_VARIABLES

function updateSecretField(field: keyof NotificationSettingsUpdate, value: string) {
  mutableForm[field as string] = value
  mutableClearedFields[field as string] = false
}

function updateField(field: keyof NotificationSettingsUpdate, value: string) {
  mutableForm[field as string] = value
  mutableClearedFields[field as string] = false
}

function clearChannel(channel: ChannelKey) {
  for (const field of channelFields[channel]) {
    const key = field as string
    mutableForm[key] = typeof mutableForm[key] === 'boolean' ? false : ''
    mutableClearedFields[key] = true
  }
  if (channel === 'webhook') {
    form.WEBHOOK_METHOD = 'POST'
    form.WEBHOOK_CONTENT_TYPE = 'JSON'
  }
  if (channel === 'email') {
    form.SMTP_PORT = 465
    form.SMTP_USE_SSL = true
  }
}

function buildPayload(): NotificationSettingsUpdate {
  return buildScopedPayload()
}

function buildScopedPayload(channel?: ChannelKey): NotificationSettingsUpdate {
  const payload: NotificationSettingsUpdate = {}
  const mutablePayload = payload as Record<string, string | boolean | null | undefined>
  const includedFields = channel
    ? new Set<string>([...channelFields[channel].map((field) => field as string), 'PCURL_TO_MOBILE'])
    : null
  const textFields: (keyof NotificationSettingsUpdate)[] = [
    'NTFY_TOPIC_URL', 'GOTIFY_URL', 'TELEGRAM_CHAT_ID', 'TELEGRAM_API_BASE_URL', 'WEBHOOK_METHOD',
    'WEBHOOK_CONTENT_TYPE', 'WEBHOOK_QUERY_PARAMETERS', 'WEBHOOK_BODY',
    'SMTP_HOST', 'SMTP_USERNAME', 'SMTP_FROM_ADDRESS', 'SMTP_TO_ADDRESS',
  ]

  for (const field of textFields) {
    if (includedFields && !includedFields.has(field as string)) {
      continue
    }
    if (mutableClearedFields[field as string]) {
      mutablePayload[field as string] = null
      continue
    }
    const current = String(mutableForm[field as string] ?? '').trim()
    const initial = String(mutableInitialValues[field as string] ?? '').trim()
    if (current !== initial) {
      mutablePayload[field as string] = current || null
    }
  }

  for (const field of secretFields) {
    if (includedFields && !includedFields.has(field as string)) {
      continue
    }
    if (mutableClearedFields[field as string]) {
      mutablePayload[field as string] = null
      continue
    }
    const value = String(mutableForm[field as string] ?? '').trim()
    if (value) {
      mutablePayload[field as string] = value
    }
  }

  if (!includedFields || includedFields.has('SMTP_PORT')) {
    if (mutableClearedFields.SMTP_PORT) {
      payload.SMTP_PORT = null
    } else {
      const currentPort = String(mutableForm.SMTP_PORT ?? '').trim()
      const initialPort = String(mutableInitialValues.SMTP_PORT ?? '').trim()
      if (currentPort !== initialPort) {
        payload.SMTP_PORT = currentPort ? Number(currentPort) : null
      }
    }
  }

  if ((!includedFields || includedFields.has('SMTP_USE_SSL')) && form.SMTP_USE_SSL !== initialValues.SMTP_USE_SSL) {
    payload.SMTP_USE_SSL = !!form.SMTP_USE_SSL
  }

  if ((!includedFields || includedFields.has('PCURL_TO_MOBILE')) && form.PCURL_TO_MOBILE !== initialValues.PCURL_TO_MOBILE) {
    payload.PCURL_TO_MOBILE = !!form.PCURL_TO_MOBILE
  }

  const enabledFields: (keyof NotificationSettingsUpdate)[] = [
    'NTFY_ENABLED', 'GOTIFY_ENABLED', 'BARK_ENABLED', 'WX_BOT_ENABLED', 'TELEGRAM_ENABLED', 'WEBHOOK_ENABLED', 'EMAIL_ENABLED',
  ]
  for (const field of enabledFields) {
    if (includedFields && !includedFields.has(field as string)) {
      continue
    }
    if (mutableForm[field as string] !== mutableInitialValues[field as string]) {
      mutablePayload[field as string] = !!mutableForm[field as string]
    }
  }
  return payload
}

function isChannelConfigured(channel: ChannelKey) {
  return activeChannels.value.includes(channel)
}

function isChannelToggleOn(channel: ChannelKey) {
  return !!mutableForm[channelEnabledField[channel] as string]
}

function setChannelToggle(channel: ChannelKey, value: boolean) {
  mutableForm[channelEnabledField[channel] as string] = value
}

async function handleSave() {
  await props.saveSettings(buildPayload())
}

async function handleTest(channel?: ChannelKey) {
  testingChannel.value = channel ?? 'all'
  try {
    const response = await props.testSettings({ channel, settings: buildScopedPayload(channel) })
    Object.assign(testResults, response.results)
    const entries = Object.values(response.results)
    if (entries.length === 0) {
      toast({ title: t('notifyPanel.testNoResult'), variant: 'destructive' })
    } else {
      for (const entry of entries) {
        toast({
          title: entry.success ? t('notifyPanel.testSuccessTitle', { channel: entry.label }) : t('notifyPanel.testFailedTitle', { channel: entry.label }),
          description: entry.message,
          variant: entry.success ? 'default' : 'destructive',
        })
      }
    }
  } catch {
    // 上层 testSettings 已经弹出过错误提示，这里避免重复提示
  } finally {
    testingChannel.value = null
  }
}

function resultClass(channel: ChannelKey) {
  return testResults[channel]?.success
    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
    : 'border-red-200 bg-red-50 text-red-700'
}

function resolveChannelBadge(channel: ChannelKey) {
  return isChannelConfigured(channel) ? t('common.active') : t('common.inactive')
}
</script>

<template>
  <div class="space-y-4">
    <Card class="app-surface overflow-hidden border-none">
      <CardHeader>
        <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div class="space-y-2">
            <div class="flex items-center gap-2 text-slate-800">
              <BellRing class="h-5 w-5 text-sky-600" />
              <CardTitle>{{ t('notifyPanel.title') }}</CardTitle>
            </div>
            <CardDescription>{{ t('notifyPanel.description') }}</CardDescription>
          </div>
          <div class="flex flex-wrap gap-2">
            <Badge variant="outline" class="border-sky-200 bg-sky-50 text-sky-700">{{ t('notifyPanel.enabledChannels', { channels: summaryText }) }}</Badge>
            <Badge variant="outline" class="border-slate-200 bg-white text-slate-600">{{ t('notifyPanel.supportedVariables') }}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent class="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
        <div class="app-surface-subtle p-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="text-sm font-semibold text-slate-900">{{ t('notifyPanel.globalBehavior') }}</p>
              <p class="text-sm text-slate-500">{{ t('notifyPanel.globalBehaviorDescription') }}</p>
            </div>
            <div class="flex items-center gap-3 rounded-full border border-slate-200 bg-slate-50 px-3 py-2">
              <Switch id="pcurl" :model-value="!!form.PCURL_TO_MOBILE" @update:model-value="(value) => form.PCURL_TO_MOBILE = !!value" />
              <Label for="pcurl" class="text-sm text-slate-700">{{ t('notifyPanel.preferMobileLink') }}</Label>
            </div>
          </div>
        </div>
        <div class="app-surface-subtle bg-slate-900/95 p-4 text-slate-100">
          <div class="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck class="h-4 w-4 text-emerald-300" />
            {{ t('notifyPanel.configurationNotes') }}
          </div>
          <p class="mt-2 text-sm leading-6 text-slate-300">{{ t('notifyPanel.configurationNotesDescription') }}</p>
        </div>
      </CardContent>
    </Card>

    <div v-if="!isReady" class="app-surface py-10 text-center text-sm text-slate-500">
      {{ t('notifyPanel.loading') }}
    </div>

    <div v-else class="grid gap-4">
      <Card class="app-surface-subtle overflow-hidden border-l-4 border-l-sky-500">
        <CardHeader>
          <div class="flex items-start justify-between gap-3">
            <div><CardTitle class="flex items-center gap-2"><Radio class="h-4 w-4 text-sky-600" /> Ntfy</CardTitle><CardDescription>{{ t('notifyPanel.ntfy.description') }}</CardDescription></div>
            <div class="flex shrink-0 items-center gap-2"><Switch id="ntfy-enabled" :model-value="isChannelToggleOn('ntfy')" @update:model-value="(v) => setChannelToggle('ntfy', !!v)" /><Label for="ntfy-enabled" class="text-xs text-slate-500">{{ t('notifyPanel.enableChannel') }}</Label></div>
          </div>
        </CardHeader>
        <CardContent><Label>Ntfy Topic URL</Label><Input :model-value="form.NTFY_TOPIC_URL ?? ''" placeholder="https://ntfy.sh/topic" @update:model-value="(value) => updateField('NTFY_TOPIC_URL', String(value))" /></CardContent>
        <CardFooter class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><Badge :variant="isChannelConfigured('ntfy') ? 'default' : 'outline'">{{ resolveChannelBadge('ntfy') }}</Badge><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('ntfy')"><TestTube2 class="h-4 w-4" />{{ t('notifyPanel.testThisChannel') }}</Button></CardFooter>
      </Card>

      <div class="grid gap-4 xl:grid-cols-2">
        <Card class="app-surface-subtle overflow-hidden border-l-4 border-l-amber-500">
          <CardHeader>
            <div class="flex items-start justify-between gap-3">
              <div><CardTitle>Bark</CardTitle><CardDescription>{{ t('notifyPanel.bark.description') }}</CardDescription></div>
              <div class="flex shrink-0 items-center gap-2"><Switch id="bark-enabled" :model-value="isChannelToggleOn('bark')" @update:model-value="(v) => setChannelToggle('bark', !!v)" /><Label for="bark-enabled" class="text-xs text-slate-500">{{ t('notifyPanel.enableChannel') }}</Label></div>
            </div>
          </CardHeader>
          <CardContent class="space-y-2"><Label>Bark URL</Label><Input :model-value="form.BARK_URL ?? ''" :placeholder="t('notifyPanel.secretPlaceholder')" @update:model-value="(value) => updateSecretField('BARK_URL', String(value))" /><p class="text-xs text-slate-500">{{ secretConfigured.BARK_URL ? t('notifyPanel.bark.configuredHint') : t('notifyPanel.notConfigured') }}</p></CardContent>
          <CardFooter class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><Badge :variant="isChannelConfigured('bark') ? 'default' : 'outline'">{{ resolveChannelBadge('bark') }}</Badge><div class="flex flex-wrap gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('bark')"><Trash2 class="h-4 w-4" />{{ t('notifyPanel.clear') }}</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('bark')"><TestTube2 class="h-4 w-4" />{{ t('notifyPanel.test') }}</Button></div></CardFooter>
        </Card>

        <Card class="app-surface-subtle overflow-hidden border-l-4 border-l-violet-500">
          <CardHeader>
            <div class="flex items-start justify-between gap-3">
              <div><CardTitle>Gotify</CardTitle><CardDescription>{{ t('notifyPanel.gotify.description') }}</CardDescription></div>
              <div class="flex shrink-0 items-center gap-2"><Switch id="gotify-enabled" :model-value="isChannelToggleOn('gotify')" @update:model-value="(v) => setChannelToggle('gotify', !!v)" /><Label for="gotify-enabled" class="text-xs text-slate-500">{{ t('notifyPanel.enableChannel') }}</Label></div>
            </div>
          </CardHeader>
          <CardContent class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>Gotify URL</Label><Input :model-value="form.GOTIFY_URL ?? ''" placeholder="https://gotify.example.com" @update:model-value="(value) => updateField('GOTIFY_URL', String(value))" /></div>
            <div class="grid gap-2"><Label>Gotify Token</Label><Input type="password" :model-value="form.GOTIFY_TOKEN ?? ''" :placeholder="t('notifyPanel.secretKeepPlaceholder')" @update:model-value="(value) => updateSecretField('GOTIFY_TOKEN', String(value))" /></div>
          </CardContent>
          <CardFooter class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><Badge :variant="isChannelConfigured('gotify') ? 'default' : 'outline'">{{ resolveChannelBadge('gotify') }}</Badge><div class="flex flex-wrap gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('gotify')"><Trash2 class="h-4 w-4" />{{ t('notifyPanel.clear') }}</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('gotify')"><TestTube2 class="h-4 w-4" />{{ t('notifyPanel.test') }}</Button></div></CardFooter>
        </Card>
      </div>

      <div class="grid gap-4 xl:grid-cols-2">
        <Card class="app-surface-subtle overflow-hidden border-l-4 border-l-emerald-500">
          <CardHeader>
            <div class="flex items-start justify-between gap-3">
              <div><CardTitle>{{ t('notifyPanel.wecom.title') }}</CardTitle><CardDescription>{{ t('notifyPanel.wecom.description') }}</CardDescription></div>
              <div class="flex shrink-0 items-center gap-2"><Switch id="wecom-enabled" :model-value="isChannelToggleOn('wecom')" @update:model-value="(v) => setChannelToggle('wecom', !!v)" /><Label for="wecom-enabled" class="text-xs text-slate-500">{{ t('notifyPanel.enableChannel') }}</Label></div>
            </div>
          </CardHeader>
          <CardContent class="space-y-2"><Label>{{ t('notifyPanel.wecom.urlLabel') }}</Label><Input :model-value="form.WX_BOT_URL ?? ''" :placeholder="t('notifyPanel.secretPlaceholder')" @update:model-value="(value) => updateSecretField('WX_BOT_URL', String(value))" /><p class="text-xs text-slate-500">{{ secretConfigured.WX_BOT_URL ? t('notifyPanel.wecom.configuredHint') : t('notifyPanel.notConfigured') }}</p></CardContent>
          <CardFooter class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><Badge :variant="isChannelConfigured('wecom') ? 'default' : 'outline'">{{ resolveChannelBadge('wecom') }}</Badge><div class="flex flex-wrap gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('wecom')"><Trash2 class="h-4 w-4" />{{ t('notifyPanel.clear') }}</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('wecom')"><TestTube2 class="h-4 w-4" />{{ t('notifyPanel.test') }}</Button></div></CardFooter>
        </Card>

        <Card class="app-surface-subtle overflow-hidden border-l-4 border-l-cyan-500">
          <CardHeader>
            <div class="flex items-start justify-between gap-3">
              <div><CardTitle>Telegram</CardTitle><CardDescription>{{ t('notifyPanel.telegram.description') }}</CardDescription></div>
              <div class="flex shrink-0 items-center gap-2"><Switch id="telegram-enabled" :model-value="isChannelToggleOn('telegram')" @update:model-value="(v) => setChannelToggle('telegram', !!v)" /><Label for="telegram-enabled" class="text-xs text-slate-500">{{ t('notifyPanel.enableChannel') }}</Label></div>
            </div>
          </CardHeader>
          <CardContent class="grid gap-4 md:grid-cols-3">
            <div class="grid gap-2"><Label>Bot Token</Label><Input type="password" :model-value="form.TELEGRAM_BOT_TOKEN ?? ''" :placeholder="t('notifyPanel.secretKeepPlaceholder')" @update:model-value="(value) => updateSecretField('TELEGRAM_BOT_TOKEN', String(value))" /></div>
            <div class="grid gap-2"><Label>Chat ID</Label><Input :model-value="form.TELEGRAM_CHAT_ID ?? ''" :placeholder="t('notifyPanel.telegram.chatIdPlaceholder')" @update:model-value="(value) => updateField('TELEGRAM_CHAT_ID', String(value))" /></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.telegram.apiBaseUrl') }}</Label><Input :model-value="form.TELEGRAM_API_BASE_URL ?? ''" placeholder="https://api.telegram.org" @update:model-value="(value) => updateField('TELEGRAM_API_BASE_URL', String(value))" /></div>
          </CardContent>
          <CardFooter class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><Badge :variant="isChannelConfigured('telegram') ? 'default' : 'outline'">{{ resolveChannelBadge('telegram') }}</Badge><div class="flex flex-wrap gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('telegram')"><Trash2 class="h-4 w-4" />{{ t('notifyPanel.clear') }}</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('telegram')"><TestTube2 class="h-4 w-4" />{{ t('notifyPanel.test') }}</Button></div></CardFooter>
        </Card>
      </div>

      <Card class="app-surface-subtle overflow-hidden border-l-4 border-l-indigo-500">
        <CardHeader>
          <div class="flex items-start justify-between gap-3">
            <div><CardTitle class="flex items-center gap-2"><Mail class="h-4 w-4 text-indigo-500" /> {{ t('notifyPanel.email.title') }}</CardTitle><CardDescription>{{ t('notifyPanel.email.description') }}</CardDescription></div>
            <div class="flex shrink-0 items-center gap-2"><Switch id="email-enabled" :model-value="isChannelToggleOn('email')" @update:model-value="(v) => setChannelToggle('email', !!v)" /><Label for="email-enabled" class="text-xs text-slate-500">{{ t('notifyPanel.enableChannel') }}</Label></div>
          </div>
        </CardHeader>
        <CardContent class="grid gap-4">
          <div class="grid gap-4 md:grid-cols-3">
            <div class="grid gap-2"><Label>{{ t('notifyPanel.email.hostLabel') }}</Label><Input :model-value="form.SMTP_HOST ?? ''" placeholder="smtp.example.com" @update:model-value="(value) => updateField('SMTP_HOST', String(value))" /></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.email.portLabel') }}</Label><Input type="number" :model-value="form.SMTP_PORT ?? 465" @update:model-value="(value) => updateField('SMTP_PORT', String(value))" /></div>
            <div class="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2"><Switch id="smtp-ssl" :model-value="!!form.SMTP_USE_SSL" @update:model-value="(value) => form.SMTP_USE_SSL = !!value" /><Label for="smtp-ssl" class="text-sm text-slate-700">{{ t('notifyPanel.email.useSslLabel') }}</Label></div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>{{ t('notifyPanel.email.usernameLabel') }}</Label><Input :model-value="form.SMTP_USERNAME ?? ''" placeholder="you@example.com" @update:model-value="(value) => updateField('SMTP_USERNAME', String(value))" /></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.email.passwordLabel') }}</Label><Input type="password" :model-value="form.SMTP_PASSWORD ?? ''" :placeholder="t('notifyPanel.secretKeepPlaceholder')" @update:model-value="(value) => updateSecretField('SMTP_PASSWORD', String(value))" /></div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>{{ t('notifyPanel.email.fromLabel') }}</Label><Input :model-value="form.SMTP_FROM_ADDRESS ?? ''" :placeholder="t('notifyPanel.email.fromPlaceholder')" @update:model-value="(value) => updateField('SMTP_FROM_ADDRESS', String(value))" /></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.email.toLabel') }}</Label><Input :model-value="form.SMTP_TO_ADDRESS ?? ''" :placeholder="t('notifyPanel.email.toPlaceholder')" @update:model-value="(value) => updateField('SMTP_TO_ADDRESS', String(value))" /></div>
          </div>
        </CardContent>
        <CardFooter class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><Badge :variant="isChannelConfigured('email') ? 'default' : 'outline'">{{ resolveChannelBadge('email') }}</Badge><div class="flex flex-wrap gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('email')"><Trash2 class="h-4 w-4" />{{ t('notifyPanel.clear') }}</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('email')"><TestTube2 class="h-4 w-4" />{{ t('notifyPanel.test') }}</Button></div></CardFooter>
      </Card>

      <Card class="app-surface-subtle overflow-hidden border-l-4 border-l-rose-500">
        <CardHeader>
          <div class="flex items-start justify-between gap-3">
            <div><CardTitle class="flex items-center gap-2"><Webhook class="h-4 w-4 text-rose-500" /> {{ t('notifyPanel.webhook.title') }}</CardTitle><CardDescription>{{ t('notifyPanel.webhook.description') }}</CardDescription></div>
            <div class="flex shrink-0 items-center gap-2"><Switch id="webhook-enabled" :model-value="isChannelToggleOn('webhook')" @update:model-value="(v) => setChannelToggle('webhook', !!v)" /><Label for="webhook-enabled" class="text-xs text-slate-500">{{ t('notifyPanel.enableChannel') }}</Label></div>
          </div>
        </CardHeader>
        <CardContent class="grid gap-4">
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.urlLabel') }}</Label><Input :model-value="form.WEBHOOK_URL ?? ''" :placeholder="t('notifyPanel.secretPlaceholder')" @update:model-value="(value) => updateSecretField('WEBHOOK_URL', String(value))" /></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.headersLabel') }}</Label><Textarea :model-value="form.WEBHOOK_HEADERS ?? ''" :placeholder="webhookHeadersPlaceholder" @update:model-value="(value) => updateSecretField('WEBHOOK_HEADERS', String(value))" /></div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.methodLabel') }}</Label><Select :model-value="form.WEBHOOK_METHOD || 'POST'" @update:model-value="(value) => updateField('WEBHOOK_METHOD', String(value))"><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="POST">POST</SelectItem><SelectItem value="GET">GET</SelectItem></SelectContent></Select></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.contentTypeLabel') }}</Label><Select :model-value="form.WEBHOOK_CONTENT_TYPE || 'JSON'" @update:model-value="(value) => updateField('WEBHOOK_CONTENT_TYPE', String(value))"><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="JSON">JSON</SelectItem><SelectItem value="FORM">FORM</SelectItem></SelectContent></Select></div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.queryLabel') }}</Label><Textarea :model-value="form.WEBHOOK_QUERY_PARAMETERS ?? ''" :placeholder="webhookQueryPlaceholder" @update:model-value="(value) => updateField('WEBHOOK_QUERY_PARAMETERS', String(value))" /></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.bodyLabel') }}</Label><Textarea :model-value="form.WEBHOOK_BODY ?? ''" :placeholder="webhookBodyPlaceholder" @update:model-value="(value) => updateField('WEBHOOK_BODY', String(value))" /></div>
          </div>
          <div class="rounded-2xl border border-dashed border-rose-200 bg-rose-50/70 px-4 py-3 text-sm text-rose-700">
            <p>{{ t('notifyPanel.webhook.variablesHelp') }}</p>
            <p class="mt-2 break-all font-mono text-xs text-rose-900">{{ webhookTemplateVariables }}</p>
          </div>
        </CardContent>
        <CardFooter class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><Badge :variant="isChannelConfigured('webhook') ? 'default' : 'outline'">{{ resolveChannelBadge('webhook') }}</Badge><div class="flex flex-wrap gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('webhook')"><Trash2 class="h-4 w-4" />{{ t('notifyPanel.clear') }}</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('webhook')"><TestTube2 class="h-4 w-4" />{{ t('notifyPanel.test') }}</Button></div></CardFooter>
      </Card>

      <div v-for="channel in ['ntfy', 'bark', 'gotify', 'wecom', 'telegram', 'webhook', 'email']" :key="channel">
        <div v-if="testResults[channel]" class="rounded-2xl border px-4 py-3 text-sm" :class="resultClass(channel as ChannelKey)">
          {{ testResults[channel].label }}：{{ testResults[channel].message }}
        </div>
      </div>
    </div>

    <div class="app-surface sticky bottom-0 z-10 flex flex-col gap-3 p-4 shadow-lg md:flex-row md:items-center md:justify-between">
      <div class="flex items-center gap-2 text-sm text-slate-600"><Send class="h-4 w-4 text-slate-400" />{{ t('notifyPanel.footerHint') }}</div>
      <div class="flex flex-col gap-2 sm:flex-row">
        <Button variant="outline" :disabled="props.isSaving" @click="handleTest()"><TestTube2 class="h-4 w-4" />{{ testingChannel === 'all' ? t('common.testing') : t('notifyPanel.testAll') }}</Button>
        <Button :disabled="props.isSaving" @click="handleSave"><Send class="h-4 w-4" />{{ t('notifyPanel.save') }}</Button>
      </div>
    </div>
  </div>
</template>





