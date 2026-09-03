<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Task, TaskQueueState } from '@/types/task.d.ts'
import { Square, ListOrdered } from 'lucide-vue-next'

const props = defineProps<{
  queue: TaskQueueState
  tasks: Task[]
}>()

const emit = defineEmits<{
  (e: 'stop-task', taskId: number): void
}>()

const { t } = useI18n()

const taskByName = computed(() => {
  const map = new Map<number, Task>()
  for (const task of props.tasks) map.set(task.id, task)
  return map
})

const runningTasks = computed(() =>
  (props.queue.running ?? []).map((id) => taskByName.value.get(id)).filter(Boolean) as Task[],
)
const queuedTasks = computed(() =>
  (props.queue.queued ?? []).map((id) => taskByName.value.get(id)).filter(Boolean) as Task[],
)
const hasItems = computed(() => runningTasks.value.length > 0 || queuedTasks.value.length > 0)
</script>

<template>
  <section
    v-if="hasItems"
    class="xy-card-flat border-amber-200/70 bg-amber-50/40 p-3"
  >
    <header class="mb-2 flex items-center gap-1.5 text-[12px] font-bold text-amber-700">
      <ListOrdered class="h-3.5 w-3.5" />
      {{ t('tasks.queue.title') }}
      <span class="text-[11px] font-normal text-amber-600/80">· {{ t('tasks.queue.hint') }}</span>
    </header>

    <div v-if="runningTasks.length" class="space-y-1.5">
      <p class="text-[10px] font-semibold uppercase tracking-wider text-emerald-600">
        {{ t('tasks.queue.running') }}
      </p>
      <div
        v-for="task in runningTasks"
        :key="`running-${task.id}`"
        class="flex items-center justify-between gap-2 rounded-xl border border-emerald-200/70 bg-white px-3 py-2"
      >
        <div class="flex min-w-0 items-center gap-2">
          <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
          <span class="truncate text-[13px] font-semibold text-foreground">{{ task.task_name }}</span>
        </div>
        <button
          type="button"
          class="xy-btn-danger h-7 text-[11px]"
          @click="emit('stop-task', task.id)"
        >
          <Square class="h-3 w-3 fill-current" />
          {{ t('tasks.table.stop') }}
        </button>
      </div>
    </div>

    <div v-if="queuedTasks.length" class="mt-3 space-y-1.5">
      <p class="text-[10px] font-semibold uppercase tracking-wider text-amber-600">
        {{ t('tasks.queue.waiting') }} ({{ queuedTasks.length }})
      </p>
      <div
        v-for="(task, index) in queuedTasks"
        :key="`queued-${task.id}`"
        class="flex items-center justify-between gap-2 rounded-xl border border-amber-200/70 bg-white px-3 py-2"
      >
        <div class="flex min-w-0 items-center gap-2">
          <span class="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">#{{ index + 1 }}</span>
          <span class="truncate text-[13px] font-medium text-foreground">{{ task.task_name }}</span>
        </div>
        <button
          type="button"
          class="xy-btn-outline h-7 border-amber-200 px-2 text-[11px] text-amber-700"
          @click="emit('stop-task', task.id)"
        >
          <Square class="h-3 w-3 fill-current" />
          {{ t('tasks.table.cancelQueue') }}
        </button>
      </div>
    </div>
  </section>
</template>




