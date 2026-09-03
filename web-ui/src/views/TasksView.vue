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
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toast'
import PageHeader from '@/components/layout/PageHeader.vue'
import { Play, Square, ListTodo, Settings2 } from 'lucide-vue-next'
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

// State for dialogs
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
const isBatchSubmitting = ref(false)

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
  if (n === 0) return t('tasks.batchEdit.trigger')
  return t('tasks.batchEdit.triggerWithCount', { count: n })
})

function handleToggleSelect(taskId: number, selected: boolean) {
  toggleTaskSelection(taskId, selected)
}

function handleToggleSelectAll(checked: boolean) {
  if (checked) {
    selectAllTasks([...allVisibleTaskIds.value])
  } else {
    clearTaskSelection()
  }
}

async function handleBatchSubmit(updates: {
  notify_enabled?: boolean | null
  max_pages?: number | null
  new_publish_option?: string | null
}) {
  isBatchSubmitting.value = true
  try {
    const ids = [...selectedTaskIds.value]
    const result = await batchUpdateTasks(ids, updates)
    isBatchEditOpen.value = false
    clearTaskSelection()
    if (result.failed.length === 0) {
      toast({ title: t('tasks.batchEdit.success', { count: result.succeeded.length }) })
    } else if (result.succeeded.length === 0) {
      toast({
        title: t('tasks.batchEdit.allFailed'),
        description: result.failed
          .slice(0, 3)
          .map((f) => `#${f.task_id}: ${f.reason}`)
          .join('；'),
        variant: 'destructive',
      })
    } else {
      toast({
        title: t('tasks.batchEdit.partialSuccess', {
          ok: result.succeeded.length,
          fail: result.failed.length,
        }),
        description: result.failed
          .slice(0, 3)
          .map((f) => `#${f.task_id}: ${f.reason}`)
          .join('；'),
        variant: 'destructive',
      })
    }
  } catch (e) {
    toast({
      title: t('tasks.batchEdit.failed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isBatchSubmitting.value = false
  }
}

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
    const editTaskId = typeof route.query.edit === 'string' ? Number(route.query.edit) : NaN
    if (!Number.isFinite(editTaskId)) return
    const match = tasks.value.find((task) => task.id === editTaskId)
    if (!match) return
    selectedTask.value = match
    isEditDialogOpen.value = true
  },
  { immediate: true }
)

async function handleUpdateTask(data: TaskUpdate) {
  if (!selectedTask.value) return
  isEditSubmitting.value = true
  try {
    await updateTask(selectedTask.value.id, data)
    isEditDialogOpen.value = false
  }
  catch (e) {
    toast({
      title: t('tasks.toasts.updateFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
  finally {
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
  <div>
    <PageHeader :title="t('tasks.title')" :icon="ListTodo">
      <template #actions>
        <Button
          variant="outline"
          :disabled="isLoading || selectedTaskIds.size === 0"
          :title="headerSelectionLabel"
          @click="isBatchEditOpen = true"
        >
          <Settings2 class="mr-1 h-4 w-4" />
          {{ headerSelectionLabel }}
        </Button>
        <Button
          variant="outline"
          :disabled="isLoading || hasRunnableTasks === false"
          :title="t('tasks.startAll')"
          @click="handleStartAll"
        >
          <Play class="mr-1 h-4 w-4" />
          {{ t('tasks.startAll') }}
        </Button>
        <Button
          variant="outline"
          :disabled="isLoading || hasActiveTasks === false"
          :title="t('tasks.stopAll')"
          @click="handleStopAll"
        >
          <Square class="mr-1 h-4 w-4" />
          {{ t('tasks.stopAll') }}
        </Button>
        <TaskCreateDialog :account-options="accountOptions" @created="fetchTasks" />
      </template>
    </PageHeader>

    <!-- Edit Task Dialog -->
    <Dialog v-model:open="isEditDialogOpen">
      <DialogContent class="sm:max-w-[640px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{{ t('tasks.editDialog.title', { task: selectedTask?.task_name || "" }) }}</DialogTitle>
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
          <Button type="submit" form="task-form" :disabled="isEditSubmitting">
            {{ isEditSubmitting ? t('common.saving') : t('tasks.editDialog.save') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Refresh Criteria Dialog -->
    <Dialog v-model:open="isCriteriaDialogOpen">
      <DialogContent class="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>{{ t('tasks.criteria.title') }}</DialogTitle>
          <DialogDescription>
            {{ t('tasks.criteria.description') }}
          </DialogDescription>
        </DialogHeader>
        <div class="grid gap-3">
          <label class="text-sm font-medium text-gray-700">{{ t('tasks.form.description') }}</label>
          <Textarea
            v-model="criteriaDescription"
            class="min-h-[140px]"
            :placeholder="t('tasks.form.descriptionPlaceholder')"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" @click="isCriteriaDialogOpen = false">
            {{ t('common.cancel') }}
          </Button>
          <Button :disabled="isCriteriaSubmitting" @click="handleRefreshCriteria">
            {{ isCriteriaSubmitting ? t('tasks.criteria.generating') : t('tasks.criteria.action') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <div v-if="error" class="app-alert-error mb-4" role="alert">
      <strong class="font-bold">{{ t('common.error') }}</strong>
      <span class="block sm:inline">{{ error.message }}</span>
    </div>

    <TaskQueuePanel
      :queue="queue"
      :tasks="tasks"
      @stop-task="handleStopTask"
    />

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
      <DialogContent class="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>{{ t('tasks.deleteDialog.title') }}</DialogTitle>
          <DialogDescription>
            {{ taskToDelete ? t('tasks.deleteDialog.descriptionWithTask', { task: taskToDelete.task_name }) : t('tasks.deleteDialog.descriptionFallback') }}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isDeleteDialogOpen = false">{{ t('common.cancel') }}</Button>
          <Button variant="destructive" @click="handleConfirmDeleteTask">{{ t('tasks.deleteDialog.confirm') }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
