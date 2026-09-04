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
const TIMESTAMP_RE = /^\s*\[?(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d{1,6})?)\]?\s*/
const HIGHLIGHT_RE = /(https?:\/\/[^\s]+|(?:ERROR|CRITICAL|FATAL|Exception|Traceback|失败|异常|错误|超时|拒绝)|(?:WARNING|WARN|警告|重试|跳过|忽略|黑名单)|(?:成功|完成|完毕|推荐|命中|已保存|已加载|正常结束)|(?:AI|OpenAI|LLM|模型|prompt|分析|推理)|(?:API|URL|请求|响应|页面|浏览器|爬取|抓取|下载)|(?:任务|队列|进度|步骤|等待|第\s*\d+\s*\/\s*\d+)|(?:价格|售价|均价|最低价|¥|￥))/gi

type DisplayLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL' | 'EVENT'
type TokenTone = 'plain' | 'danger' | 'warning' | 'success' | 'ai' | 'network' | 'progress' | 'price'
interface LogToken { text: string; tone: TokenTone }
interface ParsedLogLine {
  number: number
  timestamp: string
  level: DisplayLevel
  message: string
  tokens: LogToken[]
}

function normalizeLevel(value?: string): DisplayLevel {
  if (!value) return 'EVENT'
  if (value === 'WARN') return 'WARNING'
  if (value === 'FATAL') return 'CRITICAL'
  return value as DisplayLevel
}

function inferLevel(message: string): DisplayLevel {
  if (/(?:ERROR|CRITICAL|FATAL|Exception|Traceback|失败|异常|错误)/i.test(message)) return 'ERROR'
  if (/(?:WARNING|WARN|警告|重试|超时|忽略)/i.test(message)) return 'WARNING'
  if (/(?:DEBUG|调试)/i.test(message)) return 'DEBUG'
  return 'EVENT'
}

function tokenTone(text: string): TokenTone {
  if (/^(?:https?:\/\/|API|URL|请求|响应|页面|浏览器|爬取|抓取|下载)/i.test(text)) return 'network'
  if (/^(?:ERROR|CRITICAL|FATAL|Exception|Traceback|失败|异常|错误|超时|拒绝)/i.test(text)) return 'danger'
  if (/^(?:WARNING|WARN|警告|重试|跳过|忽略|黑名单)/i.test(text)) return 'warning'
  if (/^(?:成功|完成|完毕|推荐|命中|已保存|已加载|正常结束)/i.test(text)) return 'success'
  if (/^(?:AI|OpenAI|LLM|模型|prompt|分析|推理)/i.test(text)) return 'ai'
  if (/^(?:任务|队列|进度|步骤|等待|第\s*\d+\s*\/\s*\d+)/i.test(text)) return 'progress'
  if (/^(?:价格|售价|均价|最低价|¥|￥)/i.test(text)) return 'price'
  return 'plain'
}

function tokenize(message: string): LogToken[] {
  return message.split(HIGHLIGHT_RE).filter(Boolean).map((text) => ({ text, tone: tokenTone(text) }))
}

