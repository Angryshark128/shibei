/** 后端 API 数据模型 */

export interface LlmConfig {
  base_url: string;
  model: string;
  max_tokens: number;
  has_api_key: boolean;
  api_key_hint: string;
}

export interface SourceItem {
  name: string;
  enabled: boolean;
  nodes: string[];
}

export interface AppConfig {
  llm: LlmConfig;
  sources: SourceItem[];
}

export interface TaskItem {
  id: string;
  mode: "today" | "full";
  status: "running" | "succeeded" | "failed" | "interrupted";
  started_at: number | null;
  finished_at: number | null;
  exit_code: number | null;
  log_tail?: string;
}

export interface TaskListResponse {
  tasks: TaskItem[];
}

export interface TaskDetailResponse {
  task: TaskItem;
}

export interface RunResponse {
  task: TaskItem;
}

export interface ReportMeta {
  name: string;
  file: string;
  updated_at: number | null;
  size: number;
}

export interface ReportData {
  name: string;
  updated_at: number | null;
  content: string;
}

export interface Summary {
  total_posts: number;
  per_source: Record<string, number>;
  llm_configured: boolean;
  has_full_report: boolean;
  has_today_report: boolean;
}

export interface ReportsResponse {
  reports: ReportMeta[];
  summary: Summary;
}

export interface MeResponse {
  username: string;
}

export type ViewId = "reports" | "tasks" | "settings" | "help";
