import { STORAGE_KEYS } from "@/config/theme";
import enUS from "@/locales/en-US";
import zhCN from "@/locales/zh-CN";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

export type Locale = "zh-CN" | "en-US";

function readSavedLocale(): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEYS.locale);
    if (saved === "en-US" || saved === "zh-CN") return saved;
  } catch {
    // ignore
  }
  return "zh-CN";
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

export default i18n;
