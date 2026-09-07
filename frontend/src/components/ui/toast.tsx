import { AlertTriangle, CheckCircle, Info, X, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type ToastLevel = "success" | "error" | "warn" | "info";

interface ToastItem {
  id: number;
  level: ToastLevel;
  title: string;
  desc?: string;
}

interface ToastContextValue {
  push: (level: ToastLevel, title: string, desc?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const LEVEL_STYLE: Record<ToastLevel, { wrap: string; text: string; bar: string; Icon: typeof Info }> = {
  success: { wrap: "bg-emerald-50 dark:bg-emerald-900", text: "text-emerald-700 dark:text-emerald-300", bar: "bg-emerald-600", Icon: CheckCircle },
  error: { wrap: "bg-rose-50 dark:bg-rose-900", text: "text-rose-700 dark:text-rose-300", bar: "bg-rose-600", Icon: XCircle },
  warn: { wrap: "bg-amber-50 dark:bg-amber-900", text: "text-amber-700 dark:text-amber-300", bar: "bg-amber-600", Icon: AlertTriangle },
  info: { wrap: "bg-brand-50 dark:bg-brand-900", text: "text-brand-700 dark:text-brand-300", bar: "bg-brand-600", Icon: Info },
};

const AUTO_DISMISS_MS = 3000;
const MAX_VISIBLE = 3;

/** Toast 通知（规范 7.11）：顶部居中、success/info 3s 自动关、error/warn 手动关、最多 3 条 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((list) => list.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (level: ToastLevel, title: string, desc?: string) => {
      counter.current += 1;
      const item: ToastItem = { id: counter.current, level, title, desc };
      setToasts((list) => [...list.slice(-(MAX_VISIBLE - 1)), item]);
      if (level === "success" || level === "info") {
        window.setTimeout(() => dismiss(item.id), AUTO_DISMISS_MS);
      }
    },
    [dismiss],
  );

  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div aria-live="polite" className="fixed left-1/2 top-4 z-[60] flex w-full max-w-[480px] -translate-x-1/2 flex-col items-center gap-2 px-4">
        {toasts.map((t) => {
          const s = LEVEL_STYLE[t.level];
          return (
            <div
              key={t.id}
              role="status"
              className={cn(
                "pointer-events-auto relative flex w-full items-start gap-3 overflow-hidden rounded-lg px-4 py-3 shadow-md transition-all duration-200",
                s.wrap,
              )}
            >
              <span className={cn("absolute inset-y-0 left-0 w-1", s.bar)} aria-hidden="true" />
              <s.Icon className={cn("mt-0.5 h-4 w-4 shrink-0", s.text)} aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className={cn("text-sm font-medium", s.text)}>{t.title}</p>
                {t.desc && <p className="mt-0.5 text-xs text-ink-500 dark:text-surface-4">{t.desc}</p>}
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="关闭"
                className="shrink-0 border-none bg-transparent p-0.5 text-ink-400 transition-colors hover:text-ink-900 dark:hover:text-surface-0"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast 必须在 ToastProvider 内使用");
  return ctx;
}
