<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

const props = defineProps<{
  keywords: string[]
  isReady: boolean
  isSaving: boolean
}>()
const { t } = useI18n()

const emit = defineEmits<{
  (e: 'save', keywords: string[]): void
}>()

const draft = ref('')

watch(
  () => props.keywords,
  (value) => {
    draft.value = (value || []).join('\n')
  },
  { immediate: true }
)

function parseKeywords(input: string): string[] {
  return input
    .split(/[\n,，]+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

function handleSave() {
  emit('save', parseKeywords(draft.value))
}
</script>

<template>
  <Card class="app-surface overflow-hidden border-none">
    <CardHeader>
      <CardTitle>{{ t('settings.blacklist.title') }}</CardTitle>
      <CardDescription>{{ t('settings.blacklist.description') }}</CardDescription>
    </CardHeader>
    <CardContent v-if="isReady" class="grid gap-2">
      <Label>{{ t('settings.blacklist.rulesLabel') }}</Label>
      <Textarea
        v-model="draft"
        class="min-h-[200px] font-mono text-sm"
        :placeholder="t('settings.blacklist.rulesPlaceholder')"
      />
      <p class="text-xs text-gray-500">{{ t('settings.blacklist.rulesHint') }}</p>
    </CardContent>
    <CardContent v-else class="py-8 text-sm text-gray-500">
      {{ t('settings.blacklist.loading') }}
    </CardContent>
    <CardFooter v-if="isReady">
      <Button :disabled="isSaving" @click="handleSave">
        {{ isSaving ? t('common.saving') : t('settings.blacklist.save') }}
      </Button>
    </CardFooter>
  </Card>
</template>





