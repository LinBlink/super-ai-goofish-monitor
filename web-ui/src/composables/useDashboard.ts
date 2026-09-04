import { computed, ref } from 'vue'
import * as dashboardApi from '@/api/dashboard'
import { useWebSocket } from '@/composables/useWebSocket'
import type {
  DashboardDipTask,
  DashboardSnapshot,
  DashboardTaskSummary,
} from '@/types/dashboard.d.ts'

export function useDashboard() {
  const { on } = useWebSocket()
  const snapshot = ref<DashboardSnapshot | null>(null)
  const isLoading = ref(false)
  const error = ref<Error | null>(null)
  let activeController: AbortController | null = null

  function upsertTaskSummary(item: DashboardTaskSummary) {
    if (!snapshot.value) return
    const key = item.task_id !== null ? `id:${item.task_id}` : `name:${item.task_name}`
    const index = snapshot.value.task_summaries.findIndex((candidate) =>
      candidate.task_id !== null
        ? `id:${candidate.task_id}` === key
        : `name:${candidate.task_name}` === key,
    )
    if (index >= 0) snapshot.value.task_summaries.splice(index, 1, item)
    else snapshot.value.task_summaries.push(item)
  }

  function appendDipTask(item: DashboardDipTask) {
    if (!snapshot.value) return
    const index = snapshot.value.declining_dip_tasks.findIndex(
      (candidate) => candidate.task_id === item.task_id && candidate.keyword === item.keyword,
    )
    if (index >= 0) snapshot.value.declining_dip_tasks.splice(index, 1, item)
    else snapshot.value.declining_dip_tasks.push(item)
  }

  function waitForCardPaint(signal: AbortSignal): Promise<void> {
    return new Promise((resolve, reject) => {
      let frame = 0
      const finish = () => {
        signal.removeEventListener('abort', abort)
        resolve()
      }
      const abort = () => {
        window.clearTimeout(timer)
        if (frame) window.cancelAnimationFrame(frame)
        reject(new DOMException('Aborted', 'AbortError'))
      }
      const timer = window.setTimeout(() => {
        frame = window.requestAnimationFrame(finish)
      }, 90)
      signal.addEventListener('abort', abort, { once: true })
    })
  }

  async function fetchSummary() {
    activeController?.abort()
    const controller = new AbortController()
    activeController = controller
    isLoading.value = true
    error.value = null
    snapshot.value = {
      summary: {
        enabled_tasks: 0,
        running_tasks: 0,
        result_files: 0,
        scanned_items: 0,
        recommended_items: 0,
        ai_recommended_items: 0,
        keyword_recommended_items: 0,
        last_updated_at: null,
      },
      task_summaries: [],
      recent_activities: [],
      declining_dip_tasks: [],
      focus_file: null,
    }
    try {
      await dashboardApi.streamDashboardSummary(async (event) => {
        if (event.type === 'task_summary') {
          upsertTaskSummary(event.data)
          await waitForCardPaint(controller.signal)
        } else if (event.type === 'declining_dip_task') {
          appendDipTask(event.data)
          await waitForCardPaint(controller.signal)
        } else if (event.type === 'complete') snapshot.value = event.data
        else if (event.type === 'error') throw new Error(event.message)
      }, controller.signal)
    } catch (e) {
      if (e instanceof dashboardApi.DashboardStreamUnavailableError) {
        try {
          snapshot.value = await dashboardApi.getDashboardSummary()
        } catch (fallbackError) {
          if (fallbackError instanceof Error) error.value = fallbackError
        }
      } else if (e instanceof Error && e.name !== 'AbortError') {
        error.value = e
      }
    } finally {
      if (activeController === controller) {
        activeController = null
        isLoading.value = false
      }
    }
  }

  const taskSummaries = computed(() => snapshot.value?.task_summaries || [])
  const activities = computed(() => snapshot.value?.recent_activities || [])
  const decliningDipTasks = computed(() => snapshot.value?.declining_dip_tasks || [])

  const stats = computed(() => {
    const summary = snapshot.value?.summary
    return {
      totalTasks: taskSummaries.value.length,
      enabledTasks: summary?.enabled_tasks || 0,
      runningTasks: summary?.running_tasks || 0,
      scannedItems: summary?.scanned_items || 0,
      recommendedItems: summary?.recommended_items || 0,
      aiRecommendedItems: summary?.ai_recommended_items || 0,
      keywordRecommendedItems: summary?.keyword_recommended_items || 0,
      resultFiles: summary?.result_files || 0,
    }
  })

  on('tasks_updated', fetchSummary)
  on('results_updated', fetchSummary)
  on('task_status_changed', fetchSummary)
  on('task_queue_changed', fetchSummary)

  fetchSummary()

  return {
    snapshot,
    stats,
    taskSummaries,
    activities,
    decliningDipTasks,
    isLoading,
    error,
    fetchSummary,
  }
}
