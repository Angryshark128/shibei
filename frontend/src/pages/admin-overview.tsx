import { ExternalLink, Loader2, RefreshCw, RotateCcw, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm";
import { StatCard } from "@/components/ui/stat-card";
import { useToast } from "@/components/ui/toast";
import { PageHeader } from "@/components/layout/page-header";
import { usePolling } from "@/hooks/usePrefs";
import { ApiError, api } from "@/lib/api";
import type { Summary, TaskItem } from "@/types";

type RunMode = "today" | "full";

/** 管理总览（/admin）：数据概览 + 触发分析 + 运行中状态；报告浏览在公开页 /reports */
export function AdminOverview() {
  const { t } = useTranslation();
  const toast = useToast();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [running, setRunning] = useState<TaskItem | null>(null);
  const [triggerMode, setTriggerMode] = useState<RunMode | null>(null);
  const [stopOpen, setStopOpen] = useState(false);
  const [stopping, setStopping] = useState(false);
  const runningIdRef = useRef<string | null>(null);
  const triggerModeRef = useRef<RunMode | null>(null);

  const loadSummary = useCallback(async () => {
    try {
      const d = await api.summary();
      setSummary(d.summary);
    } catch {
      // 概览失败不阻塞页面，刷新按钮可重试
    }
  }, []);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  // ---------- 触发运行 ----------

  const startRun = useCallback(
    async (m: RunMode) => {
      try {
        const data = await api.run(m);
        runningIdRef.current = data.task.id;
        setRunning(data.task);
        setTriggerMode(m);
        triggerModeRef.current = m;
        toast.push("info", m === "full" ? t("reports.startSuccessFull") : t("reports.startSuccessToday"));
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

  // 运行中轮询：任务结束后刷新概览
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
      runningIdRef.current = null;
      setRunning(null);
      const mode = triggerModeRef.current;
      setTriggerMode(null);
      triggerModeRef.current = null;
      if (current.status === "succeeded") {
        toast.push("success", mode === "full" ? t("reports.startSuccessFull") : t("reports.startSuccessToday"));
      } else if (current.status === "interrupted") {
        toast.push("info", t("reports.taskStopped"));
      } else {
        toast.push("error", t("tasks.statusFailed"));
      }
      await loadSummary();
      return true;
    },
    3000,
    !!running,
  );

  const runDisabled = running != null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("admin.title")}
        desc={t("admin.desc")}
        actions={
          <>
            <Button
              variant="secondary"
              icon={<ExternalLink className="h-4 w-4" aria-hidden="true" />}
              onClick={() => navigate("/reports")}
            >
              {t("nav.viewReports")}
            </Button>
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
          <div className="flex shrink-0 items-center gap-2">
            <Button
              variant="secondary"
              icon={<Square className="h-4 w-4" aria-hidden="true" />}
              loading={stopping}
              className="border-rose-200 text-rose-600 hover:bg-rose-50 dark:border-rose-900 dark:hover:bg-rose-900 dark:text-rose-400"
              onClick={() => setStopOpen(true)}
            >
              {t("tasks.stopLabel")}
            </Button>
            <Button variant="ghost" onClick={() => navigate("/admin/tasks")} className="text-sm">
              {t("reports.viewLog")}
            </Button>
          </div>
        </div>
      )}

      {/* 数据概览 */}
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
          label={t("reports.statToday")}
          value={
            summary?.has_today_report ? (
              <Badge variant="success" dot>
                {summary.latest_daily ?? t("reports.statLlmReady")}
              </Badge>
            ) : (
              <Badge variant="neutral" dot>
                {t("reports.statPostsNone")}
              </Badge>
            )
          }
        />
      </div>

      <div className="rounded-xl border border-surface-3 bg-surface-1 p-4 text-sm text-ink-600 dark:border-ink-700 dark:bg-ink-900 dark:text-surface-4">
        <p className="flex items-center gap-2">
          <ExternalLink className="h-4 w-4 shrink-0 text-ink-400 dark:text-surface-4" aria-hidden="true" />
          <span>
            {t("admin.reportHint")}{" "}
            <button
              type="button"
              onClick={() => navigate("/reports")}
              className="font-medium text-brand-600 hover:underline dark:text-brand-400"
            >
              {t("nav.viewReports")}
            </button>
          </span>
        </p>
      </div>

      <ConfirmDialog
        open={stopOpen}
        onOpenChange={setStopOpen}
        title={t("tasks.stopConfirmTitle")}
        message={t("tasks.stopConfirmMessage")}
        confirmLabel={t("tasks.stopLabel")}
        danger
        confirmLoading={stopping}
        onConfirm={() => {
          if (!running) return;
          setStopping(true);
          api
            .stopTask(running.id)
            .then(() => {
              toast.push("success", t("tasks.stopSent"));
              setStopOpen(false);
            })
            .catch(() => {
              toast.push("error", t("tasks.statusFailed"));
              setStopOpen(false);
            })
            .finally(() => setStopping(false));
        }}
      />
    </div>
  );
}
