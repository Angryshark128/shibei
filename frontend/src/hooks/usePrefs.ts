import { useCallback, useEffect, useState } from "react";
import { STORAGE_KEYS, TIMEZONES } from "@/config/theme";
import { currentTimezone } from "@/lib/time";

const TIMEZONE_EVENT = "shibei:timezone-change";

/** 保存时区偏好并广播，供各处时间显示即时更新（规范 05） */
export function setTimezonePref(tz: string): void {
  try {
    localStorage.setItem(STORAGE_KEYS.timezone, tz);
  } catch {
    // ignore
  }
  window.dispatchEvent(new CustomEvent(TIMEZONE_EVENT, { detail: tz }));
}

/** 订阅时区偏好变化 */
export function useTimezone(): string {
  const [tz, setTz] = useState<string>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.timezone);
    if (saved && TIMEZONES.some((t) => t.value === saved)) return saved;
    return currentTimezone();
  });

  useEffect(() => {
    const handler = () => {
      const saved = localStorage.getItem(STORAGE_KEYS.timezone);
      setTz(saved && TIMEZONES.some((t) => t.value === saved) ? saved : currentTimezone());
    };
    window.addEventListener(TIMEZONE_EVENT, handler);
    return () => window.removeEventListener(TIMEZONE_EVENT, handler);
  }, []);

  return tz;
}

/** 轮询工具：everyMs 间隔执行 fn（fn 返回 true 停止） */
export function usePolling(fn: () => Promise<boolean | void>, everyMs: number, active: boolean): void {
  const cb = useCallback(fn, [fn]);
  useEffect(() => {
    if (!active) return;
    let stopped = false;
    let timer = 0;
    const tick = async () => {
      if (stopped) return;
      try {
        const stop = await cb();
        if (stop) return;
      } catch {
        // 轮询失败静默，下次再试
      }
      if (!stopped) timer = window.setTimeout(tick, everyMs);
    };
    void tick();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [active, everyMs, cb]);
}
