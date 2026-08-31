export interface DashboardSummary {
  enabled_tasks: number
  running_tasks: number
  result_files: number
  scanned_items: number
  recommended_items: number
  ai_recommended_items: number
  keyword_recommended_items: number
  last_updated_at: string | null
}

export interface DashboardTaskSummary {
  task_id: number | null
  task_name: string
  keyword: string
  filename: string | null
  enabled: boolean
  is_running: boolean
  account_strategy: 'auto' | 'fixed' | 'rotate'
  cron: string | null
  region: string | null
  total_items: number
  recommended_items: number
  ai_recommended_items: number
  keyword_recommended_items: number
  latest_crawl_time: string | null
  latest_recommended_title: string | null
  latest_recommended_price: number | null
  history_avg_price: number | null
  history_sample_count: number | null
  history_snapshot_at: string | null
  history_daily_trend: Array<{
    day: string
    sample_count: number
    avg_price: number | null
    median_price: number | null
    min_price: number | null
    max_price: number | null
  }>
}

export interface DashboardActivity {
  id: string
  type: 'recommendation' | 'scan' | 'task'
  task_name: string
  keyword: string
  title: string
  status: string
  detail: string | null
  filename: string | null
  timestamp: string | null
}

export interface DashboardDeal {
  keyword: string
  task_name: string
  item_id: string
  title: string
  link: string
  latest_price: number
  latest_price_display: string
  highest_price: number
  decline_percent: number
  snapshots_count: number
  trend: number[]
  first_seen_at: string | null
  last_seen_at: string | null
}

export interface DashboardSnapshot {
  summary: DashboardSummary
  task_summaries: DashboardTaskSummary[]
  recent_activities: DashboardActivity[]
  declining_deals: DashboardDeal[]
  focus_file: string | null
}
