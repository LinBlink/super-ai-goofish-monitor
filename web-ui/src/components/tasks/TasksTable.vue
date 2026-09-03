<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Task, TaskQueueState } from '@/types/task.d.ts'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Play,
  Square,
  Pencil,
  Trash2,
  Clock,
  MapPin,
  RefreshCcw,
  Search,
  Keyboard,
  BrainCircuit,
  Bell,
  BellOff,
} from 'lucide-vue-next'
import { formatCountdown, formatNextRunAbsolute } from '@/lib/taskSchedule'

type ExecStatus = 'idle' | 'queued' | 'running'

interface Props {
  tasks: Task[]
  isLoading: boolean
  stoppingIds?: Set<number>
  queue?: TaskQueueState
  selectedIds?: Set<number>
}

const props = defineProps<Props>()
const { t } = useI18n()

const emit = defineEmits<{
  (e: 'delete-task', taskId: number): void
  (e: 'run-task', taskId: number): void
  (e: 'stop-task', taskId: number): void
  (e: 'edit-task', task: Task): void
  (e: 'refresh-criteria', task: Task): void
  (e: 'toggle-enabled', task: Task, enabled: boolean): void
  (e: 'toggle-select', taskId: number, selected: boolean): void
  (e: 'toggle-select-all', selected: boolean): void
}>()

const isStopping = (id: number) => props.stoppingIds?.has(id) ?? false
const isKeywordMode = (task: Task) => task.decision_mode === 'keyword'

const nowMs = ref(Date.now())
let timer: number | null = null
onMounted(() => {
  timer = window.setInterval(() => (nowMs.value = Date.now()), 1000)
})
onBeforeUnmount(() => {
  if (timer !== null) window.clearInterval(timer)
})

const selectedSet = computed(() => props.selectedIds ?? new Set<number>())
const selectableIds = computed(() =>
  props.tasks
    .map((t) => t.id)
    .filter((id): id is number => typeof id === 'number'),
)
const allSelected = computed(
  () =>
    selectableIds.value.length > 0 &&
    selectableIds.value.every((id) => selectedSet.value.has(id)),
)
const someSelected = computed(
  () =>
    !allSelected.value &&
    selectableIds.value.some((id) => selectedSet.value.has(id)),
)

function statusOf(task: Task): ExecStatus {
  if (task.execution_status) return task.execution_status
  return task.is_running ? 'running' : 'idle'
}
function isRunning(task: Task) {
  return statusOf(task) === 'running'
}
function isQueued(task: Task) {
  return statusOf(task) === 'queued'
}
function queuePositionOf(_task: Task) {
  return -1
}
void queuePositionOf
function resolveAccountLabel(task: Task) {
  if (task.account_strategy === 'rotate') return t('tasks.table.accountRotate')
  if (task.account_strategy === 'fixed') return t('tasks.table.accountFixed')
  return t('tasks.table.accountAuto')
}
function resolveAccountName(task: Task) {
if (!task.account_state_file) return '—'
  const parts = task.account_state_file.split('/')
  return (parts[parts.length - 1] || task.account_state_file).replace('.json', '')
}
function resolveCountdownText(task: Task) {
  if (!task.cron) return t('tasks.table.manualTrigger')
  if (!task.enabled) return t('tasks.table.disabled')
  return formatCountdown(task.next_run_at, nowMs.value) || t('tasks.table.waitingSchedule')
}
function resolveCountdownTone(task: Task) {
  if (!task.cron) return 'text-slate-400'
  if (!task.enabled) return 'text-slate-400'
  return 'text-amber-600'
}
</script>

