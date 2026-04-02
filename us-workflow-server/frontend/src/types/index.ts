export interface WorkflowOverviewCard {
  key: string
  label: string
  total: number
  auto_mode: string
  description: string
}

export interface WorkflowOverview {
  cards: WorkflowOverviewCard[]
  service_status: string
  automation_scope: string
  review_scope: string
}

export interface WorkflowItem {
  uuid: string
  title: string | null
  country: string | null
  severity: string | null
  event_status: string | null
  pool: string
  imagery: string
  quality: string
  inference: string
  summary: string
  report_candidate: string
  pool_status: string
  event_date: number | null
  latitude: number | null
  longitude: number | null
  selected_image_type: string | null
  last_operator: string | null
  updated_at: number | null
}

export interface WorkflowItemListResult {
  total: number
  page: number
  page_size: number
  data: WorkflowItem[]
}

export interface WorkflowItemDetail extends WorkflowItem {
  category: string | null
  address: string | null
  source_url: string | null
  last_update: number | null
  detail_fetch_status: string | null
  detail_fetch_attempts: number | null
  detail_fetch_http_status: number | null
  detail_fetch_last_attempt: number | null
  detail_fetch_error: string | null
  detail_fetch_completed_at: number | null
  details_json: unknown
  pre_image_path: string | null
  pre_image_date: number | null
  pre_image_source: string | null
  post_image_path: string | null
  post_image_date: number | null
  post_image_source: string | null
  quality_score: number | null
  quality_assessment: unknown
  task_status: string | null
  task_progress_stage: string | null
  task_progress_message: string | null
  task_failure_reason: string | null
  summary_text: string | null
  summary_review_status: string | null
  summary_review_reason: string | null
  report_date: string | null
  report_ready: boolean
}

export interface ReportCandidate {
  uuid: string
  title: string | null
  country: string | null
  severity: string | null
  report_date: string
  updated_at: number | null
}

export interface DailyReport {
  report_date: string
  report_title: string | null
  event_count: number
  generated_at: number | null
  published: boolean
  report_content?: string
  category_stats?: string
  severity_stats?: string
  country_stats?: string
  published_at?: number | null
}

export interface User {
  id: number
  username: string
  email?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface ApiResponse<T> {
  data?: T
  message?: string
  error?: string
}

export interface BatchActionResponse {
  message: string
  total: number
  succeeded: number
  failed: number
  results: Array<{
    uuid: string
    ok: boolean
    message: string
  }>
}

export interface WorkflowBatchJob {
  id: number
  action: string
  target_pool: string
  status: string
  progress_total: number
  progress_completed: number
  progress_succeeded: number
  progress_failed: number
  progress_message: string | null
  cancel_requested: boolean
  error_message: string | null
  created_by: string | null
  created_at: number
  started_at: number | null
  finished_at: number | null
  updated_at: number
  errors: Array<{
    uuid: string
    message: string
  }>
}
