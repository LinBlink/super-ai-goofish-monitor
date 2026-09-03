<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { RefreshCw, Download, Trash2 } from 'lucide-vue-next'

interface FileOption {
  value: string
  label: string
  taskName?: string
}

interface Props {
  files: string[]
  fileOptions?: FileOption[]
  selectedFile: string | null
  aiRecommendedOnly: boolean
  keywordRecommendedOnly: boolean
  includeHidden: boolean
  recentDays: number | null
  sortBy: 'crawl_time' | 'publish_time' | 'price' | 'keyword_hit_count' | 'smart'
  sortOrder: 'asc' | 'desc'
  isLoading: boolean
  isReady: boolean
}

const props = defineProps<Props>()
const { t } = useI18n()

const options = computed(() => {
  if (!props.isReady) return []
  if (props.fileOptions && props.fileOptions.length > 0) return props.fileOptions
  return props.files.map((file) => ({ value: file, label: file }))
})

const selectedLabel = computed(() => {
  if (!props.isReady) return t('results.filters.loadingTaskNames')
  if (options.value.length === 0) return t('results.filters.noResults')
  if (!props.selectedFile) return t('results.filters.chooseResult')
  const match = options.value.find((option) => option.value === props.selectedFile)
  return match ? match.label : t('results.filters.taskNameLabel', { task: t('common.unnamed') })
})

const isSelectDisabled = computed(() => !props.isReady || options.value.length === 0)

const emit = defineEmits<{
  (e: 'update:selectedFile', value: string): void
  (e: 'update:aiRecommendedOnly', value: boolean): void
  (e: 'update:keywordRecommendedOnly', value: boolean): void
  (e: 'update:includeHidden', value: boolean): void
  (e: 'update:recentDays', value: number | null): void
  (e: 'update:sortBy', value: 'crawl_time' | 'publish_time' | 'price' | 'keyword_hit_count' | 'smart'): void
  (e: 'update:sortOrder', value: 'asc' | 'desc'): void
  (e: 'refresh'): void
  (e: 'export'): void
  (e: 'delete'): void
}>()

const dateRanges = computed(() => [
  { value: null as number | null, label: t('results.filters.dateAll') },
  { value: 1, label: t('results.filters.date1d') },
  { value: 3, label: t('results.filters.date3d') },
  { value: 7, label: t('results.filters.date7d') },
])

function isDateActive(value: number | null) {
  return props.recentDays === value
}

function handleToggleAiRecommended(value: boolean) {
  emit('update:aiRecommendedOnly', value)
  if (value) emit('update:keywordRecommendedOnly', false)
}
function handleToggleKeywordRecommended(value: boolean) {
  emit('update:keywordRecommendedOnly', value)
  if (value) emit('update:aiRecommendedOnly', false)
}
</script>

<template>
  <section class="xy-card-flat space-y-3 p-3">
    <!-- �?1：任务选择 / 排序 / 顺序 -->
    <div class="grid gap-2 md:grid-cols-3">
      <div class="space-y-1">
        <Label class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          {{ t('results.title') }}
        </Label>
        <Select
          :model-value="props.selectedFile || undefined"
          @update:model-value="(value) => emit('update:selectedFile', value as string)"
        >
          <SelectTrigger class="h-9 w-full text-xs" :disabled="isSelectDisabled">
            <span :class="!props.isReady || !props.selectedFile ? 'text-muted-foreground' : ''">
              {{ selectedLabel }}
            </span>
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="option in options" :key="option.value" :value="option.value">
              {{ option.label }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div class="space-y-1">
        <Label class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          {{ t('results.filters.sortByLabel') }}
        </Label>
        <Select
          :model-value="props.sortBy"
          @update:model-value="(value) => emit('update:sortBy', value as any)"
        >
          <SelectTrigger class="h-9 w-full text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="crawl_time">{{ t('results.filters.sortByCrawlTime') }}</SelectItem>
            <SelectItem value="publish_time">{{ t('results.filters.sortByPublishTime') }}</SelectItem>
            <SelectItem value="price">{{ t('results.filters.sortByPrice') }}</SelectItem>
            <SelectItem value="keyword_hit_count">{{ t('results.filters.sortByKeywordHits') }}</SelectItem>
            <SelectItem value="smart">{{ t('results.filters.sortBySmart') }}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div v-if="props.sortBy !== 'smart'" class="space-y-1">
        <Label class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          {{ t('results.filters.asc') }} / {{ t('results.filters.desc') }}
        </Label>
        <Select
          :model-value="props.sortOrder"
          @update:model-value="(value) => emit('update:sortOrder', value as any)"
        >
          <SelectTrigger class="h-9 w-full text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="desc">{{ t('results.filters.desc') }}</SelectItem>
            <SelectItem value="asc">{{ t('results.filters.asc') }}</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>

    <!-- �?2：日期范围胶�?-->
    <div class="flex flex-wrap items-center gap-1.5">
      <Label class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        {{ t('results.filters.dateRange') }}
      </Label>
      <button
        v-for="range in dateRanges"
        :key="String(range.value)"
        type="button"
        class="rounded-full px-3 text-[12px] transition-colors"
        :class="
          isDateActive(range.value)
            ? 'text-slate-900'
            : 'bg-muted text-slate-600 hover:bg-muted/80'
        "
        :style="isDateActive(range.value) ? 'background-color: hsl(56 100% 52%)' : ''"
        @click="emit('update:recentDays', range.value)"
      >
        {{ range.label }}
      </button>
    </div>

    <!-- �?3：过滤器 / 操作 -->
    <div class="flex flex-col gap-2 lg:flex-row lg:flex-wrap lg:items-center">
      <div class="flex flex-wrap items-center gap-3">
        <label class="flex cursor-pointer items-center gap-1.5 text-[12px]">
          <Checkbox
            id="ai-recommended-only"
            :model-value="props.aiRecommendedOnly"
            @update:modelValue="(value) => handleToggleAiRecommended(value === true)"
          />
          <span>{{ t('results.filters.aiOnly') }}</span>
        </label>
        <label class="flex cursor-pointer items-center gap-1.5 text-[12px]">
          <Checkbox
            id="keyword-recommended-only"
            :model-value="props.keywordRecommendedOnly"
            @update:modelValue="(value) => handleToggleKeywordRecommended(value === true)"
          />
          <span>{{ t('results.filters.keywordOnly') }}</span>
        </label>
        <label class="flex cursor-pointer items-center gap-1.5 text-[12px]">
          <Checkbox
            id="include-hidden"
            :model-value="props.includeHidden"
            @update:modelValue="(value) => emit('update:includeHidden', value === true)"
          />
          <span>{{ t('results.filters.includeHidden') }}</span>
        </label>
      </div>

      <div class="flex flex-wrap items-center gap-1.5 lg:ml-auto">
        <button type="button" class="xy-btn-outline h-8 text-[12px]" :disabled="props.isLoading" @click="emit('refresh')">
          <RefreshCw class="h-3 w-3" />
          {{ t('common.refresh') }}
        </button>
        <button
          type="button"
          class="xy-btn-outline h-8 text-[12px]"
          :disabled="props.isLoading || !props.selectedFile"
          @click="emit('export')"
        >
          <Download class="h-3 w-3" />
          {{ t('results.filters.exportCsv') }}
        </button>
        <button
          type="button"
          class="xy-btn-danger h-8 text-[12px]"
          :disabled="props.isLoading || !props.selectedFile"
          @click="emit('delete')"
        >
          <Trash2 class="h-3 w-3" />
          {{ t('results.filters.deleteResult') }}
        </button>
      </div>
    </div>
  </section>
</template>