<template>
  <!-- ============================= 移动端：任务卡堆�?============================= -->
  <div class="space-y-2 lg:hidden">
    <template v-if="isLoading && tasks.length === 0">
      <div class="xy-card flex items-center justify-center gap-2 py-10 text-sm text-slate-400">
        <RefreshCcw class="h-4 w-4 animate-spin" />
        {{ t('tasks.table.syncing') }}
      </div>
    </template>
    <template v-else-if="tasks.length === 0">
      <div class="xy-card flex flex-col items-center justify-center gap-2 py-10 text-center text-sm text-slate-500">
        <RefreshCcw class="h-6 w-6 text-slate-300" />
        <span class="font-bold">{{ t('tasks.table.empty') }}</span>
      </div>
    </template>
    <template v-else>
      <article
        v-for="task in tasks"
        :key="task.id"
        class="xy-card relative flex p-3"
      >
        <!-- 左：复选框 -->
        <div class="mr-3 mt-0.5 flex shrink-0 items-start">
          <Checkbox
            :model-value="task.id !== undefined && selectedSet.has(task.id)"
            :aria-label="t('tasks.batchSelect.toggleRow', { name: task.task_name })"
            @update:model-value="(v) => task.id !== undefined && emit('toggle-select', task.id, v as boolean)"
          />
        </div>

        <!-- 中：信息 -->
        <div class="min-w-0 flex-1 space-y-1.5">
          <header class="flex items-start justify-between gap-2">
            <div class="min-w-0 flex-1">
              <h3 class="truncate text-[14px] font-bold text-foreground">{{ task.task_name }}</h3>
              <p class="mt-0.5 flex items-center gap-1 text-[11px] text-slate-500">
                <Search class="h-3 w-3" />
                <span class="truncate">{{ task.keyword }}</span>
              </p>
            </div>
            <span
              class="shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-bold"
              :class="
                isKeywordMode(task)
                  ? 'bg-blue-50 text-blue-600'
                  : 'bg-emerald-50 text-emerald-700'
              "
            >
              <component
                :is="isKeywordMode(task) ? Keyboard : BrainCircuit"
                class="mr-0.5 inline h-2.5 w-2.5"
              />
              {{ isKeywordMode(task) ? 'K' : 'AI' }}
            </span>
          </header>

          <div class="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-600">
            <span class="xy-chip">
              <Clock class="h-3 w-3" />
              {{ task.cron || t('tasks.table.manualTrigger') }}
            </span>
            <span class="xy-chip">
              ¥{{ task.min_price || 0 }} - {{ task.max_price || 'MAX' }}
            </span>
            <span class="xy-chip">{{ resolveAccountLabel(task) }}</span>
            <span v-if="task.region" class="xy-chip">
              <MapPin class="h-3 w-3" />
              {{ task.region }}
            </span>
            <span v-if="task.notify_enabled === false" class="xy-chip text-slate-400">
              <BellOff class="h-3 w-3" />
              {{ t('tasks.table.notifyOff') }}
            </span>
            <span v-else class="xy-chip text-slate-400">
              <Bell class="h-3 w-3" />
            </span>
          </div>

          <p
            v-if="task.cron && task.next_run_at"
            class="text-[11px] tabular"
            :class="resolveCountdownTone(task)"
          >
            {{ resolveCountdownText(task) }}
            <span v-if="task.enabled" class="ml-1 text-slate-400">
              · {{ formatNextRunAbsolute(task.next_run_at) }}
            </span>
          </p>

          <footer class="flex items-center gap-2 pt-1">
            <button
              v-if="!isRunning(task) && !isQueued(task)"
              type="button"
              class="xy-btn-primary h-7 px-3 text-[12px]"
              :class="task.enabled ? '' : 'opacity-50 pointer-events-none'"
              @click="emit('run-task', task.id)"
            >
              <Play class="h-3 w-3 fill-current" />
              {{ t('tasks.table.start') }}
            </button>
            <button
              v-else
              type="button"
              class="xy-btn-danger h-7 px-3 text-[12px]"
              :disabled="isStopping(task.id)"
              @click="emit('stop-task', task.id)"
            >
              <Square class="h-3 w-3 fill-current" />
              {{ isStopping(task.id) ? t('tasks.table.stopping') : t('tasks.table.stop') }}
            </button>
            <button
              type="button"
              class="xy-btn-outline h-7 px-2 text-[12px]"
              :aria-label="t('common.edit')"
              @click="emit('edit-task', task)"
            >
              <Pencil class="h-3 w-3" />
            </button>
            <button
              type="button"
              class="xy-btn-outline h-7 px-2 text-[12px] text-rose-500"
              :aria-label="t('common.delete')"
              @click="emit('delete-task', task.id)"
            >
              <Trash2 class="h-3 w-3" />
            </button>
          </footer>
        </div>
      </article>
    </template>
  </div>

  <!-- ============================= 桌面端：表格 ============================= -->
  <div class="hidden lg:block">
    <div class="xy-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-muted text-[11px] uppercase tracking-wider text-slate-500">
          <tr>
            <th class="w-10 px-3 py-2 text-center">
              <Checkbox
                :model-value="allSelected"
                :indeterminate="someSelected"
                :aria-label="t('tasks.batchSelect.toggleAll')"
                @update:model-value="(v) => emit('toggle-select-all', v as boolean)"
              />
            </th>
            <th class="px-3 py-2 text-left font-bold">{{ t('tasks.table.headers.details') }}</th>
            <th class="px-3 py-2 text-left font-bold">{{ t('tasks.table.headers.crawl') }}</th>
            <th class="px-3 py-2 text-left font-bold">{{ t('tasks.table.headers.mode') }}</th>
            <th class="px-3 py-2 text-center font-bold">{{ t('tasks.table.headers.schedule') }}</th>
            <th class="px-3 py-2 text-right font-bold">{{ t('tasks.table.headers.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="isLoading && tasks.length === 0">
            <td colspan="6" class="px-3 py-10 text-center text-sm text-slate-400">
              <RefreshCcw class="mx-auto mb-2 h-5 w-5 animate-spin" />
              {{ t('tasks.table.syncing') }}
            </td>
          </tr>
          <tr v-else-if="tasks.length === 0">
            <td colspan="6" class="px-3 py-10 text-center text-sm text-slate-500">
              {{ t('tasks.table.empty') }}
            </td>
          </tr>
          <tr
            v-for="task in tasks"
            :key="task.id"
            class="border-t border-border align-middle"
          >
            <td class="px-3 py-2 text-center">
              <Checkbox
                :model-value="task.id !== undefined && selectedSet.has(task.id)"
                :aria-label="t('tasks.batchSelect.toggleRow', { name: task.task_name })"
                @update:model-value="(v) => task.id !== undefined && emit('toggle-select', task.id, v as boolean)"
              />
            </td>
            <td class="px-3 py-2">
              <div class="flex items-center gap-1.5">
                <span class="text-[14px] font-bold text-foreground">{{ task.task_name }}</span>
                <span
                  class="rounded-full px-1.5 text-[10px] font-bold"
                  :class="isKeywordMode(task) ? 'bg-blue-50 text-blue-600' : 'bg-emerald-50 text-emerald-700'"
                >
                  {{ isKeywordMode(task) ? 'K' : 'AI' }}
                </span>
              </div>
              <p class="mt-0.5 flex items-center gap-1 text-[11px] text-slate-500">
                <Search class="h-3 w-3" /> {{ task.keyword }}
              </p>
            </td>
            <td class="px-3 py-2">
              <p class="text-[13px] tabular text-foreground">
                ¥{{ task.min_price || 0 }} - {{ task.max_price || 'MAX' }}
              </p>
              <p class="text-[10px] text-slate-400">{{ resolveAccountLabel(task) }}</p>
            </td>
            <td class="px-3 py-2">
              <span class="text-[12px] text-slate-600">{{ resolveAccountName(task) }}</span>
            </td>
            <td class="px-3 py-2 text-center">
              <p class="text-[12px] font-bold tabular" :class="resolveCountdownTone(task)">
                {{ resolveCountdownText(task) }}
              </p>
              <p
                v-if="task.cron && task.next_run_at && task.enabled"
                class="text-[10px] tabular text-slate-400"
              >
                {{ formatNextRunAbsolute(task.next_run_at) }}
              </p>
            </td>
            <td class="px-3 py-2">
              <div class="flex items-center justify-end gap-1.5">
                <button
                  v-if="!isRunning(task) && !isQueued(task)"
                  type="button"
                  class="xy-btn-op h-7 px-2.5 text-[11px]"
                  :class="task.enabled ? '' : 'opacity-50 pointer-events-none'"
                  @click="emit('run-task', task.id)"
                >
                  <Play class="h-3 w-3 fill-current" />
                  {{ t('tasks.table.start') }}
                </button>
                <button
                  v-else
                  type="button"
                  class="xy-btn-danger h-7 px-2.5 text-[11px]"
                  :disabled="isStopping(task.id)"
                  @click="emit('stop-task', task.id)"
                >
                  <Square class="h-3 w-3 fill-current" />
                  {{ isStopping(task.id) ? t('tasks.table.stopping') : t('tasks.table.stop') }}
                </button>
                <button
                  type="button"
                  class="rounded-full p-1.5 text-slate-500 hover:bg-muted hover:text-slate-700"
                  :aria-label="t('common.edit')"
                  @click="emit('edit-task', task)"
                >
                  <Pencil class="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  class="rounded-full p-1.5 text-slate-500 hover:bg-rose-50 hover:text-rose-600"
                  :aria-label="t('common.delete')"
                  @click="emit('delete-task', task.id)"
                >
                  <Trash2 class="h-3.5 w-3.5" />
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>




