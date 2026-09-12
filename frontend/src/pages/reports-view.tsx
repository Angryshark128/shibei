import { ArrowUp, ChevronRight, FileText, FileX, Info, Loader2, RefreshCw, Shell } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import i18n, { currentLocale } from "@/i18n";
import { EmptyState } from "@/components/ui/empty";
import { ErrorBlock } from "@/components/ui/error";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { MarkdownView } from "@/components/ui/markdown";
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

/**
 * 提取报告的「文档（H2）→ 分类（H3）」结构。
 * 序号与 MarkdownView 注入的 sec-N 一致（H2/H3 依次递增），用于滚动定位。
 */
function parseDocs(content: string): TocSection[] {
  const docs: TocSection[] = [];
  let seq = 0;
  for (const raw of content.split("\n")) {
    const m = /^(#{2,3})\s+(.+)$/.exec(raw.trim());
    if (!m) continue;
    seq += 1;
    const title = m[2].replace(/[*_`~#>]/g, "").trim();
    if (m[1].length === 2) {
      docs.push({ id: `sec-${seq}`, title, items: [] });
    } else if (docs.length > 0) {
      docs[docs.length - 1].items.push({ id: `sec-${seq}`, title });
    }
  }
  return docs;
}

function scrollToSection(id: string): void {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/**
 * 公开报告页（/reports/:name，name = YYYY-MM-DD 每日归档或 analysis 全量总览）。免登录只读。
 *
 * 布局：左侧侧边栏（品牌 + 树状导航：日期可折叠 → 文档 → 分类），底部固定更新时间与刷新；
 * 右侧报告正文。窄屏时侧边栏收为顶部区域。
 */
export function ReportsView() {
  const { t } = useTranslation();
  const tz = useTimezone();
  const navigate = useNavigate();
  const { name } = useParams();
  const paramName = name ?? "";

  /** 报告展示语言：跟随 UI 语言（zh-CN→zh / en-US→en），切换时同步刷新 */
  const [preferredLang, setPreferredLang] = useState<"zh" | "en">(() =>
    currentLocale() === "en-US" ? "en" : "zh",
  );

  useEffect(() => {
    const handler = () => setPreferredLang(currentLocale() === "en-US" ? "en" : "zh");
    i18n.on("languageChanged", handler);
    return () => {
      i18n.off("languageChanged", handler);
    };
  }, []);

  const [metaList, setMetaList] = useState<ReportMeta[] | null>(null);
  const [metaError, setMetaError] = useState(false);
  const [content, setContent] = useState<{ text: string; updated_at: number | null } | null>(null);
  const [contentLoading, setContentLoading] = useState(true);
  const [contentError, setContentError] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [langFallback, setLangFallback] = useState(false);
  const [activeDoc, setActiveDoc] = useState(0);
  const [showTop, setShowTop] = useState(false);
  /** 各日期报告的目录（日期 → 文档/分类树），展开树时按需加载 */
  const [outlines, setOutlines] = useState<Record<string, TocSection[]>>({});
  const [expandedDates, setExpandedDates] = useState<Record<string, boolean>>({});
  const [expandedDocs, setExpandedDocs] = useState<Record<string, boolean>>({});
  /** 跨日期跳转时，等内容渲染完成后滚动到目标锚点 */
  const pendingScroll = useRef<{ secId: string; docIndex: number } | null>(null);

  /** 按基名分组的报告（同一份报告可有 zh/en 两种语言文件） */
  const byName = useMemo(() => {
    const map = new Map<string, ReportMeta[]>();
    for (const r of metaList ?? []) map.set(r.name, [...(map.get(r.name) ?? []), r]);
    return map;
  }, [metaList]);

  /** 每日归档日期列表（后端按日期倒序，最新在前；多语言文件合并为一个日期） */
  const dates = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const r of metaList ?? []) {
      if (r.kind !== "daily" || seen.has(r.name)) continue;
      seen.add(r.name);
      out.push(r.name);
    }
    return out;
  }, [metaList]);

  /** 优先取偏好语言的文件，缺失时回退任意一份（回退时正文显示提示条） */
  const pickMeta = useCallback(
    (n: string) => {
      const items = byName.get(n) ?? [];
      return items.find((r) => r.lang === preferredLang) ?? items[0];
    },
    [byName, preferredLang],
  );

  const mode: Mode = paramName === FULL_REPORT_NAME ? "full" : "daily";
  const currentMeta = pickMeta(paramName);

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

  const loadContent = useCallback(
    async (n: string) => {
      setContentLoading(true);
      setContentError(false);
      setNotFound(false);
      setLangFallback(false);
      try {
        const target = pickMeta(n);
        const d = await api.report(n, target?.lang ?? preferredLang);
        setContent({ text: d.content, updated_at: d.updated_at });
        setOutlines((o) => ({ ...o, [n]: parseDocs(d.content) }));
        setLangFallback(d.language !== preferredLang);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
        else setContentError(true);
      } finally {
        setContentLoading(false);
      }
    },
    [pickMeta, preferredLang],
  );

  useEffect(() => {
    void loadList();
  }, [loadList]);

  // 切报告或界面语言时重载正文（语言切换后，同语言新报告立即生效）
  useEffect(() => {
    if (paramName) void loadContent(paramName);
  }, [paramName, loadContent]);

  // 切到某份报告：展开其日期节点，回到顶部，并按需恢复目标文档
  useEffect(() => {
    if (!paramName) return;
    setExpandedDates((e) => ({ ...e, [paramName]: true }));
    const pending = pendingScroll.current;
    setActiveDoc(pending ? pending.docIndex : 0);
    window.scrollTo({ top: 0 });
  }, [paramName]);

  // 正文就绪后执行跨日期跳转的滚动
  useEffect(() => {
    const pending = pendingScroll.current;
    if (!content || !pending) return;
    pendingScroll.current = null;
    requestAnimationFrame(() => scrollToSection(pending.secId));
  }, [content]);

  // 回到顶部按钮：内容滚动一段距离后出现
  useEffect(() => {
    const onScroll = () => setShowTop(window.scrollY > 320);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const goLatest = useCallback(() => {
    if (dates.length > 0) navigate(`/reports/${dates[0]}`);
    else navigate("/reports");
  }, [dates, navigate]);

  const docs = useMemo(() => (content ? parseDocs(content.text) : []), [content]);
  const docIdx = docs.length > 0 ? Math.min(activeDoc, docs.length - 1) : 0;
  const updatedAt = content?.updated_at ?? currentMeta?.updated_at ?? null;
  const known = metaList == null || paramName === FULL_REPORT_NAME || dates.includes(paramName);
  const ready = !!content && !contentLoading && !contentError;
  const showTree = ready && !metaError && !notFound && known;

  // ---------- 树交互 ----------

  const isDateOpen = (d: string) => expandedDates[d] ?? d === paramName;

  const onDateClick = (d: string) => {
    const open = isDateOpen(d);
    setExpandedDates((e) => ({ ...e, [d]: !open }));
    if (!open) {
      if (d === paramName) return;
      pendingScroll.current = null;
      navigate(`/reports/${d}`);
    }
  };

  const isDocOpen = (d: string, secId: string, index: number) =>
    expandedDocs[`${d}:${secId}`] ?? (d === paramName && index === docIdx);

  const onDocClick = (d: string, doc: TocSection, index: number) => {
    if (d === paramName) {
      setActiveDoc(index);
      scrollToSection(doc.id);
    } else {
      pendingScroll.current = { secId: doc.id, docIndex: index };
      navigate(`/reports/${d}`);
    }
  };

  const onSectionClick = (d: string, secId: string, docIndex: number) => {
    if (d === paramName) {
      scrollToSection(secId);
    } else {
      pendingScroll.current = { secId, docIndex };
      navigate(`/reports/${d}`);
    }
  };

  // ---------- 渲染 ----------

  return (
    <>
      {/* 侧边栏：品牌（logo + 名称 + slogan）+ 可滚动树状导航 + 固定底部工具 */}
      <aside className="border-b border-surface-3 bg-surface-0 px-4 py-4 dark:border-ink-700 dark:bg-ink-700 lg:fixed lg:inset-y-0 lg:left-0 lg:z-20 lg:flex lg:w-64 lg:flex-col lg:overflow-hidden lg:border-b-0 lg:border-r lg:px-3 lg:py-5">
        <div className="flex shrink-0 items-center gap-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white dark:bg-brand-500">
            <Shell className="h-5 w-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-base font-semibold text-ink-900 dark:text-surface-0">
              {t("common.appName")}
            </p>
            <p className="truncate text-xs text-ink-400 dark:text-surface-4">{t("common.appTagline")}</p>
          </div>
        </div>

        <nav className="mt-4 min-h-0 lg:mt-6 lg:flex-1 lg:overflow-y-auto lg:pr-1" aria-label={t("reports.title")}>
          {showTree && (
            <>
              <p className="px-1.5 pb-1.5 text-xs font-medium text-ink-400 dark:text-surface-4">
                {t("reports.dateNav")}
              </p>
              {dates.map((d) => {
                const open = isDateOpen(d);
                const outline = d === paramName ? docs : outlines[d];
                return (
                  <div key={d} className="mb-0.5">
                    <button
                      type="button"
                      aria-expanded={open}
                      onClick={() => onDateClick(d)}
                      className={cn(
                        "flex w-full items-center gap-1 rounded-md px-1.5 py-1.5 text-left transition-colors duration-150",
                        d === paramName
                          ? "bg-brand-600 text-white shadow-sm"
                          : "text-ink-700 hover:bg-surface-2 dark:text-surface-4 dark:hover:bg-ink-900",
                      )}
                    >
                      <ChevronRight
                        className={cn("h-3.5 w-3.5 shrink-0 transition-transform duration-150", open && "rotate-90")}
                        aria-hidden="true"
                      />
                      <span className="font-mono text-xs">{d}</span>
                    </button>

                    {open && (
                      <div className="ml-2.5 border-l border-surface-3 pl-1.5 dark:border-ink-900">
                        {!outline ? (
                          <p className="px-2 py-1 text-xs text-ink-400 dark:text-surface-4">{t("common.loading")}</p>
                        ) : (
                          outline.map((doc, i) => {
                            const dk = `${d}:${doc.id}`;
                            const dOpen = isDocOpen(d, doc.id, i);
                            const isActive = d === paramName && i === docIdx;
                            return (
                              <div key={doc.id} className="mb-0.5">
                                <div
                                  className={cn(
                                    "flex items-center rounded-md",
                                    isActive
                                      ? "bg-surface-1 dark:bg-ink-900"
                                      : "hover:bg-surface-2 dark:hover:bg-ink-900",
                                  )}
                                >
                                  <button
                                    type="button"
                                    onClick={() => onDocClick(d, doc, i)}
                                    className={cn(
                                      "flex min-w-0 flex-1 items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-sm",
                                      isActive
                                        ? "font-medium text-brand-600 dark:text-brand-300"
                                        : "text-ink-600 dark:text-surface-4",
                                    )}
                                  >
                                    <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                                    <span className="truncate">{doc.title}</span>
                                  </button>
                                  {doc.items.length > 0 && (
                                    <button
                                      type="button"
                                      aria-expanded={dOpen}
                                      aria-label={doc.title}
                                      onClick={() => setExpandedDocs((e) => ({ ...e, [dk]: !dOpen }))}
                                      className="shrink-0 rounded p-1 text-ink-400 hover:text-ink-700 dark:text-surface-4 dark:hover:text-surface-0"
                                    >
                                      <ChevronRight
                                        className={cn("h-3 w-3 transition-transform duration-150", dOpen && "rotate-90")}
                                        aria-hidden="true"
                                      />
                                    </button>
                                  )}
                                </div>

                                {dOpen && doc.items.length > 0 && (
                                  <div className="ml-3 border-l border-surface-3 pl-1.5 dark:border-ink-900">
                                    {doc.items.map((it) => (
                                      <button
                                        key={it.id}
                                        type="button"
                                        onClick={() => onSectionClick(d, it.id, i)}
                                        className="block w-full truncate rounded-md px-2 py-1 text-left text-[13px] text-ink-500 transition-colors duration-150 hover:bg-surface-2 hover:text-brand-600 dark:text-surface-4 dark:hover:bg-ink-900 dark:hover:text-brand-300"
                                      >
                                        {it.title}
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </>
          )}
        </nav>

        {/* 固定在侧边栏底部：更新时间 + 刷新 */}
        <div className="mt-3 flex shrink-0 items-center justify-between gap-2 border-t border-surface-3 pt-2 dark:border-ink-900">
          {updatedAt != null ? (
            <span className="truncate text-[11px] text-ink-400 dark:text-surface-4">{formatTime(updatedAt, tz)}</span>
          ) : (
            <span />
          )}
          <Button
            variant="ghost"
            size="sm"
            icon={<RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />}
            disabled={contentLoading}
            onClick={() => {
              void loadList();
              if (paramName) void loadContent(paramName);
            }}
          >
            {t("common.refresh")}
          </Button>
        </div>
      </aside>

      {/* 正文 */}
      <main className="min-w-0 px-4 py-6 sm:px-6 lg:py-8 lg:pl-[17rem] lg:pr-8">
        <div className="mx-auto w-full max-w-5xl">
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
              action={<Button onClick={goLatest}>{t("reports.latest")}</Button>}
            />
          ) : content ? (
            <>
              {langFallback && (
                <div className="mb-3 flex items-start gap-2 rounded-lg border border-surface-3 bg-surface-1 px-3 py-2 text-xs leading-5 text-ink-500 dark:border-ink-900 dark:bg-ink-900 dark:text-surface-4">
                  <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <span>{t("reports.langFallback")}</span>
                </div>
              )}
              <Card>
                <CardBody className="pt-6">
                  <MarkdownView content={content.text} />
                </CardBody>
              </Card>
              <p className="mt-4 text-xs text-ink-400 dark:text-surface-4">{t("reports.runHint")}</p>
            </>
          ) : (
            <EmptyState
              icon={FileX}
              title={t("reports.emptyToday")}
              action={<Button onClick={goLatest}>{t("reports.latest")}</Button>}
            />
          )}
        </div>
      </main>

      {/* 回到顶部：放在悬浮按钮组左侧（右下角，与主按钮水平相邻） */}
      {showTop && (
        <button
          type="button"
          aria-label={t("reports.backToTop")}
          title={t("reports.backToTop")}
          className="fixed bottom-6 right-20 z-50 flex h-11 w-11 items-center justify-center rounded-full border border-surface-3 bg-surface-0 text-ink-700 shadow-lg transition-all duration-200 hover:scale-105 hover:bg-surface-2 dark:border-ink-900 dark:bg-ink-700 dark:text-surface-0 dark:hover:bg-ink-900"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        >
          <ArrowUp className="h-5 w-5" aria-hidden="true" />
        </button>
      )}

      {/* 公开页也保留主题/语言等外观切换，无退出按钮 */}
      <FloatingControls showLogout={false} onLoggedOut={() => undefined} />
    </>
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
