// Based on the Pydantic model in the backend

export interface Task {
  id: number;
  task_name: string;
  enabled: boolean;
  keyword: string;
  description: string;
  analyze_images: boolean;
  max_pages: number;
  personal_only: boolean;
  min_price: string | null;
  max_price: string | null;
  cron: string | null;
  next_run_at?: string | null;
  ai_prompt_base_file: string;
  ai_prompt_criteria_file: string;
  account_state_file?: string | null;
  account_strategy: 'auto' | 'fixed' | 'rotate';
  free_shipping?: boolean;
  new_publish_option?: string | null;
  region?: string | null;
  decision_mode: 'ai' | 'keyword';
  keyword_rules: string[];
  blacklist_keywords: string[];
  is_running: boolean;
  execution_status?: 'idle' | 'queued' | 'running';
  ai_title_screening?: boolean | null;
  notify_enabled?: boolean | null;
}

export interface TaskQueueState {
  running: number[];
  queued: number[];
}

export type TaskGenerationStatus = 'queued' | 'running' | 'completed' | 'failed';
export type TaskGenerationStepStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface TaskGenerationStep {
  key: string;
  label: string;
  status: TaskGenerationStepStatus;
  message: string;
}

export interface TaskGenerationJob {
  job_id: string;
  task_name: string;
  status: TaskGenerationStatus;
  message: string;
  current_step: string | null;
  steps: TaskGenerationStep[];
  task: Task | null;
  error: string | null;
}

export interface TaskCreateResponse {
  message: string;
  task?: Task;
  job?: TaskGenerationJob;
}

// For PATCH requests, all fields are optional
export type TaskUpdate = Partial<Omit<Task, 'id' | 'next_run_at'>>;

// 批量修改：支持通知推送 / AI 标题预筛 / 搜索页数 / 新发布范围
export interface TaskBatchUpdate {
  notify_enabled?: boolean | null
  ai_title_screening?: boolean | null
  max_pages?: number | null
  new_publish_option?: string | null
}

export interface TaskBatchUpdateRequest {
  task_ids: number[]
  updates: TaskBatchUpdate
}

export interface TaskBatchUpdateFailure {
  task_id: number
  reason: string
}

export interface TaskBatchUpdateResponse {
  message: string
  succeeded: number[]
  failed: TaskBatchUpdateFailure[]
}

// For task creation
export interface TaskGenerateRequest {
  task_name: string;
  keyword: string;
  description?: string;
  analyze_images?: boolean;
  personal_only?: boolean;
  min_price?: string | null;
  max_price?: string | null;
  max_pages?: number;
  cron?: string | null;
  account_state_file?: string | null;
  account_strategy?: 'auto' | 'fixed' | 'rotate';
  free_shipping?: boolean;
  new_publish_option?: string | null;
  region?: string | null;
  decision_mode?: 'ai' | 'keyword';
  keyword_rules?: string[];
  blacklist_keywords?: string[];
  ai_title_screening?: boolean | null;
  notify_enabled?: boolean | null;
}
