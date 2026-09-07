import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

type BadgeVariant = "success" | "warn" | "danger" | "brand" | "neutral";

const VARIANT_CLASS: Record<BadgeVariant, { wrap: string; dot: string }> = {
  success: { wrap: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300", dot: "bg-emerald-600" },
  warn: { wrap: "bg-amber-50 text-amber-700 dark:bg-amber-900 dark:text-amber-300", dot: "bg-amber-600" },
  danger: { wrap: "bg-rose-50 text-rose-700 dark:bg-rose-900 dark:text-rose-300", dot: "bg-rose-600" },
  brand: { wrap: "bg-brand-50 text-brand-700 dark:bg-brand-900 dark:text-brand-300", dot: "bg-brand-600" },
  neutral: { wrap: "bg-surface-2 text-ink-700 dark:bg-ink-900 dark:text-surface-4", dot: "bg-ink-500" },
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  /** 前置圆点（规范 7.5：圆点/图标只用一种） */
  dot?: boolean;
  /** 前置图标（Lucide，跟随文字色） */
  icon?: ReactNode;
}

/** 状态标签（规范 7.5）：语义色仅限 success/warn/danger/brand/neutral */
export function Badge({ variant = "neutral", dot, icon, className, children, ...rest }: BadgeProps) {
  const v = VARIANT_CLASS[variant];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium", v.wrap, className)} {...rest}>
      {icon}
      {dot && !icon && <span className={cn("h-1.5 w-1.5 rounded-full", v.dot)} aria-hidden="true" />}
      {children}
    </span>
  );
}
