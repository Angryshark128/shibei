import { STORAGE_KEYS } from "@/config/theme";
import enUS from "@/locales/en-US";
import zhCN from "@/locales/zh-CN";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

export type Locale = "zh-CN" | "en-US";

/** 系统语言 → 支持的语言：en* → en-US，其余（含无偏好）→ zh-CN */
function detectSystemLocale(): Locale {
  const candidates = [navigator.language, ...(navigator.languages ?? [])];
  for (const tag of candidates) {
    if (typeof tag === "string" && tag.toLowerCase().startsWith("en")) return "en-US";
  }
  return "zh-CN";
}

/** 界面语言：用户显式选择优先，否则跟随系统语言 */
function readSavedLocale(): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEYS.locale);
    if (saved === "en-US" || saved === "zh-CN") return saved;
  } catch {
    // ignore
  }
  return detectSystemLocale();
}

export const DEFAULT_LOCALE: Locale = readSavedLocale();

i18n.use(initReactI18next).init({
  resources: {
    "zh-CN": { translation: zhCN },
    "en-US": { translation: enUS },
  },
  lng: DEFAULT_LOCALE,
  fallbackLng: "zh-CN",
  interpolation: { escapeValue: false },
});

function syncHtmlLang(locale: Locale): void {
  document.documentElement.lang = locale === "en-US" ? "en" : "zh-CN";
}

/** 浏览器 tab 标题跟随语言；changeLanguage 是异步的，故监听事件更新 */
function syncTitle(): void {
  document.title = i18n.t("common.pageTitle");
}

syncHtmlLang(DEFAULT_LOCALE);
syncTitle();
i18n.on("languageChanged", syncTitle);

export function setLocale(locale: Locale): void {
  try {
    localStorage.setItem(STORAGE_KEYS.locale, locale);
  } catch {
    // ignore
  }
  syncHtmlLang(locale);
  void i18n.changeLanguage(locale);
}

export function currentLocale(): Locale {
  return i18n.language?.startsWith("en") ? "en-US" : "zh-CN";
}

/** 报告语言：跟随界面语言（zh-CN→zh / en-US→en） */
export function currentReportLang(): "zh" | "en" {
  return currentLocale() === "en-US" ? "en" : "zh";
}

export default i18n;
