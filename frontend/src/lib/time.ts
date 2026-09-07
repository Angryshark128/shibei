import dayjs from "dayjs";
import timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";
import { STORAGE_KEYS } from "@/config/theme";
import i18n from "@/i18n";

dayjs.extend(utc);
dayjs.extend(timezone);

/** 用户时区（规范 05：6 固定时区之一；未设置取浏览器） */
export function currentTimezone(): string {
  const saved = localStorage.getItem(STORAGE_KEYS.timezone);
  if (saved && saved !== "auto") return saved;
  return dayjs.tz.guess() || "Asia/Shanghai";
}

/** 统一 24 小时制格式：YYYY-MM-DD HH:mm（规范 05） */
export function formatTime(value: number | string | Date | null | undefined, tz?: string): string {
  if (value == null) return "—";
  const zone = tz || currentTimezone();
  return dayjs(value).tz(zone).format("YYYY-MM-DD HH:mm");
}

/** 短格式：MM-DD HH:mm（紧凑表格列用） */
export function formatTimeShort(value: number | string | Date | null | undefined, tz?: string): string {
  if (value == null) return "—";
  const zone = tz || currentTimezone();
  return dayjs(value).tz(zone).format("MM-DD HH:mm");
}

/** 时长（秒）→ 人类可读 */
export function formatDuration(startedAt: number | null | undefined, finishedAt: number | null | undefined): string {
  if (startedAt == null) return "—";
  const end = finishedAt ?? Date.now() / 1000;
  const secs = Math.max(0, Math.round(end - startedAt));
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return s > 0 ? `${m}m${s}s` : `${m}m`;
}

/** 相对时间（文案走 i18n） */
export function formatRelative(value: number | null | undefined): string {
  if (value == null) return "—";
  const diff = Date.now() / 1000 - value;
  const t = i18n.t.bind(i18n);
  if (diff < 60) return t("common.justNow");
  if (diff < 3600) return t("common.minutesAgo", { n: Math.floor(diff / 60) });
  if (diff < 86400) return t("common.hoursAgo", { n: Math.floor(diff / 3600) });
  return formatTimeShort(value);
}
