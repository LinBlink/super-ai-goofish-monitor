<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'

const props = defineProps<{
  paused: boolean
  isReady: boolean
  isSaving: boolean
}>()
const { t } = useI18n()

const localPaused = ref(props.paused)
watch(
  () => props.paused,
  (value) => {
    localPaused.value = value
  }
)

const emit = defineEmits<{
  (e: 'save', paused: boolean): void
}>()
</script>

<template>
  <Card class="app-surface overflow-hidden border-none">
    <CardHeader>
      <CardTitle>{{ t('scheduler.title') }}</CardTitle>
      <CardDescription>{{ t('scheduler.description') }}</CardDescription>
    </CardHeader>
    <CardContent v-if="isReady" class="grid gap-6 lg:grid-cols-2">
      <section class="app-surface-subtle p-5">
        <div class="flex items-center justify-between gap-4">
          <div>
            <h3 class="font-semibold text-slate-900">{{ t('scheduler.pauseTriggers') }}</h3>
            <p class="mt-1 text-sm text-slate-500">{{ t('scheduler.pauseTriggersHint') }}</p>
          </div>
          <Switch
            :model-value="localPaused"
            :disabled="isSaving"
            @update:model-value="(value) => emit('save', Boolean(value))"
          />
        </div>
        <p class="mt-3 text-xs font-medium" :class="localPaused ? 'text-amber-600' : 'text-green-600'">
          {{ localPaused ? t('scheduler.currentPaused') : t('scheduler.currentActive') }}
        </p>
      </section>
    </CardContent>
    <CardContent v-else class="py-8 text-sm text-gray-500">
      {{ t('scheduler.loading') }}
    </CardContent>
  </Card>
</template>
