<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLogs } from '@/composables/useLogs'
import { useTasks } from '@/composables/useTasks'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { toast } from '@/components/ui/toast'
import { Terminal, Trash2, RefreshCw } from 'lucide-vue-next'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const { t } = useI18n()
const { tasks } = useTasks()
const { logs, isAutoRefresh, clearLogs, toggleAutoRefresh, fetchLogs, setTaskId, loadLatest, loadPrevious, isFetchingHistory, hasMoreHistory } = useLogs()
const logContainer = ref<HTMLElement | null>(null)
const autoScroll = ref(true)
const isClearDialogOpen = ref(false)
const selectedTaskId = ref('')
const isPrepending = ref(false)
const lastScrollTop = ref(0)
const lastScrollHeight = ref(0)

type LogLevel = 'all' | 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
const LEVEL_SEVERITY: Record<string, number> = {
  DEBUG: 10, INFO: 20, WARN: 30, WARNING: 30, ERROR: 40, CRITICAL: 50, FATAL: 50,
}
const LEVEL_RE = /\[(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\]/
const levelFilter = ref<LogLevel>('all')
const levelOptions = [
  { value: 'all', label: t('logs.levels.all') },
  { value: 'DEBUG', label: t('logs.levels.debug') },
  { value: 'INFO', label: t('logs.levels.info') },
  { value: 'WARNING', label: t('logs.levels.warning') },
  { value: 'ERROR', label: t('logs.levels.error') },
  { value: 'CRITICAL', label: t('logs.levels.critical') },
]
const filteredLogs = computed(() => {
  if (levelFilter.value === 'all') return logs.value
  const min = LEVEL_SEVERITY[levelFilter.value] ?? 0
  return logs.value
    .split('\n')
    .filter((line) => {
      const m = line.match(LEVEL_RE)
      const group = m && m[1] ? m[1].toUpperCase() : ''
      const level = group ? (LEVEL_SEVERITY[group] ?? 20) : 20
      return level >= min
    })
    .join('\n')
})
const logsEmpty = computed(() => logs.value.trim().length === 0)
const filteredEmpty = computed(() => !logsEmpty.value && filteredLogs.value.trim().length === 0)

watch(logs, async () => {
  if (isPrepending.value) {
    await nextTick()
    if (logContainer.value) {
      const delta = logContainer.value.scrollHeight - lastScrollHeight.value
      logContainer.value.scrollTop = lastScrollTop.value + delta
    }
    isPrepending.value = false
    return
  }
  if (autoScroll.value) {
    await nextTick()
    scrollToBottom()
  }
})

watch(tasks, (list) => {
  if (!list.length) {
    selectedTaskId.value = ''
    setTaskId(null)
    return
  }
  if (selectedTaskId.value && list.some((task) => String(task.id) === selectedTaskId.value)) return
  const running = list.find((task) => task.is_running)
  const fallback = list[0]
  if (!fallback) {
    selectedTaskId.value = ''
    setTaskId(null)
    return
  }
  selectedTaskId.value = String(running ? running.id : fallback.id)
}, { immediate: true })

watch(selectedTaskId, (taskId) => {
  const resolvedTaskId = taskId ? Number(taskId) : null
  setTaskId(resolvedTaskId)
  if (resolvedTaskId) loadLatest(50)
})

function scrollToBottom() {
  if (logContainer.value) logContainer.value.scrollTop = logContainer.value.scrollHeight
}
async function handleScroll() {
  if (!logContainer.value) return
  if (!hasMoreHistory.value || isFetchingHistory.value) return
  if (logContainer.value.scrollTop > 120) return
  lastScrollTop.value = logContainer.value.scrollTop
  lastScrollHeight.value = logContainer.value.scrollHeight
  isPrepending.value = true
  await loadPrevious(50)
}

function openClearDialog() {
  isClearDialogOpen.value = true
}
async function handleClearLogs() {
  try {
    await clearLogs()
    toast({ title: t('logs.logsCleared') })
  } catch (e) {
    toast({ title: t('logs.clearFailed'), description: (e as Error).message, variant: 'destructive' })
  } finally {
    isClearDialogOpen.value = false
  }
}
</script>

<template>
  <div class="flex h-[calc(100vh-7rem)] flex-col gap-2">
    <header class="xy-card-flat flex flex-col gap-2 p-2.5 lg:flex-row lg:items-center lg:flex-wrap">
      <div class="flex items-center gap-2">
        <span
          class="flex h-7 w-7 items-center justify-center rounded-xl"
          style="background-color: hsl(56 100% 52%)"
        >
          <Terminal class="h-4 w-4 text-slate-900" />
        </span>
        <h1 class="text-base font-black text-foreground">{{ t('logs.title') }}</h1>
      </div>

      <div class="flex flex-wrap items-center gap-2 lg:ml-auto">
        <div class="flex items-center gap-1.5">
          <Label class="text-[11px] text-slate-500">{{ t('logs.task') }}</Label>
          <Select v-model="selectedTaskId">
            <SelectTrigger class="h-8 w-[200px] text-xs">
              <SelectValue :placeholder="t('logs.selectTask')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="task in tasks" :key="task.id" :value="String(task.id)">
                {{ task.task_name }}{{ task.is_running ? t('logs.taskRunningSuffix') : '' }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex items-center gap-1.5">
          <Label class="text-[11px] text-slate-500">{{ t('logs.filterLevel') }}</Label>
          <Select v-model="levelFilter">
            <SelectTrigger class="h-8 w-[140px] text-xs">
              <SelectValue :placeholder="t('logs.levels.all')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="opt in levelOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <button type="button" class="xy-btn-outline h-8 text-[12px]" :disabled="!selectedTaskId" @click="fetchLogs">
          <RefreshCw class="h-3 w-3" />
          {{ t('common.refresh') }}
        </button>
        <div class="flex items-center gap-1.5">
          <Switch
            id="auto-refresh"
            :model-value="isAutoRefresh"
            @update:model-value="toggleAutoRefresh"
          />
          <Label for="auto-refresh" class="text-[11px] text-slate-500">{{ t('logs.autoRefresh') }}</Label>
        </div>
        <div class="flex items-center gap-1.5">
          <Switch id="auto-scroll" v-model="autoScroll" />
          <Label for="auto-scroll" class="text-[11px] text-slate-500">{{ t('logs.autoScroll') }}</Label>
        </div>
        <button type="button" class="xy-btn-danger h-8 text-[12px]" :disabled="!selectedTaskId" @click="openClearDialog">
          <Trash2 class="h-3 w-3" />
          {{ t('logs.clearLogs') }}
        </button>
      </div>
    </header>

    <div class="relative flex-1 overflow-hidden rounded-2xl bg-slate-950 text-slate-100 shadow-sm">
      <pre
        ref="logContainer"
        @scroll="handleScroll"
        class="absolute inset-0 overflow-auto whitespace-pre-wrap break-all p-3 font-mono text-[12px] leading-relaxed"
      >{{ filteredEmpty ? t('logs.emptyAfterFilter') : filteredLogs }}</pre>
    </div>

    <Dialog v-model:open="isClearDialogOpen">
      <DialogContent class="max-w-[420px]">
        <DialogHeader>
          <DialogTitle>{{ t('logs.dialogTitle') }}</DialogTitle>
          <DialogDescription>{{ t('logs.dialogDescription') }}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <button type="button" class="xy-btn-outline" @click="isClearDialogOpen = false">{{ t('common.cancel') }}</button>
          <button type="button" class="xy-btn-danger" @click="handleClearLogs">{{ t('logs.confirmClear') }}</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>




