import { computed, ref } from 'vue'
import * as dashboardApi from '@/api/dashboard'
import { useWebSocket } from '@/composables/useWebSocket'
import type { DashboardSnapshot } from '@/types/dashboard.d.ts'

export function useDashboard() {
  const { on } = useWebSocket()
  const snapshot = ref<DashboardSnapshot | null>(null)
  const isLoading = ref(false)
  const error = ref<Error | null>(null)

  async function fetchSummary() {
    isLoading.value = true
    error.value = null
    try {
      snapshot.value = await dashboardApi.getDashboardSummary()
    } catch (e) {
      if (e instanceof Error) error.value = e
    } finally {
      isLoading.value = false
    }
  }

  const taskSummaries = computed(() => snapshot.value?.task_summaries || [])
  const activities = computed(() => snapshot.value?.recent_activities || [])
  const decliningDeals = computed(() => snapshot.value?.declining_deals || [])

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
    decliningDeals,
    isLoading,
    error,
    fetchSummary,
  }
}
