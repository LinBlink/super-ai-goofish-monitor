import type {
  Task,
  TaskBatchUpdateRequest,
  TaskBatchUpdateResponse,
  TaskCreateResponse,
  TaskGenerateRequest,
  TaskGenerationJob,
  TaskUpdate,
  TaskQueueState,
} from '@/types/task.d.ts'
import { http } from '@/lib/http'

export async function getAllTasks(): Promise<Task[]> {
  return await http('/api/tasks')
}

export async function createTaskWithAI(data: TaskGenerateRequest): Promise<TaskCreateResponse> {
  return await http('/api/tasks/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
}

export async function getTaskGenerationJob(jobId: string): Promise<TaskGenerationJob> {
  const result = await http(`/api/tasks/generate-jobs/${jobId}`)
  return result.job
}

export async function updateTask(taskId: number, data: TaskUpdate): Promise<Task> {
  const result = await http(`/api/tasks/${taskId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  return result.task
}

export async function startTask(taskId: number): Promise<void> {
  await http(`/api/tasks/start/${taskId}`, { method: 'POST' })
}

export async function stopTask(taskId: number): Promise<void> {
  await http(`/api/tasks/stop/${taskId}`, { method: 'POST' })
}

export async function deleteTask(taskId: number): Promise<void> {
  await http(`/api/tasks/${taskId}`, { method: 'DELETE' })
}

export async function getTaskQueue(): Promise<TaskQueueState> {
  return await http('/api/tasks/queue')
}

export async function startAllTasks(): Promise<{ enqueued: number; skipped: number }> {
  return await http('/api/tasks/start-all', { method: 'POST' })
}

export interface StartWithoutDataTodayResponse {
  date: string
  enqueued: number
  skipped_with_data: number
  skipped_unavailable: number
}

export async function startTasksWithoutDataToday(): Promise<StartWithoutDataTodayResponse> {
  return await http('/api/tasks/start-without-data-today', { method: 'POST' })
}

export async function stopAllTasks(): Promise<void> {
  await http('/api/tasks/stop-all', { method: 'POST' })
}

export async function batchUpdateTasks(
  payload: TaskBatchUpdateRequest,
): Promise<TaskBatchUpdateResponse> {
  return await http('/api/tasks/batch-update', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
}
