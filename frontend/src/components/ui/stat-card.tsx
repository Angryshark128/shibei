import type { ReactNode } from "react";

export interface StatCardProps {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  hint?: ReactNode;
}

/** 数据统计卡（布局 4.4：标题+图表子布局中的指标卡） */
export function StatCard({ label, value, icon, hint }: StatCardProps) {
  return (
    <div className="rounded-xl border border-surface-3 bg-surface-0 p-5 shadow-sm dark:border-ink-700 dark:bg-ink-700">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-sm text-ink-500 dark:text-surface-4">{label}</p>
        {icon != null && <span className="shrink-0 text-ink-400 dark:text-surface-4">{icon}</span>}
      </div>
      <p className="mt-2 text-xl font-bold text-ink-900 dark:text-surface-0">{value}</p>
      {hint != null && <p className="mt-1 truncate text-xs text-ink-400 dark:text-surface-4">{hint}</p>}
    </div>
  );
}
