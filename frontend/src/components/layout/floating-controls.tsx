import { Globe, LogOut, Moon, Palette, Settings, Sun } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ConfirmDialog } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { THEMES, type Scheme, type ThemeId } from "@/config/theme";
import { useTheme } from "@/hooks/useTheme";
import { api } from "@/lib/api";
import { currentLocale, setLocale } from "@/i18n";
import { cn } from "@/lib/utils";

export interface FloatingControlsProps {
  onLoggedOut: () => void;
  /** 登录页等未登录场景隐藏退出按钮 */
  showLogout?: boolean;
}

/**
 * 悬浮控制按钮组（规范 7.16 最新约束）：
 * 默认折叠为单个品牌色主按钮，hover/focus 展开子按钮组（主题色→明暗→语言→退出登录），
 * 退出登录用 rose 语义色 + ConfirmDialog，成功后 Toast 跳转。
 */
export function FloatingControls({ onLoggedOut, showLogout = true }: FloatingControlsProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const { theme, scheme, applyTheme, toggleScheme } = useTheme();
  const [expanded, setExpanded] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const groupRef = useRef<HTMLDivElement>(null);

  const locale = currentLocale();

  // 点外部 / Esc 收起（规范 7.16.8）
  useEffect(() => {
    if (!expanded) return;
    function onPointerDown(e: MouseEvent) {
      if (groupRef.current && !groupRef.current.contains(e.target as Node)) {
        setExpanded(false);
        setPaletteOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setExpanded(false);
        setPaletteOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [expanded]);

  const collapse = () => {
    setExpanded(false);
    setPaletteOpen(false);
  };

  const togglePalette = () => {
    setPaletteOpen((v) => !v);
  };

  const handlePickTheme = (id: ThemeId) => {
    applyTheme(id);
    setPaletteOpen(false);
  };

  const toggleLanguage = () => {
    setLocale(locale === "en-US" ? "zh-CN" : "en-US");
  };

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await api.logout();
      toast.push("success", t("floating.logoutSuccess"));
      onLoggedOut();
    } catch {
      toast.push("error", t("errors.server"));
      setLoggingOut(false);
    }
  };

  const isDark = scheme === "dark";
  const childBase =
    "flex h-11 w-11 items-center justify-center rounded-full border bg-surface-0 shadow-lg transition-all duration-150 hover:scale-105 dark:bg-ink-700";

  const sub = (visible: boolean) =>
    cn(
      "flex flex-col items-end gap-3 transition-opacity duration-200",
      visible ? "opacity-100" : "pointer-events-none opacity-0",
    );

  return (
    <>
      <div
        ref={groupRef}
        className="fixed bottom-6 right-6 z-50"
        onMouseEnter={() => setExpanded(true)}
        onMouseLeave={collapse}
      >
        <div className="flex flex-col items-end">
          <div className={sub(expanded)}>
            {/* 主题色气泡：相对按钮左侧水平展开（规范：避免遮挡同级按钮） */}
            <div className="relative">
              <button
                type="button"
                aria-label={t("floating.themeLabel")}
                aria-expanded={paletteOpen}
                className={cn(childBase, "border-surface-3 text-ink-700 hover:bg-surface-2 dark:border-ink-900 dark:text-surface-0 dark:hover:bg-ink-900")}
                onClick={togglePalette}
              >
                <Palette className="h-5 w-5" aria-hidden="true" />
              </button>
              {paletteOpen && (
                <div
                  role="listbox"
                  aria-label={t("floating.themeLabel")}
                  className="absolute bottom-0 right-full mr-3 flex items-center gap-2 rounded-xl border border-surface-3 bg-surface-0 p-3 shadow-xl dark:border-ink-900 dark:bg-ink-700"
                >
                  {THEMES.map((th) => (
                    <button
                      key={th.id}
                      type="button"
                      role="option"
                      aria-selected={theme === th.id}
                      aria-label={th.id}
                      className={cn(
                        "h-7 w-7 rounded-full transition-transform duration-150 hover:scale-110",
                        theme === th.id && "ring-2 ring-offset-2 ring-brand-600 dark:ring-offset-ink-700",
                      )}
                      style={{ background: th.dot }}
                      onClick={() => handlePickTheme(th.id)}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* 明暗切换 */}
            <button
              type="button"
              aria-label={t("floating.schemeLabel")}
              className={cn(childBase, "border-surface-3 text-ink-700 hover:bg-surface-2 dark:border-ink-900 dark:text-surface-0 dark:hover:bg-ink-900")}
              onClick={toggleScheme}
            >
              {isDark ? <Sun className="h-5 w-5" aria-hidden="true" /> : <Moon className="h-5 w-5" aria-hidden="true" />}
            </button>

            {/* 语言切换 + 徽标 */}
            <div className="relative">
              <button
                type="button"
                aria-label={t("floating.languageLabel")}
                className={cn(childBase, "border-surface-3 text-ink-700 hover:bg-surface-2 dark:border-ink-900 dark:text-surface-0 dark:hover:bg-ink-900")}
                onClick={toggleLanguage}
              >
                <Globe className="h-5 w-5" aria-hidden="true" />
              </button>
              <span
                className="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-brand-600 text-[10px] font-bold text-white dark:bg-brand-500"
                aria-hidden="true"
              >
                {locale === "zh-CN" ? "中" : "EN"}
              </span>
            </div>

            {/* 退出登录（危险操作，rose 语义色） */}
            {showLogout && (
              <button
                type="button"
                aria-label={t("floating.logoutLabel")}
                className={cn(
                  "flex h-11 w-11 items-center justify-center rounded-full border border-rose-200 bg-rose-50 shadow-lg transition-all duration-150 hover:scale-105 dark:border-rose-900 dark:bg-rose-900",
                )}
                onClick={() => setLogoutOpen(true)}
              >
                <LogOut className="h-5 w-5 text-rose-600 dark:text-rose-400" aria-hidden="true" />
              </button>
            )}
          </div>

          {/* 主按钮（brand 实底） */}
          <button
            type="button"
            aria-label={t("common.appName")}
            aria-expanded={expanded}
            className="mt-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg transition-all duration-200 hover:scale-105 hover:bg-brand-700 dark:bg-brand-500 dark:hover:bg-brand-600"
            onClick={() => {
              setExpanded((v) => !v);
              setPaletteOpen(false);
            }}
          >
            <Settings
              className={cn("h-5 w-5 transition-transform duration-200", expanded && "rotate-45")}
              aria-hidden="true"
            />
          </button>
        </div>
      </div>

      <ConfirmDialog
        open={logoutOpen}
        onOpenChange={setLogoutOpen}
        title={t("floating.logoutConfirmTitle")}
        message={t("floating.logoutConfirmMessage")}
        confirmLabel={t("floating.logoutConfirmAction")}
        danger
        confirmLoading={loggingOut}
        onConfirm={() => void handleLogout()}
      />
    </>
  );
}

export type { Scheme };
