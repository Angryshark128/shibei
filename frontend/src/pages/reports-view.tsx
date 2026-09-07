import { FileX, Loader2, Play, RefreshCw, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState } from "@/components/ui/empty";
import { ErrorBlock } from "@/components/ui/error";
import { StatCard } from "@/components/ui/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { MarkdownView } from "@/components/ui/markdown";
import { useToast } from "@/components/ui/toast";
import { PageHeader } from "@/components/layout/page-header";
import { usePolling, useTimezone } from "@/hooks/usePrefs";
import { ApiError, api } from "@/lib/api";
import { formatTime } from "@/lib/time";
import { cn } from "@/lib/utils";
import type { Summary, TaskItem } from "@/types";

type ReportTab = "analysis" | "analysis_today";
type RunMode = "today" | "full";

interface ReportCache {
  content: string | null;
  updated_at: number | null;
  loading: boolean;
  error: boolean;
}

const EMPTY_CACHE: ReportCache = { content: null, updated_at: null, loading: false, error: false };

export interface ReportsViewProps {
  onGoTasks: () => void;
}

/** 报告页：概览统计 + 手动触发分析 + 报告浏览（布局 4.4 标题+图表 与 标题+详情 混合） */
export function ReportsView({ onGoTasks }: ReportsViewProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const tz = useTimezone();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [tab, setTab] = useState<ReportTab>("analysis");
  const [cache, setCache] = useState<Record<ReportTab, ReportCache>>({
    analysis: { ...EMPTY_CACHE },
    analysis_today: { ...EMPTY_CACHE },
  });
  const [running, setRunning] = useState<TaskItem | null>(null);
  const [triggerMode, setTriggerMode] = useState<RunMode | null>(null);
  const runningIdRef = useRef<string | null>(null);
  const triggerModeRef = useRef<RunMode | null>(null);

  // ---------- 数据加载 ----------

  const loadSummary = useCallback(async () => {
    try {
      const data = await api.reports();
      setSummary(data.summary);
    } catch {
      // 概览失败不影响报告区；下一轮自动/手动刷新会重试
    }
  }, []);

  const loadReport = useCallback(async (name: ReportTab) => {
    setCache((c) => ({ ...c, [name]: { ...c[name], loading: true, error: false } }));
    try {
      const data = await api.report(name);
      setCache((c) => ({ ...c, [name]: { content: data.content, updated_at: data.updated_at, loading: false, error: false } }));
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setCache((c) => ({ ...c, [name]: { content: null, updated_at: null, loading: false, error: false } }));
        return;
      }
      setCache((c) => ({ ...c, [name]: { ...c[name], loading: false, error: true } }));
    }
  }, []);

  const refreshActiveTab = useCallback(
    async (name: ReportTab) => {
      await Promise.all([loadSummary(), loadReport(name)]);
    },
    [loadSummary, loadReport],
  );

  // ---------- 触发运行 ----------

  const startRun = useCallback(
    async (mode: RunMode) => {
      try {
        const data = await api.run(mode);
        runningIdRef.current = data.task.id;
        setRunning(data.task);
        setTriggerMode(mode);
        triggerModeRef.current = mode;
        toast.push("info", mode === "full" ? t("reports.startSuccessFull") : t("reports.startSuccessToday"));
      } catch (e) {
        if (e instanceof ApiError) {
          if (e.code === "no_api_key") {
            toast.push("warn", t("reports.noApiKeyError"));
          } else if (e.code === "task_running") {
            toast.push("warn", t("reports.taskRunningError"));
          } else {
            toast.push("error", t("reports.startFail"), e.message || undefined);
          }
        } else {
          toast.push("error", t("errors.network"));
        }
      }
    },
    [t, toast],
  );

  // 运行中轮询：任务结束后刷新概览与报告
  usePolling(
    async () => {
      if (!runningIdRef.current) return true;
      const { tasks } = await api.tasks();
      const current = tasks.find((x) => x.id === runningIdRef.current);
      if (!current) {
        runningIdRef.current = null;
        setRunning(null);
        setTriggerMode(null);
        return true;
      }
      if (current.status === "running") {
        setRunning(current);
        return false;
      }
      // 任务结束
      runningIdRef.current = null;
      setRunning(null);
      const mode = triggerModeRef.current;
      setTriggerMode(null);
      triggerModeRef.current = null;
      if (current.status === "succeeded") {
        toast.push("success", mode === "full" ? t("reports.startSuccessFull") : t("reports.startSuccessToday"));
      } else {
        toast.push("error", t("tasks.statusFailed"));
      }
      await refreshActiveTab(tab);
      return true;
    },
    3000,
    !!running,
  );

  // 首次进入：拉概览 + 全量报告
  useEffect(() => {
    void loadSummary();
    void loadReport("analysis");
  }, [loadSummary, loadReport]);

  const current = cache[tab];
  const anyRunning = running != null;
  const runDisabled = anyRunning;

  // ---------- 渲染 ----------

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("reports.title")}
        desc={t("reports.desc")}
        actions={
          <>
            <Button
              variant="secondary"
              icon={<RefreshCw className="h-4 w-4" aria-hidden="true" />}
              loading={runDisabled && triggerMode === "today"}
              disabled={runDisabled}
              onClick={() => void startRun("today")}
            >
              {runDisabled && triggerMode === "today" ? "" : t("reports.btnRunToday")}
            </Button>
            <Button
              variant="primary"
              icon={<RotateCcw className="h-4 w-4" aria-hidden="true" />}
              loading={runDisabled && triggerMode === "full"}
              disabled={runDisabled}
              onClick={() => void startRun("full")}
            >
              {runDisabled && triggerMode === "full" ? "" : t("reports.btnRunFull")}
            </Button>
          </>
        }
      />

      {/* 运行中提示条 */}
      {running && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-brand-100 bg-brand-50 px-4 py-3 dark:border-brand-900 dark:bg-brand-900"
        >
          <Loader2 className="h-5 w-5 animate-spin text-brand-600 dark:text-brand-300" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-brand-700 dark:text-brand-300">
              {t("reports.runningBannerTitle")}
              <Badge variant="brand" className="ml-2">
                {running.mode === "full" ? t("tasks.modeFull") : t("tasks.modeToday")}
              </Badge>
            </p>
            <p className="mt-0.5 text-xs text-brand-700/80 dark:text-brand-300/80">{t("reports.runningBannerDesc")}</p>
          </div>
          <Button variant="ghost" onClick={onGoTasks} className="text-sm">
            {t("reports.viewLog")}
          </Button>
        </div>
      )}

      {/* 概览统计 */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label={t("reports.statPosts")}
          value={summary ? summary.total_posts : "…"}
          hint={
            summary && Object.keys(summary.per_source).length > 0
              ? Object.keys(summary.per_source).join(" · ")
              : t("reports.statPostsNone")
          }
        />
        <StatCard label={t("reports.statSources")} value={summary ? Object.keys(summary.per_source).length : "…"} />
        <StatCard
          label={t("reports.statLlm")}
          value={
            summary ? (
              summary.llm_configured ? (
                <Badge variant="success" dot>
                  {t("reports.statLlmReady")}
                </Badge>
              ) : (
                <Badge variant="warn" dot>
                  {t("reports.statLlmMissing")}
                </Badge>
              )
            ) : (
              "…"
            )
          }
        />
        <StatCard
          label={t("reports.tabToday")}
          value={
            summary?.has_today_report ? (
              <Badge variant="success" dot>
                {t("tasks.statusSucceeded")}
              </Badge>
            ) : (
              <Badge variant="neutral" dot>
                {t("reports.statPostsNone")}
              </Badge>
            )
          }
        />
      </div>

      {/* 报告卡 */}
      <Card>
        <CardBody className="pt-6">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-3 pb-4 dark:border-ink-900">
            <div
              role="tablist"
              aria-label={t("reports.title")}
              className="inline-flex items-center gap-1 rounded-lg bg-surface-2 p-1 dark:bg-ink-900"
            >
              {(
                [
                  { id: "analysis" as const, label: t("reports.tabFull") },
                  { id: "analysis_today" as const, label: t("reports.tabToday") },
                ]
              ).map((x) => (
                <button
                  key={x.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === x.id}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-medium transition-all duration-150",
                    tab === x.id
                      ? "bg-surface-0 text-ink-900 shadow-sm dark:bg-ink-700 dark:text-surface-0"
                      : "text-ink-500 hover:text-ink-900 dark:text-surface-4 dark:hover:text-surface-0",
                  )}
                  onClick={() => {
                    setTab(x.id);
                    if (!cache[x.id].content && !cache[x.id].loading && !cache[x.id].error) {
                      void loadReport(x.id);
                    }
                  }}
                >
                  {x.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-3">
              {current.updated_at != null && (
                <span className="text-xs text-ink-400 dark:text-surface-4">{t("reports.updatedAt", { time: formatTime(current.updated_at, tz) })}</span>
              )}
              <Button
                variant="ghost"
                icon={<RefreshCw className="h-4 w-4" aria-hidden="true" />}
                disabled={current.loading}
                onClick={() => void refreshActiveTab(tab)}
              >
                {t("common.refresh")}
              </Button>
            </div>
          </div>

          <div className="pt-4">
            {current.loading ? (
              <div className="space-y-3 py-4" aria-busy="true">
                <div className="h-4 w-1/3 animate-pulse rounded bg-surface-2 dark:bg-ink-900" />
                <div className="h-4 w-2/3 animate-pulse rounded bg-surface-2 dark:bg-ink-900" />
                <div className="h-4 w-full animate-pulse rounded bg-surface-2 dark:bg-ink-900" />
              </div>
            ) : current.error ? (
              <ErrorBlock
                title={t("reports.loadFailedTitle")}
                desc={t("reports.loadFailedDesc")}
                onRetry={() => void refreshActiveTab(tab)}
              />
            ) : current.content ? (
              <MarkdownView content={current.content} />
            ) : (
              <EmptyState
                icon={FileX}
                title={tab === "analysis" ? t("reports.emptyFull") : t("reports.emptyToday")}
                action={
                  <Button
                    icon={<Play className="h-4 w-4" aria-hidden="true" />}
                    disabled={runDisabled}
                    onClick={() => void startRun(tab === "analysis" ? "full" : "today")}
                  >
                    {tab === "analysis" ? t("reports.btnRunFull") : t("reports.btnRunToday")}
                  </Button>
                }
              />
            )}
          </div>
        </CardBody>
      </Card>

      <p className="text-xs text-ink-400 dark:text-surface-4">{t("reports.runHint")}</p>
    </div>
  );
}
