import { Globe, LogOut, Moon, Palette, Settings, Sun } from "lucide-react";
import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useTranslation } from "react-i18next";
import { ConfirmDialog } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { THEMES, type ThemeId } from "@/config/theme";
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
 * 展开/折叠带位移+透明度动画（200ms）；主题色气泡在按钮左侧水平展开，
 * 鼠标移入气泡不触发收起（气泡是组的 DOM 后代，离开判定用 relatedTarget）。
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

  const collapse = () => {
    setExpanded(false);
    setPaletteOpen(false);
  };

  // 点外部 / Esc 收起（规范 7.16.8）
  useEffect(() => {
    if (!expanded) return;
    function onPointerDown(e: Event) {
      if (groupRef.current && !groupRef.current.contains(e.target as Node)) {
        collapse();
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") collapse();
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [expanded]);

  /** 鼠标移出整组：目标仍在组内（含气泡）不算离开，避免点配色时自动收起。
   * 气泡打开期间不收起——relatedTarget 为 null（触屏/窗口失焦/快速移动）时
   * 旧逻辑会立刻 collapse，气泡"点开即灭"无法点选色块；改为仅点色块、
   * 再点调色板按钮或点外部/Esc 才关闭。 */
  const handleMouseLeave = (e: ReactMouseEvent<HTMLDivElement>) => {
    if (paletteOpen) return;
    const related = e.relatedTarget as Node | null;
    if (related && groupRef.current && groupRef.current.contains(related)) return;
    collapse();
  };

  const togglePalette = () => {
    setPaletteOpen((v) => {
      const next = !v;
      if (next) setExpanded(true);
      return next;
    });
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
  // 子按钮组：展开淡入+上移，折叠淡出+下移（规范 7.16.8，约 200ms）
  const panelAnim = expanded ? "opacity-100 translate-y-0 scale-100" : "pointer-events-none translate-y-2 scale-95 opacity-0";
  const childBase =
    "flex h-11 w-11 items-center justify-center rounded-full border bg-surface-0 shadow-lg transition-all duration-200 hover:scale-105 dark:bg-ink-700";

  return (
    <>
      <div
        ref={groupRef}
        className="fixed bottom-6 right-6 z-50"
        onMouseEnter={() => setExpanded(true)}
        onMouseLeave={handleMouseLeave}
      >
        <div className="flex flex-col items-end">
          <div className={cn("flex flex-col items-end gap-3 transition-all duration-200 ease-out", panelAnim)}>
            {/* 主题色按钮 + 气泡（相对按钮左侧水平展开） */}
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
              <div
                role="listbox"
                aria-label={t("floating.themeLabel")}
                className={cn(
                  "absolute bottom-0 right-full mr-3 origin-bottom-right transition-all duration-200",
                  paletteOpen ? "scale-100 opacity-100" : "pointer-events-none scale-90 opacity-0",
                )}
                onPointerDown={(e) => e.stopPropagation()}
              >
                <div className="flex items-center gap-2 rounded-xl border border-surface-3 bg-surface-0 p-3 shadow-xl dark:border-ink-900 dark:bg-ink-700">
                  {THEMES.map((th) => (
                    <button
                      key={th.id}
                      type="button"
                      role="option"
                      aria-selected={theme === th.id}
                      aria-label={th.id}
                      className={cn(
                        "h-7 w-7 rounded-full transition-transform duration-150 hover:scale-110",
                        theme === th.id && "ring-2 ring-brand-600 ring-offset-2 ring-offset-surface-0 dark:ring-offset-ink-700",
                      )}
                      style={{ background: th.dot }}
                      onClick={() => handlePickTheme(th.id)}
                    />
                  ))}
                </div>
              </div>
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
                  "flex h-11 w-11 items-center justify-center rounded-full border border-rose-200 bg-rose-50 shadow-lg transition-all duration-200 hover:scale-105 dark:border-rose-900 dark:bg-rose-900",
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
