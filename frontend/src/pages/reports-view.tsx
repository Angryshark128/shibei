import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FileText,
  FileX,
  Loader2,
  RefreshCw,
  Settings2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { EmptyState } from "@/components/ui/empty";
import { ErrorBlock } from "@/components/ui/error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { MarkdownView } from "@/components/ui/markdown";
import { PageHeader } from "@/components/layout/page-header";
import { FloatingControls } from "@/components/layout/floating-controls";
import { useTimezone } from "@/hooks/usePrefs";
import { ApiError, api } from "@/lib/api";
import { formatTime } from "@/lib/time";
import { cn } from "@/lib/utils";
import type { ReportMeta } from "@/types";

export const FULL_REPORT_NAME = "analysis";
type Mode = "daily" | "full";

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

/** 公开报告页（/reports/:name，name = YYYY-MM-DD 每日归档或 analysis 全量总览）。免登录只读。 */
export function ReportsView() {
  const { t } = useTranslation();
  const tz = useTimezone();
  const navigate = useNavigate();
  const { name } = useParams();
  const paramName = name ?? "";

  const [metaList, setMetaList] = useState<ReportMeta[] | null>(null);
  const [metaError, setMetaError] = useState(false);
  const [content, setContent] = useState<{ text: string; updated_at: number | null } | null>(null);
  const [contentLoading, setContentLoading] = useState(true);
  const [contentError, setContentError] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});

  /** 每日归档日期列表（后端按日期倒序，最新在前） */
  const dates = useMemo(
    () => (metaList ?? []).filter((r) => r.kind === "daily").map((r) => r.name),
    [metaList],
  );
  const mode: Mode = paramName === FULL_REPORT_NAME ? "full" : "daily";
  const currentMeta = metaList?.find((r) => r.name === paramName);

  // ---------- 数据加载 ----------

  const loadList = useCallback(async () => {
    try {
      const data = await api.reports();
      setMetaList(data.reports);
      setMetaError(false);
    } catch {
      setMetaList((m) => {
        if (m === null) setMetaError(true);
        return m;
      });
    }
  }, []);

  const loadContent = useCallback(async (n: string) => {
    setContentLoading(true);
    setContentError(false);
    setNotFound(false);
    try {
      const d = await api.report(n);
      setContent({ text: d.content, updated_at: d.updated_at });
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setNotFound(true);
      else setContentError(true);
    } finally {
      setContentLoading(false);
    }
  }, []);

  // 挂载拉一次报告列表
  useEffect(() => {
    void loadList();
  }, [loadList]);

  // 路由参数变化时加载对应报告内容
  useEffect(() => {
    if (paramName) void loadContent(paramName);
  }, [paramName, loadContent]);

  const goLatest = useCallback(() => {
    if (dates.length > 0) navigate(`/reports/${dates[0]}`);
    else navigate("/reports");
  }, [dates, navigate]);

  const current = content;
  const toc = useMemo(() => (current ? parseToc(current.text) : []), [current]);
  const updatedAt = current?.updated_at ?? currentMeta?.updated_at ?? null;
  const curIdx = dates.indexOf(paramName);
  const known = metaList == null || paramName === FULL_REPORT_NAME || dates.includes(paramName);

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
          <Button
            variant="secondary"
            icon={<Settings2 className="h-4 w-4" aria-hidden="true" />}
            onClick={() => navigate("/admin")}
          >
            {t("nav.manage")}
          </Button>
        }
      />

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
                  onClick={() => {
                    if (x.id === "full") navigate(`/reports/${FULL_REPORT_NAME}`);
                    else if (dates.length > 0) navigate(`/reports/${dates[0]}`);
                    else navigate("/reports");
                  }}
                >
                  {x.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-3">
              {updatedAt != null && (
                <Badge variant="neutral" title={formatTime(updatedAt, tz)}>
                  {t("reports.updatedAt", { time: formatTime(updatedAt, tz) })}
                </Badge>
              )}
              <Button
                variant="ghost"
                icon={<RefreshCw className="h-4 w-4" aria-hidden="true" />}
                disabled={contentLoading}
                onClick={() => {
                  void loadList();
                  if (paramName) void loadContent(paramName);
                }}
              >
                {t("common.refresh")}
              </Button>
            </div>
          </div>

          {/* 每日报告：按日导航（左右逐日 + 日期胶囊） */}
          {mode === "daily" && dates.length > 0 && (
            <div className="flex items-center gap-1 border-b border-surface-3 pb-3 pt-3 dark:border-ink-900">
              <Button
                variant="ghost"
                size="sm"
                className="shrink-0 px-1.5"
                aria-label={t("reports.datePrev")}
                title={t("reports.datePrev")}
                disabled={curIdx <= 0}
                onClick={() => curIdx > 0 && navigate(`/reports/${dates[curIdx - 1]}`)}
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </Button>
              <div className="scrollbar-thin flex gap-1.5 overflow-x-auto py-0.5">
                {dates.map((d) => (
                  <button
                    key={d}
                    type="button"
                    aria-pressed={paramName === d}
                    title={`${d} · ${t("reports.tabDaily")}`}
                    className={cn(
                      "shrink-0 rounded-md px-2.5 py-1 font-mono text-xs transition-all duration-150",
                      paramName === d
                        ? "bg-brand-600 text-white shadow-sm"
                        : "bg-surface-2 text-ink-600 hover:bg-surface-3 dark:bg-ink-900 dark:text-surface-4 dark:hover:bg-ink-700",
                    )}
                    onClick={() => navigate(`/reports/${d}`)}
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
                onClick={() => curIdx >= 0 && curIdx < dates.length - 1 && navigate(`/reports/${dates[curIdx + 1]}`)}
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          )}

          <div className="pt-4">
            {metaError ? (
              <ErrorBlock
                title={t("reports.loadFailedTitle")}
                desc={t("reports.loadFailedDesc")}
                onRetry={() => void loadList()}
              />
            ) : contentLoading ? (
              <div className="space-y-3 py-4" aria-busy="true">
                <div className="h-4 w-1/3 animate-pulse rounded bg-surface-2 dark:bg-ink-900" />
                <div className="h-4 w-2/3 animate-pulse rounded bg-surface-2 dark:bg-ink-900" />
                <div className="h-4 w-full animate-pulse rounded bg-surface-2 dark:bg-ink-900" />
              </div>
            ) : contentError ? (
              <ErrorBlock
                title={t("reports.loadFailedTitle")}
                desc={t("reports.loadFailedDesc")}
                onRetry={() => paramName && void loadContent(paramName)}
              />
            ) : notFound || !known ? (
              <EmptyState
                icon={FileX}
                title={mode === "full" ? t("reports.emptyFull") : t("reports.notFound")}
                desc={mode === "full" ? undefined : dates.length > 0 ? t("reports.emptyWrongDate") : undefined}
                action={
                  <Button icon={<ChevronRight className="h-4 w-4" aria-hidden="true" />} onClick={goLatest}>
                    {t("reports.latest")}
                  </Button>
                }
              />
            ) : current ? (
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
                  <MarkdownView content={current.text} />
                </div>
              </div>
            ) : (
              <EmptyState
                icon={FileX}
                title={mode === "full" ? t("reports.emptyFull") : t("reports.emptyToday")}
                action={
                  <Button onClick={() => navigate("/admin")}>{t("reports.goAdmin")}</Button>
                }
              />
            )}
          </div>
        </CardBody>
      </Card>

      <p className="text-xs text-ink-400 dark:text-surface-4">{t("reports.runHint")}</p>

      {/* 公开页也保留主题/语言等外观切换，无退出按钮 */}
      <FloatingControls showLogout={false} onLoggedOut={() => undefined} />
    </div>
  );
}

/** /reports（无参数）：拉列表后跳到最新一份每日报告 */
export function ReportsIndex() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [pending, setPending] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const data = await api.reports();
        const latest = data.reports.filter((r) => r.kind === "daily").map((r) => r.name)[0];
        navigate(latest ? `/reports/${latest}` : "/reports", { replace: true });
      } catch {
        setPending(false);
      }
    })();
  }, [navigate]);

  if (!pending) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <ErrorBlock
          title={t("reports.loadFailedTitle")}
          desc={t("reports.loadFailedDesc")}
          onRetry={() => {
            setPending(true);
            void api.reports().then((d) => {
              const latest = d.reports.filter((r) => r.kind === "daily").map((r) => r.name)[0];
              navigate(latest ? `/reports/${latest}` : "/reports", { replace: true });
            });
          }}
        />
      </div>
    );
  }
  return (
    <div className="flex min-h-[60vh] items-center justify-center" aria-busy="true">
      <Loader2 className="h-6 w-6 animate-spin text-brand-600 dark:text-brand-400" aria-hidden="true" />
    </div>
  );
}
