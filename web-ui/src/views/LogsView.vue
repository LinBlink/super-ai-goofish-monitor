<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLogs } from '@/composables/useLogs'
import { useTasks } from '@/composables/useTasks'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/components/ui/toast'
import { Terminal } from 'lucide-vue-next'

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

// ── 日志等级过滤（按最低严重级别） ──────────────────────────────
type LogLevel = 'all' | 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'

const LEVEL_SEVERITY: Record<string, number> = {
  DEBUG: 10,
  INFO: 20,
  WARN: 30,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50,
  FATAL: 50,
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

// 无等级标记的普通行视为 INFO，便于"全部/DEBUG/INFO"时都能看到
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

// Auto-scroll logic
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
  if (selectedTaskId.value && list.some((task) => String(task.id) === selectedTaskId.value)) {
    return
  }
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
  if (resolvedTaskId) {
    loadLatest(50)
  }
})

function scrollToBottom() {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
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
    toast({
      title: t('logs.clearFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isClearDialogOpen.value = false
  }
}
</script>

<template>
  <div class="flex h-[calc(100vh-100px)] flex-col gap-4">
    <div class="app-surface p-4">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center">
        <div class="flex items-center gap-3">
          <div class="page-icon"><Terminal class="h-6 w-6" /></div>
          <h1 class="text-2xl font-black text-slate-800">{{ t('logs.title') }}</h1>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Label class="text-sm text-gray-600">{{ t('logs.task') }}</Label>
          <Select v-model="selectedTaskId">
            <SelectTrigger class="w-full sm:w-[260px]">
              <SelectValue :placeholder="t('logs.selectTask')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="task in tasks" :key="task.id" :value="String(task.id)">
                {{ task.task_name }}{{ task.is_running ? t('logs.taskRunningSuffix') : '' }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Label class="text-sm text-gray-600">{{ t('logs.filterLevel') }}</Label>
          <Select v-model="levelFilter">
            <SelectTrigger class="w-full sm:w-[170px]">
              <SelectValue :placeholder="t('logs.levels.all')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="opt in levelOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      
      <div class="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center md:justify-end">
        <Button variant="outline" size="sm" :disabled="!selectedTaskId" @click="fetchLogs">
          {{ t('common.refresh') }}
        </Button>

        <div class="flex items-center space-x-2">
          <Switch id="auto-refresh" :model-value="isAutoRefresh" @update:model-value="toggleAutoRefresh" />
          <Label for="auto-refresh">{{ t('logs.autoRefresh') }}</Label>
        </div>

        <div class="flex items-center space-x-2">
          <Switch id="auto-scroll" v-model="autoScroll" />
          <Label for="auto-scroll">{{ t('logs.autoScroll') }}</Label>
        </div>

        <Button variant="destructive" size="sm" :disabled="!selectedTaskId" @click="openClearDialog">
          {{ t('logs.clearLogs') }}
        </Button>
      </div>
    </div>
    </div>

    <Card class="app-surface flex flex-1 flex-col overflow-hidden border-none">
      <CardContent class="flex-1 p-0 relative">
        <pre
          ref="logContainer"
          @scroll="handleScroll"
          class="absolute inset-0 p-4 bg-gray-950 text-gray-100 font-mono text-sm overflow-auto whitespace-pre-wrap break-all"
        >{{ filteredEmpty ? t('logs.emptyAfterFilter') : filteredLogs }}</pre>
      </CardContent>
    </Card>

    <Dialog v-model:open="isClearDialogOpen">
      <DialogContent class="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>{{ t('logs.dialogTitle') }}</DialogTitle>
          <DialogDescription>
            {{ t('logs.dialogDescription') }}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isClearDialogOpen = false">{{ t('common.cancel') }}</Button>
          <Button variant="destructive" @click="handleClearLogs">{{ t('logs.confirmClear') }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
