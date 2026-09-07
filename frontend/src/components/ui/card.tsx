import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

/** 卡片（规范 7.2）：surface-0 底 + border-surface-3 + rounded-xl */
export function Card({ className, children, ...rest }: CardProps) {
  return (
    <div
      className={cn("rounded-xl border border-surface-3 bg-surface-0 shadow-sm dark:border-ink-700 dark:bg-ink-700", className)}
      {...rest}
    >
      {children}
    </div>
  );
}

export interface CardHeaderProps {
  title?: ReactNode;
  desc?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function CardHeader({ title, desc, actions, className }: CardHeaderProps) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-3 px-6 pt-6 pb-4", className)}>
      <div className="min-w-0">
        {title != null && <h3 className="text-base font-semibold text-ink-900 dark:text-surface-0">{title}</h3>}
        {desc != null && <p className="mt-1 text-sm text-ink-500 dark:text-surface-4">{desc}</p>}
      </div>
      {actions != null && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function CardBody({ className, children, ...rest }: CardProps) {
  return (
    <div className={cn("px-6 pb-6", className)} {...rest}>
      {children}
    </div>
  );
}
