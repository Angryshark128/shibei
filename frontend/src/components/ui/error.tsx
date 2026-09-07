import { AlertCircle, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";

export interface ErrorBlockProps {
  title?: string;
  desc?: string;
  onRetry?: () => void;
  className?: string;
}

/**
 * 加载失败占位（规范 08）：友好文案 + 就地重试，失败态常驻控件区，不裸显状态码。
 */
export function ErrorBlock({ title, desc, onRetry, className }: ErrorBlockProps) {
  const { t } = useTranslation();
  return (
    <div className={`flex flex-col items-center justify-center rounded-xl border border-surface-3 bg-surface-0 px-6 py-12 text-center dark:border-ink-700 dark:bg-ink-700 ${className ?? ""}`}>
      <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 dark:bg-rose-900">
        <AlertCircle className="h-6 w-6 text-rose-600 dark:text-rose-400" aria-hidden="true" />
      </span>
      <h3 className="text-base font-semibold text-ink-900 dark:text-surface-0">{title ?? t("errors.server")}</h3>
      {desc && <p className="mt-1 text-sm text-ink-500 dark:text-surface-4">{desc}</p>}
      {onRetry && (
        <Button variant="secondary" icon={<RefreshCw className="h-4 w-4" aria-hidden="true" />} onClick={onRetry} className="mt-5">
          {t("common.retry")}
        </Button>
      )}
    </div>
  );
}
