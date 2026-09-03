<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Bell, Layers, Sparkles } from 'lucide-vue-next'
import type { TaskBatchUpdate } from '@/types/task.d.ts'

const UNCHANGED = '__unchanged__'

interface Props {
  open: boolean
  count: number
  selectedNames?: string[]
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'submit', updates: TaskBatchUpdate): void
}>()

const { t } = useI18n()

const notifyEnabled = ref<string>(UNCHANGED)
const maxPages = ref<string>(UNCHANGED)
const newPublishOption = ref<string>(UNCHANGED)
const submitting = ref(false)

watch(
  () => props.open,
  (val) => {
    if (val) {
      notifyEnabled.value = UNCHANGED
      maxPages.value = UNCHANGED
      newPublishOption.value = UNCHANGED
      submitting.value = false
    }
  },
)

const publishOptions = [
  { value: '', label: 'tasks.form.publishOptions.none' },
  { value: '最新', label: 'tasks.form.publishOptions.latest' },
  { value: '1天内', label: 'tasks.form.publishOptions.oneDay' },
  { value: '3天内', label: 'tasks.form.publishOptions.threeDays' },
  { value: '7天内', label: 'tasks.form.publishOptions.sevenDays' },
  { value: '14天内', label: 'tasks.form.publishOptions.fourteenDays' },
] as const

const notifyEnabledEffective = computed(() =>
  notifyEnabled.value === UNCHANGED ? null : notifyEnabled.value === 'true',
)

const maxPagesEffective = computed(() => {
  if (maxPages.value === UNCHANGED) return null
  const n = Number(maxPages.value)
  return Number.isFinite(n) && n >= 1 ? n : null
})

const newPublishEffective = computed(() => {
  if (newPublishOption.value === UNCHANGED) return null
  return newPublishOption.value
})

const hasAnyChange = computed(
  () =>
    notifyEnabledEffective.value !== null ||
    maxPagesEffective.value !== null ||
    newPublishEffective.value !== null,
)

const maxPagesError = computed(() => {
  if (maxPages.value === UNCHANGED) return null
  const n = Number(maxPages.value)
  if (!Number.isFinite(n) || n < 1 || n > 50) return t('tasks.batchEdit.maxPagesError')
  return null
})

function onClose() {
  if (submitting.value) return
  emit('update:open', false)
}

async function onSubmit() {
  if (!hasAnyChange.value || maxPagesError.value) return
  const updates: TaskBatchUpdate = {}
  if (notifyEnabledEffective.value !== null) {
    updates.notify_enabled = notifyEnabledEffective.value
  }
  if (maxPagesEffective.value !== null) {
    updates.max_pages = maxPagesEffective.value
  }
  if (newPublishEffective.value !== null) {
    updates.new_publish_option = newPublishEffective.value || null
  }
  submitting.value = true
  try {
    emit('submit', updates)
  } finally {
    submitting.value = false
  }
}

const subtitle = computed(() => {
  if (!props.selectedNames || props.selectedNames.length === 0) {
    return t('tasks.batchEdit.subtitle', { count: props.count })
  }
  if (props.selectedNames.length <= 3) {
    return t('tasks.batchEdit.subtitleWithNames', {
      count: props.count,
      names: props.selectedNames.join(','),
    })
  }
  return t('tasks.batchEdit.subtitleWithNamesTruncated', {
    count: props.count,
    names: props.selectedNames.slice(0, 3).join(','),
    extra: props.selectedNames.length - 3,
  })
})
</script>

