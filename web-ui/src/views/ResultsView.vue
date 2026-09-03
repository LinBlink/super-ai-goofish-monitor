<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useResults } from '@/composables/useResults'
import ResultsFilterBar from '@/components/results/ResultsFilterBar.vue'
import ResultsGrid from '@/components/results/ResultsGrid.vue'
import ResultsInsightsPanel from '@/components/results/ResultsInsightsPanel.vue'
import { toast } from '@/components/ui/toast'
import { Inbox } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const { t } = useI18n()

const {
  files,
  selectedFile,
  results,
  insights,
  filters,
  isLoading,
  error,
  refreshResults,
  exportSelectedResults,
  deleteSelectedFile,
  toggleItemBlock,
  fileOptions,
  isFileOptionsReady,
} = useResults()

const isDeleteDialogOpen = ref(false)

const selectedTaskLabel = computed(() => {
  if (!selectedFile.value || fileOptions.value.length === 0) return null
  const match = fileOptions.value.find((option) => option.value === selectedFile.value)
  if (!match) return null
  return match.taskName || null
})

const deleteConfirmText = computed(() =>
  selectedTaskLabel.value
    ? t('results.filters.deleteDialogWithTask', { task: selectedTaskLabel.value })
    : t('results.filters.deleteDialogFallback'),
)

function openDeleteDialog() {
  if (!selectedFile.value) {
    toast({ title: t('results.filters.noResultToDelete'), variant: 'destructive' })
    return
  }
  isDeleteDialogOpen.value = true
}

function handleExportResults() {
  if (!selectedFile.value) {
    toast({ title: t('results.filters.noResultToExport'), variant: 'destructive' })
    return
  }
  exportSelectedResults()
}

async function handleDeleteResults() {
  if (!selectedFile.value) return
  try {
    await deleteSelectedFile(selectedFile.value)
    toast({ title: t('results.filters.resultDeleted') })
  } catch (e) {
    toast({
      title: t('results.filters.deleteFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isDeleteDialogOpen.value = false
  }
}
</script>

<template>
  <div class="space-y-3">
    <header class="xy-card-flat flex items-center gap-2 p-2.5">
      <span
        class="flex h-7 w-7 items-center justify-center rounded-xl"
        style="background-color: hsl(56 100% 52%)"
      >
        <Inbox class="h-4 w-4 text-slate-900" />
      </span>
      <h1 class="truncate text-base font-black text-foreground">{{ t('results.title') }}</h1>
      <p class="hidden text-[12px] text-slate-500 sm:block">{{ t('results.description') }}</p>
    </header>

    <div v-if="error" class="xy-card-flat border-rose-200 bg-rose-50/40 p-3 text-sm text-rose-700">
      {{ error.message }}
    </div>

    <ResultsFilterBar
      :files="files"
      :file-options="fileOptions"
      :is-ready="isFileOptionsReady"
      v-model:selectedFile="selectedFile"
      v-model:aiRecommendedOnly="filters.ai_recommended_only"
      v-model:keywordRecommendedOnly="filters.keyword_recommended_only"
      v-model:includeHidden="filters.include_hidden"
      v-model:recentDays="filters.recent_days"
      v-model:sortBy="filters.sort_by"
      v-model:sortOrder="filters.sort_order"
      :is-loading="isLoading"
      @refresh="refreshResults"
      @export="handleExportResults"
      @delete="openDeleteDialog"
    />

    <ResultsInsightsPanel :insights="insights" :selected-task-label="selectedTaskLabel" />

    <ResultsGrid :results="results" :is-loading="isLoading" @toggle-block="toggleItemBlock" />

    <Dialog v-model:open="isDeleteDialogOpen">
      <DialogContent class="max-w-[420px]">
        <DialogHeader>
          <DialogTitle>{{ t('results.filters.deleteDialogTitle') }}</DialogTitle>
          <DialogDescription>{{ deleteConfirmText }}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <button type="button" class="xy-btn-outline" @click="isDeleteDialogOpen = false">
            {{ t('common.cancel') }}
          </button>
          <button type="button" class="xy-btn-danger" :disabled="isLoading" @click="handleDeleteResults">
            {{ t('results.filters.confirmDelete') }}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>




