import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface PageHeaderProps {
  title: ReactNode;
  desc?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

/** 页面标题行（布局 4.2：标题 + 描述 + 右侧操作组） */
export function PageHeader({ title, desc, actions, className }: PageHeaderProps) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-3", className)}>
      <div className="min-w-0">
        <h1 className="text-xl font-bold text-ink-900 dark:text-surface-0">{title}</h1>
        {desc != null && <p className="mt-1 text-sm text-ink-500 dark:text-surface-4">{desc}</p>}
      </div>
      {actions != null && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
