import { useCallback, useState } from "react";
import { DEFAULT_THEME, STORAGE_KEYS, type Scheme, type ThemeId } from "@/config/theme";

function readTheme(): ThemeId {
  const v = document.documentElement.getAttribute("data-theme");
  if (v === "indigo" || v === "emerald" || v === "rose" || v === "amber" || v === "slate") return v;
  return DEFAULT_THEME;
}

function readScheme(): Scheme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

/** 主题双轴（规范 03）：theme=主题色（html[data-theme]），scheme=明暗（html.dark） */
export function useTheme() {
  const [theme, setTheme] = useState<ThemeId>(readTheme);
  const [scheme, setScheme] = useState<Scheme>(readScheme);

  const applyTheme = useCallback((next: ThemeId) => {
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(STORAGE_KEYS.theme, next);
    } catch {
      // ignore
    }
    setTheme(next);
  }, []);

  const applyScheme = useCallback((next: Scheme) => {
    document.documentElement.classList.toggle("dark", next === "dark");
    try {
      localStorage.setItem(STORAGE_KEYS.colorScheme, next);
    } catch {
      // ignore
    }
    setScheme(next);
  }, []);

  const toggleScheme = useCallback(() => {
    applyScheme(scheme === "dark" ? "light" : "dark");
  }, [applyScheme, scheme]);

  return { theme, scheme, applyTheme, applyScheme, toggleScheme };
}
