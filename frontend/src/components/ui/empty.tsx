import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  desc?: string;
  /** 空状态操作（按钮等） */
  action?: React.ReactNode;
  className?: string;
}

/** 空状态（规范 5.3）：SVG 图标 + 标题 + 描述 + 可选操作，居中 */
export function EmptyState({ icon: Icon = undefined, title, desc, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-16 text-center", className)}>
      {Icon && (
        <span className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-surface-2 dark:bg-ink-900">
          <Icon className="h-8 w-8 text-ink-400" aria-hidden="true" />
        </span>
      )}
      <h3 className="text-base font-semibold text-ink-900 dark:text-surface-0">{title}</h3>
      {desc && <p className="mt-1 max-w-sm text-sm text-ink-500 dark:text-surface-4">{desc}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
