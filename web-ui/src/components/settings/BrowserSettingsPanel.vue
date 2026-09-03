<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import type { BrowserSettings } from '@/api/settings'

defineProps<{
  settings: BrowserSettings
  isReady: boolean
  isSaving: boolean
}>()
const { t } = useI18n()

const emit = defineEmits<{
  (e: 'save'): void
}>()
</script>

<template>
  <Card class="app-surface overflow-hidden border-none">
    <CardHeader>
      <CardTitle>{{ t('browser.title') }}</CardTitle>
      <CardDescription>{{ t('browser.description') }}</CardDescription>
    </CardHeader>
    <CardContent v-if="isReady" class="grid gap-6 lg:grid-cols-2">
      <section class="app-surface-subtle p-5">
        <div class="mb-5 flex items-center justify-between">
          <div>
            <h3 class="font-semibold text-slate-900">{{ t('browser.useSystemChrome') }}</h3>
            <p class="text-sm text-slate-500">{{ t('browser.useSystemChromeHint') }}</p>
          </div>
          <Switch v-model="settings.USE_SYSTEM_CHROME" />
        </div>
      </section>
    </CardContent>
    <CardContent v-else class="py-8 text-sm text-gray-500">
      {{ t('browser.loading') }}
    </CardContent>
    <CardFooter v-if="isReady" class="flex justify-end gap-2">
      <Button @click="emit('save')" :disabled="isSaving">{{ t('browser.save') }}</Button>
    </CardFooter>
  </Card>
</template>





