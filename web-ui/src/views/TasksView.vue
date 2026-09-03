<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useTasks } from '@/composables/useTasks'
import type { Task, TaskUpdate } from '@/types/task.d.ts'
import { parseTaskFormDefaults } from '@/lib/taskFormQuery'
import TaskCreateDialog from '@/components/tasks/TaskCreateDialog.vue'
import TasksTable from '@/components/tasks/TasksTable.vue'
import TaskQueuePanel from '@/components/tasks/TaskQueuePanel.vue'
import TaskForm from '@/components/tasks/TaskForm.vue'
import TaskBatchEditDialog from '@/components/tasks/TaskBatchEditDialog.vue'
import { listAccounts, type AccountItem } from '@/api/accounts'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toast'
import { Play, Square, ListTodo, Settings2, Plus } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const {
  tasks,
  queue,
  isLoading,
  error,
  fetchTasks,
  removeTask,
  updateTask,
  startTask,
  stopTask,
  startAll,
  stopAll,
  batchUpdateTasks,
  selectedTaskIds,
  allVisibleTaskIds,
  toggleTaskSelection,
  selectAllTasks,
  clearTaskSelection,
  stoppingTaskIds,
} = useTasks()
const route = useRoute()
const { t } = useI18n()

const isEditDialogOpen = ref(false)
const isCriteriaDialogOpen = ref(false)
const isEditSubmitting = ref(false)
const selectedTask = ref<Task | null>(null)
const criteriaTask = ref<Task | null>(null)
const criteriaDescription = ref('')
const isCriteriaSubmitting = ref(false)
const isDeleteDialogOpen = ref(false)
const taskToDeleteId = ref<number | null>(null)
const accountOptions = ref<AccountItem[]>([])
const isBatchEditOpen = ref(false)

const taskToDelete = computed(() => {
  if (taskToDeleteId.value === null) return null
  return tasks.value.find((task) => task.id === taskToDeleteId.value) || null
})
const editDefaults = computed(() => parseTaskFormDefaults(route.query))

const hasRunnableTasks = computed(() =>
  tasks.value.some(
    (task) =>
      task.enabled &&
      !task.is_running &&
      (task.execution_status || 'idle') !== 'queued' &&
      (task.execution_status || 'idle') !== 'running',
  ),
)
const hasActiveTasks = computed(
  () => (queue.value.running?.length ?? 0) > 0 || (queue.value.queued?.length ?? 0) > 0,
)

const selectedNames = computed(() => {
  if (selectedTaskIds.value.size === 0) return []
  return tasks.value
    .filter((task) => task.id !== undefined && selectedTaskIds.value.has(task.id))
    .map((task) => task.task_name)
})
const headerSelectionLabel = computed(() => {
  const n = selectedTaskIds.value.size
  return n === 0
    ? t('tasks.batchEdit.trigger')
    : t('tasks.batchEdit.triggerWithCount', { count: n })
})

