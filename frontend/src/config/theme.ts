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

/** 规范 05：可选时区固定 6 个 */
export const TIMEZONES: Array<{ label: string; value: string }> = [
  { label: "Asia/Shanghai", value: "Asia/Shanghai" },
  { label: "Asia/Tokyo", value: "Asia/Tokyo" },
  { label: "Asia/Singapore", value: "Asia/Singapore" },
  { label: "Europe/London", value: "Europe/London" },
  { label: "America/New_York", value: "America/New_York" },
  { label: "America/Los_Angeles", value: "America/Los_Angeles" },
];

export const STORAGE_KEYS = {
  theme: "theme",
  colorScheme: "colorScheme",
  locale: "locale",
  timezone: "timezone",
} as const;