function parseLogLine(raw: string, index: number): ParsedLogLine {
  const timestampMatch = raw.match(TIMESTAMP_RE)
  const timestamp = timestampMatch?.[1] ?? ''
  let message = timestampMatch ? raw.slice(timestampMatch[0].length) : raw
  const levelMatch = message.match(/^\s*\[(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\]\s*/i)
  const level = levelMatch ? normalizeLevel(levelMatch[1]?.toUpperCase()) : inferLevel(message)
  if (levelMatch) message = message.slice(levelMatch[0].length)
  return { number: index + 1, timestamp, level, message, tokens: tokenize(message) }
}

const levelFilter = ref<LogLevel>('all')
const levelOptions = [
  { value: 'all', label: t('logs.levels.all') },
  { value: 'DEBUG', label: t('logs.levels.debug') },
  { value: 'INFO', label: t('logs.levels.info') },
  { value: 'WARNING', label: t('logs.levels.warning') },
  { value: 'ERROR', label: t('logs.levels.error') },
  { value: 'CRITICAL', label: t('logs.levels.critical') },
]
const parsedLogs = computed(() => {
  const lines = logs.value.split('\n')
  if (lines[lines.length - 1] === '') lines.pop()
  return lines.map(parseLogLine)
})
const filteredLogLines = computed(() => {
  if (levelFilter.value === 'all') return parsedLogs.value
  const min = LEVEL_SEVERITY[levelFilter.value] ?? 0
  return parsedLogs.value.filter((line) => (LEVEL_SEVERITY[line.level] ?? 20) >= min)
})
const logsEmpty = computed(() => logs.value.trim().length === 0)
const filteredEmpty = computed(() => !logsEmpty.value && filteredLogLines.value.length === 0)

const levelClass: Record<DisplayLevel, string> = {
  DEBUG: 'border-violet-400 bg-violet-50/50',
  INFO: 'border-sky-400 bg-sky-50/40',
  WARNING: 'border-amber-500 bg-amber-50/70',
  ERROR: 'border-rose-500 bg-rose-50/80',
  CRITICAL: 'border-fuchsia-600 bg-fuchsia-50/90',
  EVENT: 'border-emerald-400 bg-emerald-50/30',
}
const badgeClass: Record<DisplayLevel, string> = {
  DEBUG: 'bg-violet-100 text-violet-700 ring-violet-300',
  INFO: 'bg-sky-100 text-sky-700 ring-sky-300',
  WARNING: 'bg-amber-100 text-amber-800 ring-amber-300',
  ERROR: 'bg-rose-100 text-rose-700 ring-rose-300',
  CRITICAL: 'bg-fuchsia-100 text-fuchsia-800 ring-fuchsia-300',
  EVENT: 'bg-emerald-100 text-emerald-700 ring-emerald-300',
}
const tokenClass: Record<TokenTone, string> = {
  plain: 'text-slate-700',
  danger: 'rounded bg-rose-100 px-0.5 font-bold text-rose-700',
  warning: 'rounded bg-amber-100 px-0.5 font-semibold text-amber-800',
  success: 'font-semibold text-emerald-700',
  ai: 'font-semibold text-fuchsia-700',
  network: 'text-cyan-700 underline decoration-cyan-400/40 underline-offset-2',
  progress: 'font-semibold text-violet-700',
  price: 'font-bold text-orange-700',
}

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

      <div class="grid w-full grid-cols-2 items-center gap-2 lg:ml-auto lg:flex lg:w-auto lg:flex-wrap">
        <div class="col-span-2 flex items-center gap-1.5 lg:col-span-1">
          <Label class="text-[11px] text-slate-500">{{ t('logs.task') }}</Label>
          <Select v-model="selectedTaskId">
            <SelectTrigger class="h-8 min-w-0 flex-1 text-xs lg:w-[200px] lg:flex-none">
              <SelectValue :placeholder="t('logs.selectTask')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="task in tasks" :key="task.id" :value="String(task.id)">
                {{ task.task_name }}{{ task.is_running ? t('logs.taskRunningSuffix') : '' }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="col-span-2 flex items-center gap-1.5 lg:col-span-1">
          <Label class="text-[11px] text-slate-500">{{ t('logs.filterLevel') }}</Label>
          <Select v-model="levelFilter">
            <SelectTrigger class="h-8 min-w-0 flex-1 text-xs lg:w-[140px] lg:flex-none">
              <SelectValue :placeholder="t('logs.levels.all')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="opt in levelOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <button type="button" class="xy-btn-outline h-8 justify-center text-[12px]" :disabled="!selectedTaskId" @click="fetchLogs">
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
        <button type="button" class="xy-btn-danger h-8 justify-center text-[12px]" :disabled="!selectedTaskId" @click="openClearDialog">
          <Trash2 class="h-3 w-3" />
          {{ t('logs.clearLogs') }}
        </button>
      </div>
    </header>

    <div class="relative min-h-0 flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-white text-slate-800 shadow-sm">
      <div
        ref="logContainer"
        @scroll="handleScroll"
        class="absolute inset-0 overflow-auto font-mono text-[12px] leading-relaxed"
      >
        <div class="sticky top-0 z-10 grid grid-cols-[minmax(0,1fr)_auto] border-b border-slate-200 bg-slate-50/95 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.16em] shadow-sm backdrop-blur sm:grid-cols-[3.5rem_10.5rem_5.5rem_minmax(0,1fr)]">
          <span class="hidden text-slate-400 sm:block">{{ t('logs.columns.line') }}</span>
          <span class="text-cyan-700">{{ t('logs.columns.time') }}</span>
          <span class="text-violet-700">{{ t('logs.columns.level') }}</span>
          <span class="hidden text-emerald-700 sm:block">{{ t('logs.columns.message') }}</span>
        </div>

        <div v-if="logsEmpty || filteredEmpty" class="flex h-full items-center justify-center px-6 text-center text-sm text-slate-500">
          {{ filteredEmpty ? t('logs.emptyAfterFilter') : t('logs.empty') }}
        </div>

        <div v-else class="py-1">
          <div
            v-for="line in filteredLogLines"
            :key="line.number"
            class="group grid grid-cols-[minmax(0,1fr)_auto] border-l-2 px-3 py-2 transition-colors hover:bg-slate-100/80 sm:grid-cols-[3.5rem_10.5rem_5.5rem_minmax(0,1fr)] sm:py-1.5"
            :class="levelClass[line.level]"
          >
            <span class="hidden select-none pr-4 text-right text-slate-300 group-hover:text-slate-500 sm:block">
              {{ line.number }}
            </span>
            <time class="font-medium tabular-nums text-cyan-700">
              {{ line.timestamp || '····-··-·· ··:··:··' }}
            </time>
            <span>
              <span
                class="inline-flex min-w-[4.5rem] justify-center rounded px-1.5 py-0.5 text-[10px] font-black tracking-wider ring-1 ring-inset"
                :class="badgeClass[line.level]"
              >
                {{ line.level }}
              </span>
            </span>
            <span class="col-span-2 mt-1 whitespace-pre-wrap break-words text-[12px] leading-5 sm:col-span-1 sm:mt-0 sm:pr-4">
              <span
                v-for="(token, tokenIndex) in line.tokens"
                :key="tokenIndex"
                :class="tokenClass[token.tone]"
              >{{ token.text }}</span>
            </span>
          </div>
        </div>
      </div>
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