function handleDeleteTask(taskId: number) {
  taskToDeleteId.value = taskId
  isDeleteDialogOpen.value = true
}
async function handleConfirmDeleteTask() {
  if (!taskToDelete.value) {
    toast({ title: t('tasks.toasts.notFound'), variant: 'destructive' })
    isDeleteDialogOpen.value = false
    return
  }
  try {
    await removeTask(taskToDelete.value.id)
    toast({ title: t('tasks.toasts.deleted') })
  } catch (e) {
    toast({
      title: t('tasks.toasts.deleteFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isDeleteDialogOpen.value = false
    taskToDeleteId.value = null
  }
}
function handleEditTask(task: Task) {
  selectedTask.value = task
  isEditDialogOpen.value = true
}

watch(
  () => [route.query.edit, tasks.value],
  () => {
    const editId = typeof route.query.edit === 'string' ? Number(route.query.edit) : NaN
    if (!Number.isFinite(editId)) return
    const match = tasks.value.find((task) => task.id === editId)
    if (!match) return
    selectedTask.value = match
    isEditDialogOpen.value = true
  },
  { immediate: true },
)

async function handleUpdateTask(data: TaskUpdate) {
  if (!selectedTask.value) return
  isEditSubmitting.value = true
  try {
    await updateTask(selectedTask.value.id, data)
    isEditDialogOpen.value = false
  } catch (e) {
    toast({
      title: t('tasks.toasts.updateFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isEditSubmitting.value = false
  }
}

function handleOpenCriteriaDialog(task: Task) {
  criteriaTask.value = task
  criteriaDescription.value = task.description || ''
  isCriteriaDialogOpen.value = true
}
async function handleRefreshCriteria() {
  if (!criteriaTask.value) return
  if (!criteriaDescription.value.trim()) {
    toast({
      title: t('tasks.toasts.descriptionRequired'),
      description: t('tasks.criteria.descriptionRequired'),
      variant: 'destructive',
    })
    return
  }
  isCriteriaSubmitting.value = true
  try {
    await updateTask(criteriaTask.value.id, { description: criteriaDescription.value })
    isCriteriaDialogOpen.value = false
  } catch (e) {
    toast({
      title: t('tasks.toasts.regenerateFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isCriteriaSubmitting.value = false
  }
}

async function handleStartTask(taskId: number) {
  try {
    await startTask(taskId)
  } catch (e) {
    toast({
      title: t('tasks.toasts.startFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}
async function handleStopTask(taskId: number) {
  try {
    await stopTask(taskId)
  } catch (e) {
    toast({
      title: t('tasks.toasts.stopFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}
async function handleToggleEnabled(task: Task, enabled: boolean) {
  const previous = task.enabled
  task.enabled = enabled
  try {
    await updateTask(task.id, { enabled })
  } catch (e) {
    task.enabled = previous
    toast({
      title: t('tasks.toasts.toggleFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}
async function handleStartAll() {
  try {
    await startAll()
    toast({ title: t('tasks.toasts.startAllDone') })
  } catch (e) {
    toast({
      title: t('tasks.toasts.startFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}
async function handleStopAll() {
  try {
    await stopAll()
    toast({ title: t('tasks.toasts.stopAllDone') })
  } catch (e) {
    toast({
      title: t('tasks.toasts.stopFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

function handleToggleSelect(taskId: number, selected: boolean) {
  toggleTaskSelection(taskId, selected)
}
function handleToggleSelectAll(checked: boolean) {
  if (checked) selectAllTasks([...allVisibleTaskIds.value])
  else clearTaskSelection()
}

async function handleBatchSubmit(updates: {
  notify_enabled?: boolean | null
  max_pages?: number | null
  new_publish_option?: string | null
}) {
  try {
    const ids = [...selectedTaskIds.value]
    const result = await batchUpdateTasks(ids, updates)
    isBatchEditOpen.value = false
    clearTaskSelection()
    const failedSummary = result.failed
      .slice(0, 3)
      .map((f) => `#${f.task_id}: ${f.reason}`)
      .join(' / ')
    if (result.failed.length === 0) {
      toast({ title: t('tasks.batchEdit.success', { count: result.succeeded.length }) })
    } else if (result.succeeded.length === 0) {
      toast({
        title: t('tasks.batchEdit.allFailed'),
        description: failedSummary,
        variant: 'destructive',
      })
    } else {
      toast({
        title: t('tasks.batchEdit.partialSuccess', {
          ok: result.succeeded.length,
          fail: result.failed.length,
        }),
        description: failedSummary,
        variant: 'destructive',
      })
    }
  } catch (e) {
    toast({
      title: t('tasks.batchEdit.failed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

async function fetchAccountOptions() {
  try {
    accountOptions.value = await listAccounts()
  } catch (e) {
    toast({
      title: t('tasks.toasts.loadAccountsFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}
onMounted(fetchAccountOptions)
</script>

<template>
  <div class="space-y-3">
    <!-- 操作栏 -->
    <header class="xy-card-flat flex flex-wrap items-center gap-2 p-2.5">
      <div class="flex min-w-0 items-center gap-2">
        <span
          class="flex h-7 w-7 items-center justify-center rounded-xl text-slate-700"
          style="background-color: hsl(56 100% 52%)"
        >
          <ListTodo class="h-4 w-4" />
        </span>
        <h1 class="truncate text-base font-black text-foreground">{{ t('tasks.title') }}</h1>
        <span class="xy-chip">{{ tasks.length }}</span>
      </div>

      <div class="ml-auto flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          class="xy-btn-outline h-9 text-[13px]"
          :disabled="selectedTaskIds.size === 0"
          @click="isBatchEditOpen = true"
        >
          <Settings2 class="h-3.5 w-3.5" />
          {{ headerSelectionLabel }}
        </button>
        <button
          type="button"
          class="xy-btn-outline h-9 text-[13px]"
          :disabled="!hasRunnableTasks"
          @click="handleStartAll"
        >
          <Play class="h-3.5 w-3.5" />
          {{ t('tasks.startAll') }}
        </button>
        <button
          type="button"
          class="xy-btn-outline h-9 text-[13px]"
          :disabled="!hasActiveTasks"
          @click="handleStopAll"
        >
          <Square class="h-3.5 w-3.5" />
          {{ t('tasks.stopAll') }}
        </button>
        <TaskCreateDialog :account-options="accountOptions" @created="fetchTasks">
          <template #trigger>
            <button type="button" class="xy-btn-primary h-9 text-[13px]">
              <Plus class="h-3.5 w-3.5" />
              {{ t('tasks.createDialog.trigger') }}
            </button>
          </template>
        </TaskCreateDialog>
      </div>
    </header>

    <Dialog v-model:open="isEditDialogOpen">
      <DialogContent class="max-h-[88vh] max-w-[640px] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{{ t('tasks.editDialog.title', { task: selectedTask?.task_name || '' }) }}</DialogTitle>
        </DialogHeader>
        <TaskForm
          v-if="selectedTask"
          mode="edit"
          :initial-data="selectedTask"
          :account-options="accountOptions"
          :default-values="editDefaults"
          @submit="(data) => handleUpdateTask(data as TaskUpdate)"
        />
        <DialogFooter>
          <button
            type="submit"
            form="task-form"
            class="xy-btn-primary"
            :disabled="isEditSubmitting"
          >
            {{ isEditSubmitting ? t('common.saving') : t('tasks.editDialog.save') }}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="isCriteriaDialogOpen">
      <DialogContent class="max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{{ t('tasks.criteria.title') }}</DialogTitle>
          <DialogDescription>{{ t('tasks.criteria.description') }}</DialogDescription>
        </DialogHeader>
        <div class="space-y-2">
          <label class="text-sm font-medium text-slate-700">{{ t('tasks.form.description') }}</label>
          <Textarea
            v-model="criteriaDescription"
            class="min-h-[120px]"
            :placeholder="t('tasks.form.descriptionPlaceholder')"
          />
        </div>
        <DialogFooter>
          <button type="button" class="xy-btn-outline" @click="isCriteriaDialogOpen = false">
            {{ t('common.cancel') }}
          </button>
          <button type="button" class="xy-btn-op" :disabled="isCriteriaSubmitting" @click="handleRefreshCriteria">
            {{ isCriteriaSubmitting ? t('tasks.criteria.generating') : t('tasks.criteria.action') }}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <div v-if="error" class="xy-card-flat border-rose-200 bg-rose-50/40 p-3 text-sm text-rose-700">
      {{ error.message }}
    </div>

    <TaskQueuePanel :queue="queue" :tasks="tasks" @stop-task="handleStopTask" />

    <TasksTable
      :tasks="tasks"
      :is-loading="isLoading"
      :stopping-ids="stoppingTaskIds"
      :queue="queue"
      :selected-ids="selectedTaskIds"
      @delete-task="handleDeleteTask"
      @edit-task="handleEditTask"
      @run-task="handleStartTask"
      @stop-task="handleStopTask"
      @refresh-criteria="handleOpenCriteriaDialog"
      @toggle-enabled="handleToggleEnabled"
      @toggle-select="handleToggleSelect"
      @toggle-select-all="handleToggleSelectAll"
    />

    <TaskBatchEditDialog
      v-model:open="isBatchEditOpen"
      :count="selectedTaskIds.size"
      :selected-names="selectedNames"
      @submit="handleBatchSubmit"
    />

    <Dialog v-model:open="isDeleteDialogOpen">
      <DialogContent class="max-w-[420px]">
        <DialogHeader>
          <DialogTitle>{{ t('tasks.deleteDialog.title') }}</DialogTitle>
          <DialogDescription>
            {{ taskToDelete
              ? t('tasks.deleteDialog.descriptionWithTask', { task: taskToDelete.task_name })
              : t('tasks.deleteDialog.descriptionFallback') }}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <button type="button" class="xy-btn-outline" @click="isDeleteDialogOpen = false">
            {{ t('common.cancel') }}
          </button>
          <button type="button" class="xy-btn-danger" @click="handleConfirmDeleteTask">
            {{ t('tasks.deleteDialog.confirm') }}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>