import { Shell } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

export interface TopBarProps {
  username: string;
}

const NAV_ITEMS: Array<{ to: string; end?: boolean; key: string }> = [
  { to: "/admin", end: true, key: "nav.overview" },
  { to: "/admin/tasks", key: "nav.tasks" },
  { to: "/admin/settings", key: "nav.settings" },
];

/** 管理端顶部导航（规范 4.3）：品牌（点击回公开报告页）+ tab 下划线选中态 */
export function TopBar({ username }: TopBarProps) {
  const { t } = useTranslation();
  return (
    <header className="sticky top-0 z-30 border-b border-surface-3 bg-surface-0 dark:border-ink-700 dark:bg-ink-700">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/reports" className="flex min-w-0 items-center gap-2.5" title={t("nav.viewReports")}>
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white dark:bg-brand-500">
            <Shell className="h-5 w-5" aria-hidden="true" />
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-base font-semibold leading-tight text-ink-900 dark:text-surface-0">
              {t("common.appName")}
            </span>
            <span className="truncate text-xs leading-tight text-ink-400 dark:text-surface-4">
              {t("common.appTagline")}
            </span>
          </span>
        </Link>
        <nav aria-label="主导航" className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors duration-150",
                  isActive
                    ? "bg-brand-50 text-brand-700 dark:bg-brand-900 dark:text-brand-300"
                    : "text-ink-500 hover:bg-surface-2 hover:text-ink-900 dark:text-surface-4 dark:hover:bg-ink-900 dark:hover:text-surface-0",
                )
              }
            >
              {t(item.key)}
            </NavLink>
          ))}
        </nav>
        <div className="flex shrink-0 items-center gap-3">
          <NavLink
            to="/reports"
            className="hidden rounded-lg px-3 py-1.5 text-sm font-medium text-ink-500 hover:bg-surface-2 hover:text-ink-900 sm:block dark:text-surface-4 dark:hover:bg-ink-900 dark:hover:text-surface-0"
          >
            {t("nav.viewReports")}
          </NavLink>
          <span className="hidden shrink-0 items-center gap-2 sm:flex">
            <span
              className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700 dark:bg-brand-900 dark:text-brand-300"
              aria-hidden="true"
            >
              {username.slice(0, 1).toUpperCase()}
            </span>
            <span className="max-w-40 truncate text-sm text-ink-500 dark:text-surface-4">{username}</span>
          </span>
        </div>
      </div>
    </header>
  );
}