<template>
  <Dialog :open="open" @update:open="(v) => emit('update:open', v)">
    <DialogContent class="sm:max-w-[520px]">
      <DialogHeader>
        <DialogTitle>{{ t('tasks.batchEdit.title') }}</DialogTitle>
        <DialogDescription>{{ subtitle }}</DialogDescription>
      </DialogHeader>

      <div class="space-y-4 py-2">
        <!-- 通知推�?-->
        <div class="rounded-lg border border-slate-200/70 bg-white/60 p-3">
          <div class="flex items-center justify-between gap-3">
            <div class="flex items-start gap-2">
              <Bell class="mt-0.5 h-4 w-4 text-slate-500" />
              <div>
                <Label class="text-sm font-semibold text-slate-700">
                  {{ t('tasks.form.notifyEnabled') }}
                </Label>
                <p class="text-[11px] text-slate-400">
                  {{ t('tasks.batchEdit.notifyHint') }}
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <Select v-model="notifyEnabled">
                <SelectTrigger class="h-8 w-[140] text-xs">
                  <SelectValue :placeholder="t('tasks.batchEdit.unchanged')" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__unchanged__">{{ t('tasks.batchEdit.unchanged') }}</SelectItem>
                  <SelectItem value="true">{{ t('tasks.batchEdit.enable') }}</SelectItem>
                  <SelectItem value="false">{{ t('tasks.batchEdit.disable') }}</SelectItem>
                </SelectContent>
              </Select>
              <Switch
                v-if="notifyEnabled !== '__unchanged__'"
                :model-value="notifyEnabled === 'true'"
                :aria-label="t('tasks.form.notifyEnabled')"
                @update:model-value="(val) => (notifyEnabled = val ? 'true' : 'false')"
              />
            </div>
          </div>
        </div>

        <!-- 搜索页数 -->
        <div class="rounded-lg border border-slate-200/70 bg-white/60 p-3">
          <div class="flex items-center justify-between gap-3">
            <div class="flex items-start gap-2">
              <Layers class="mt-0.5 h-4 w-4 text-slate-500" />
              <div>
                <Label class="text-sm font-semibold text-slate-700">
                  {{ t('tasks.form.maxPages') }}
                </Label>
                <p class="text-[11px] text-slate-400">
                  {{ t('tasks.batchEdit.maxPagesHint') }}
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span
                v-if="maxPages !== '__unchanged__'"
                class="text-[11px] font-medium"
                :class="maxPagesError ? 'text-rose-500' : 'text-slate-500'"
              >
                {{ maxPagesError || t('tasks.batchEdit.pagesUnit', { n: maxPagesEffective }) }}
              </span>
              <Input
                v-model="maxPages"
                type="number"
                min="1"
                max="50"
                :placeholder="t('tasks.batchEdit.unchanged')"
                :class="['h-8 w-24 text-sm', maxPagesError ? 'border-rose-300 focus-visible:ring-rose-200' : '']"
              />
            </div>
          </div>
        </div>

        <!-- 新发布范�?-->
        <div class="rounded-lg border border-slate-200/70 bg-white/60 p-3">
          <div class="flex items-center justify-between gap-3">
            <div class="flex items-start gap-2">
              <Sparkles class="mt-0.5 h-4 w-4 text-slate-500" />
              <div>
                <Label class="text-sm font-semibold text-slate-700">
                  {{ t('tasks.form.newPublish') }}
                </Label>
                <p class="text-[11px] text-slate-400">
                  {{ t('tasks.batchEdit.newPublishHint') }}
                </p>
              </div>
            </div>
            <Select v-model="newPublishOption">
              <SelectTrigger class="h-8 w-[160] text-xs">
                <SelectValue :placeholder="t('tasks.batchEdit.unchanged')" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__unchanged__">{{ t('tasks.batchEdit.unchanged') }}</SelectItem>
                <SelectItem v-for="opt in publishOptions" :key="opt.value || 'none'" :value="opt.value || '__none__'">
                  {{ t(opt.label) }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" :disabled="submitting" @click="onClose">
          {{ t('common.cancel') }}
        </Button>
        <Button :disabled="!hasAnyChange || !!maxPagesError || submitting" @click="onSubmit">
          {{ submitting ? t('common.saving') : t('tasks.batchEdit.submit', { count }) }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>




