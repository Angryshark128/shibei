export type ThemeId = "indigo" | "emerald" | "rose" | "amber" | "slate";

export const THEMES: Array<{ id: ThemeId; dot: string }> = [
  { id: "indigo", dot: "#4f46e5" },
  { id: "emerald", dot: "#059669" },
  { id: "rose", dot: "#e11d48" },
  { id: "amber", dot: "#d97706" },
  { id: "slate", dot: "#475569" },
];

export type Scheme = "light" | "dark";

export const SCHEMES: Array<{ id: Scheme; icon: "sun" | "moon" }> = [
  { id: "light", icon: "sun" },
  { id: "dark", icon: "moon" },
];

export const DEFAULT_THEME: ThemeId = "indigo";
export const DEFAULT_SCHEME: Scheme = "light";

/** 显示时区选项（固定 2 个：上海 + UTC） */
export const TIMEZONES: Array<{ label: string; value: string }> = [
  { label: "上海 (UTC+8)", value: "Asia/Shanghai" },
  { label: "UTC (UTC+0)", value: "UTC" },
];

export const STORAGE_KEYS = {
  theme: "theme",
  colorScheme: "colorScheme",
  locale: "locale",
  timezone: "timezone",
} as const;
