import { ChevronDown, ChevronLeft, ChevronRight, FileText, FileX, Loader2, Play, RefreshCw, RotateCcw, Square } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ConfirmDialog } from "@/components/ui/confirm";
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
import type { ReportMeta, Summary, TaskItem } from "@/types";

const FULL_REPORT_NAME = "analysis";
type Mode = "daily" | "full";
type RunMode = "today" | "full";

interface TocItem {
  id: string;
  title: string;
}

interface TocSection {
  id: string;
  title: string;
  items: TocItem[];
}

/** 从报告 Markdown 提取 H2/H3 目录（序号锚点与 MarkdownView 注入的 sec-N 一致） */
function parseToc(content: string): TocSection[] {
  const sections: TocSection[] = [];
  let seq = 0;
  for (const raw of content.split("\n")) {
    const m = /^(#{2,3})\s+(.+)$/.exec(raw.trim());
    if (!m) continue;
    seq += 1;
    const title = m[2].replace(/[*_`~#>]/g, "").trim();
    if (m[1].length === 2) {
      sections.push({ id: `sec-${seq}`, title, items: [] });
    } else if (sections.length > 0) {
      sections[sections.length - 1].items.push({ id: `sec-${seq}`, title });
    }
  }
  return sections;
}

function scrollToSection(id: string): void {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

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

/** 报告页：概览统计 + 手动触发 + 报告浏览（每日报告按日导航，默认最新一天；另含全量总览） */
export function ReportsView({ onGoTasks }: ReportsViewProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const tz = useTimezone();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [metaList, setMetaList] = useState<ReportMeta[]>([]);
  const [mode, setMode] = useState<Mode>("daily");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [cache, setCache] = useState<Record<string, ReportCache>>({});
  const [running, setRunning] = useState<TaskItem | null>(null);
  const [triggerMode, setTriggerMode] = useState<RunMode | null>(null);
  const [stopOpen, setStopOpen] = useState(false);
  const [stopping, setStopping] = useState(false);
  const runningIdRef = useRef<string | null>(null);
  const triggerModeRef = useRef<RunMode | null>(null);
  const selectedDateRef = useRef<string | null>(null);
  const modeRef = useRef<Mode>("daily");
  const bootRef = useRef(false);

  /** 每日归档日期列表（后端已按日期倒序，最新在前） */
  const dates = useMemo(
    () => metaList.filter((r) => r.kind === "daily").map((r) => r.name),
    [metaList],
  );

  // ---------- 数据加载 ----------

  const loadReport = useCallback(async (name: string) => {
    setCache((c) => ({ ...c, [name]: { ...(c[name] ?? EMPTY_CACHE), loading: true, error: false } }));
    try {
      const data = await api.report(name);
      setCache((c) => ({
        ...c,
        [name]: { content: data.content, updated_at: data.updated_at, loading: false, error: false },
      }));
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setCache((c) => ({ ...c, [name]: { ...EMPTY_CACHE } }));
        return;
      }
      setCache((c) => ({ ...c, [name]: { ...(c[name] ?? EMPTY_CACHE), loading: false, error: true } }));
    }
  }, []);

  /** 拉一次报告列表 + 概览，返回原始数据供调用方决定默认选中 */
  const loadData = useCallback(async () => {
    const data = await api.reports();
    setMetaList(data.reports);
    setSummary(data.summary);
    return data;
  }, []);

  const selectDate = useCallback(
    (date: string) => {
      setSelectedDate(date);
      selectedDateRef.current = date;
      void loadReport(date);
    },
    [loadReport],
  );

  /** 切换 每日 / 全量 视图：目标报告未加载则拉取 */
  const switchMode = useCallback(
    (m: Mode) => {
      setMode(m);
      modeRef.current = m;
      if (m === "daily") {
        if (selectedDateRef.current) {
          void loadReport(selectedDateRef.current);
        } else if (dates.length > 0) {
          selectDate(dates[0]);
        }
      } else {
        void loadReport(FULL_REPORT_NAME);
      }
    },
    [dates, loadReport, selectDate],
  );

  // 首次进入：拉列表，默认选中最新一份每日报告（无则停留在每日空态）
  useEffect(() => {
    if (bootRef.current) return;
    bootRef.current = true;
    void loadData().then((data) => {
      const dailies = data.reports.filter((r) => r.kind === "daily").map((r) => r.name);
      if (dailies.length > 0) selectDate(dailies[0]);
    });
  }, [loadData, selectDate]);

  // 任务结束后：刷新列表/概览；每日视图下若有更新的归档（如定时任务刚跑完）自动跳到最新
  const refreshAfterTask = useCallback(async () => {
    const data = await loadData();
    const dailies = data.reports.filter((r) => r.kind === "daily").map((r) => r.name);
    if (modeRef.current === "daily") {
      const latest = dailies[0];
      if (latest && latest !== selectedDateRef.current) {
        selectDate(latest);
        return;
      }
      if (selectedDateRef.current) await loadReport(selectedDateRef.current);
    } else {
      await loadReport(FULL_REPORT_NAME);
    }
  }, [loadData, loadReport, selectDate]);

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
      } else if (current.status === "interrupted") {
        toast.push("info", t("reports.taskStopped"));
      } else {
        toast.push("error", t("tasks.statusFailed"));
      }
      await refreshAfterTask();
      return true;
    },
    3000,
    !!running,
  );

  const activeName = mode === "full" ? FULL_REPORT_NAME : selectedDate;
  const current = (activeName && cache[activeName]) || EMPTY_CACHE;
  const currentMeta = activeName ? metaList.find((r) => r.name === activeName) : undefined;
  const anyRunning = running != null;
  const runDisabled = anyRunning;
  const curIdx = selectedDate ? dates.indexOf(selectedDate) : -1;

  // 报告目录树（章节目录导航；H2 为父节点、H3 为子项）
  const toc = useMemo(() => (current.content ? parseToc(current.content) : []), [current.content]);
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});
  const toggleSection = useCallback((i: number) => {
    setCollapsed((c) => ({ ...c, [i]: !c[i] }));
  }, []);

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
            <Button variant="ghost" onClick={onGoTasks} className="text-sm">
              {t("reports.viewLog")}
            </Button>
          </div>
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
                  { id: "daily" as const, label: t("reports.tabDaily") },
                  { id: "full" as const, label: t("reports.tabFull") },
                ]
              ).map((x) => (
                <button
                  key={x.id}
                  type="button"
                  role="tab"
                  aria-selected={mode === x.id}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-medium transition-all duration-150",
                    mode === x.id
                      ? "bg-surface-0 text-ink-900 shadow-sm dark:bg-ink-700 dark:text-surface-0"
                      : "text-ink-500 hover:text-ink-900 dark:text-surface-4 dark:hover:text-surface-0",
                  )}
                  onClick={() => switchMode(x.id)}
                >
                  {x.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-3">
              {(current.updated_at != null || currentMeta?.updated_at != null) && (
                <Badge variant="neutral" title={formatTime((current.updated_at ?? currentMeta?.updated_at) ?? 0, tz)}>
                  {t("reports.updatedAt", {
                    time: formatTime((current.updated_at ?? currentMeta?.updated_at) ?? 0, tz),
                  })}
                </Badge>
              )}
              <Button
                variant="ghost"
                icon={<RefreshCw className="h-4 w-4" aria-hidden="true" />}
                disabled={current.loading}
                onClick={() => {
                  void loadData();
                  if (activeName) void loadReport(activeName);
                }}
              >
                {t("common.refresh")}
              </Button>
            </div>
          </div>

          {/* 每日报告：按日导航（左右逐日 + 日期胶囊，默认最新） */}
          {mode === "daily" && dates.length > 0 && (
            <div className="flex items-center gap-1 border-b border-surface-3 pb-3 pt-3 dark:border-ink-900">
              <Button
                variant="ghost"
                size="sm"
                className="shrink-0 px-1.5"
                aria-label={t("reports.datePrev")}
                title={t("reports.datePrev")}
                disabled={curIdx <= 0}
                onClick={() => curIdx > 0 && selectDate(dates[curIdx - 1])}
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </Button>
              <div className="scrollbar-thin flex gap-1.5 overflow-x-auto py-0.5">
                {dates.map((d) => (
                  <button
                    key={d}
                    type="button"
                    aria-pressed={selectedDate === d}
                    title={`${d} · ${t("reports.tabDaily")}`}
                    className={cn(
                      "shrink-0 rounded-md px-2.5 py-1 font-mono text-xs transition-all duration-150",
                      selectedDate === d
                        ? "bg-brand-600 text-white shadow-sm"
                        : "bg-surface-2 text-ink-600 hover:bg-surface-3 dark:bg-ink-900 dark:text-surface-4 dark:hover:bg-ink-700",
                    )}
                    onClick={() => selectDate(d)}
                  >
                    {d}
                  </button>
                ))}
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="shrink-0 px-1.5"
                aria-label={t("reports.dateNext")}
                title={t("reports.dateNext")}
                disabled={curIdx < 0 || curIdx >= dates.length - 1}
                onClick={() => curIdx >= 0 && curIdx < dates.length - 1 && selectDate(dates[curIdx + 1])}
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          )}

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
                onRetry={() => activeName && void loadReport(activeName)}
              />
            ) : current.content ? (
              <div className="lg:grid lg:grid-cols-[minmax(0,230px)_minmax(0,1fr)] lg:gap-8">
                {toc.length > 0 && (
                  <aside className="mb-4 hidden lg:block" aria-label={t("reports.tocTitle")}>
                    <nav className="scrollbar-thin sticky top-6 max-h-[calc(100vh-3rem)] overflow-y-auto rounded-xl bg-surface-1 p-2 text-sm dark:bg-ink-900">
                      <p className="px-2 pb-1 pt-1 text-xs font-medium text-ink-400 dark:text-surface-4">
                        {t("reports.tocTitle")}
                      </p>
                      {toc.map((s, i) => (
                        <div key={s.id} className="mb-0.5">
                          <div className="flex items-center rounded-md hover:bg-surface-2 dark:hover:bg-ink-700">
                            <button
                              type="button"
                              aria-expanded={!collapsed[i]}
                              className="shrink-0 rounded p-1 text-ink-400 hover:text-ink-700 dark:text-surface-4 dark:hover:text-surface-0"
                              onClick={() => toggleSection(i)}
                            >
                              <ChevronDown
                                className={cn("h-3.5 w-3.5 transition-transform duration-150", collapsed[i] && "-rotate-90")}
                                aria-hidden="true"
                              />
                            </button>
                            <button
                              type="button"
                              onClick={() => scrollToSection(s.id)}
                              className="min-w-0 flex-1 truncate rounded-md py-1 pr-2 text-left font-medium text-ink-700 hover:text-brand-600 dark:text-surface-4 dark:hover:text-brand-300"
                            >
                              {s.title}
                            </button>
                          </div>
                          {!collapsed[i] &&
                            s.items.map((it) => (
                              <button
                                key={it.id}
                                type="button"
                                onClick={() => scrollToSection(it.id)}
                                className="ml-6 flex min-w-0 items-center gap-1.5 rounded-md px-2 py-1 text-left text-ink-500 hover:bg-surface-2 hover:text-brand-600 dark:text-surface-4 dark:hover:bg-ink-700 dark:hover:text-brand-300"
                              >
                                <FileText className="h-3 w-3 shrink-0" aria-hidden="true" />
                                <span className="truncate">{it.title}</span>
                              </button>
                            ))}
                        </div>
                      ))}
                    </nav>
                  </aside>
                )}
                <div className="min-w-0">
                  <MarkdownView content={current.content} />
                </div>
              </div>
            ) : (
              <EmptyState
                icon={FileX}
                title={mode === "full" ? t("reports.emptyFull") : t("reports.emptyToday")}
                action={
                  <Button
                    icon={<Play className="h-4 w-4" aria-hidden="true" />}
                    disabled={runDisabled}
                    onClick={() => void startRun(mode === "full" ? "full" : "today")}
                  >
                    {mode === "full" ? t("reports.btnRunFull") : t("reports.btnRunToday")}
                  </Button>
                }
              />
            )}
          </div>
        </CardBody>
      </Card>

      <p className="text-xs text-ink-400 dark:text-surface-4">{t("reports.runHint")}</p>

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
