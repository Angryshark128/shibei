import type {
  AppConfig,
  MeResponse,
  ReportData,
  ReportsResponse,
  RunResponse,
  ScheduleConfig,
  TaskDetailResponse,
  TaskItem,
  TaskListResponse,
  WebhookConfig,
} from "@/types";

/** 浏览器侧 API 前缀：依赖 vite base（/shibei/api 或 /api） */
export const API_BASE = `${import.meta.env.BASE_URL}api`;

export class ApiError extends Error {
  status: number;
  code: string;
  friendly: boolean;

  constructor(message: string, status: number, code = "", friendly = false) {
    super(message);
    this.status = status;
    this.code = code;
    this.friendly = friendly;
  }
}

/** 未登录（401）时抛出，由调用方统一跳登录 */
export class AuthError extends Error {
  constructor() {
    super("未登录");
  }
}

function friendlyMessage(e: unknown): string {
  // 网络层失败：友好文案，禁止裸显 Failed to fetch（规范 08）
  if (e instanceof TypeError) return "网络连接失败，请检查网络后重试";
  return "服务暂时不可用，请稍后重试";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      ...init,
    });
  } catch (e) {
    throw new ApiError(friendlyMessage(e), 0, "network");
  }

  let body: unknown = null;
  try {
    body = await resp.json();
  } catch {
    // 非 JSON 响应
  }

  if (resp.status === 401) {
    // 会话过期/未登录：通知全局登出
    window.dispatchEvent(new Event("shibei:unauthorized"));
    throw new AuthError();
  }
  if (!resp.ok) {
    const detail = body as { error?: string; message?: string } | null;
    throw new ApiError(detail?.message || friendlyMessage(null), resp.status, detail?.error || "");
  }
  return body as T;
}

export const api = {
  me: () => request<MeResponse>("/me"),

  login: (username: string, password: string) =>
    request<MeResponse>("/login", { method: "POST", body: JSON.stringify({ username, password }) }),

  logout: () => request<{ ok: boolean }>("/logout", { method: "POST" }),

  getConfig: () => request<AppConfig>("/config"),

  saveConfig: (payload: {
    llm?: { base_url?: string; model?: string; max_tokens?: number };
    api_key?: string;
    clear_api_key?: boolean;
  }) =>
    request<{ ok: boolean }>("/config", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  testConfig: (payload: { llm?: { base_url?: string; model?: string }; api_key?: string }) =>
    request<{ ok: boolean; latency_ms: number }>("/config/test", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  changePassword: (current_password: string, new_password: string) =>
    request<{ ok: boolean }>("/password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),

  setSource: (name: string, enabled: boolean) =>
    request<{ ok: boolean }>(`/sources/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify({ enabled }),
    }),

  schedule: () => request<ScheduleConfig>("/schedule"),

  saveSchedule: (payload: { enabled?: boolean; time?: string }) =>
    request<ScheduleConfig>("/schedule", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  webhook: () => request<WebhookConfig>("/webhook"),

  saveWebhook: (payload: {
    enabled?: boolean;
    url?: string;
    header_key?: string;
    token?: string;
    clear_token?: boolean;
  }) =>
    request<WebhookConfig>("/webhook", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  testWebhook: () => request<{ ok: boolean }>("/webhook/test", { method: "POST" }),

  stopTask: (id: string) =>
    request<{ ok: boolean }>(`/tasks/${encodeURIComponent(id)}/stop`, { method: "POST" }),

  run: (mode: "today" | "full") =>
    request<RunResponse>("/run", {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),

  tasks: () => request<TaskListResponse>("/tasks"),

  task: (id: string) => request<TaskDetailResponse>(`/tasks/${encodeURIComponent(id)}`),

  reports: () => request<ReportsResponse>("/reports"),

  report: (name: "analysis" | "analysis_today") =>
    request<ReportData>(`/reports/${name}`),
};

export type { TaskItem };
