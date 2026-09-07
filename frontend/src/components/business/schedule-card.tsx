import { CalendarClock, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { ScheduleConfig } from "@/types";

const HOURS = Array.from({ length: 24 }, (_, h) => ({
  value: String(h).padStart(2, "0"),
  label: String(h).padStart(2, "0"),
}));
const MINUTES = Array.from({ length: 12 }, (_, i) => ({
  value: String(i * 5).padStart(2, "0"),
  label: String(i * 5).padStart(2, "0"),
}));

/** 每日定时调度卡：启用开关（即时保存）+ 时间选择（时:分，5 分钟步进） */
export function ScheduleCard() {
  const { t } = useTranslation();
  const toast = useToast();
  const [cfg, setCfg] = useState<ScheduleConfig | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        setCfg(await api.schedule());
      } catch {
        toast.push("error", t("errors.server"));
      }
    })();
  }, [t, toast]);

  const apply = async (patch: { enabled?: boolean; time?: string }) => {
    setSaving(true);
    try {
      const saved = await api.saveSchedule(patch);
      setCfg(saved);
      toast.push("success", t("settings.saveSuccess"));
    } catch {
      toast.push("error", t("settings.saveFail"));
    } finally {
      setSaving(false);
    }
  };

  if (!cfg) {
    return (
      <Card className="flex items-center justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin text-brand-600 dark:text-brand-400" aria-hidden="true" />
      </Card>
    );
  }

  const [hh, mm] = (cfg.time || "00:00").split(":");
  const enabled = cfg.enabled;

  return (
    <Card>
      <CardHeader
        title={t("settings.scheduleSection")}
        desc={t("settings.scheduleDesc")}
        actions={<CalendarClock className="h-4 w-4 text-ink-400" aria-hidden="true" />}
      />
      <CardBody className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-ink-700 dark:text-surface-4">{t("settings.scheduleEnabled")}</p>
          <Switch
            checked={enabled}
            disabled={saving}
            onCheckedChange={(next) => void apply({ enabled: next })}
            aria-label={t("settings.scheduleEnabled")}
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-ink-700 dark:text-surface-4">{t("settings.scheduleTime")}</span>
          <div className="w-24">
            <Select
              label={t("settings.scheduleTime")}
              value={HOURS.some((o) => o.value === hh) ? hh : "00"}
              options={HOURS}
              disabled={!enabled || saving}
              onChange={(v) => void apply({ time: `${v}:${mm}` })}
            />
          </div>
          <span className="text-sm text-ink-500 dark:text-surface-4">:</span>
          <div className="w-24">
            <Select
              label={t("settings.scheduleTime")}
              value={MINUTES.some((o) => o.value === mm) ? mm : "00"}
              options={MINUTES}
              disabled={!enabled || saving}
              onChange={(v) => void apply({ time: `${hh}:${v}` })}
            />
          </div>
        </div>
        <p className="text-xs text-ink-400 dark:text-surface-4">
          {t("settings.scheduleTimeHint")}
          {" · "}
          {cfg.last_fired ? t("settings.scheduleLastFired", { date: cfg.last_fired }) : t("settings.scheduleNever")}
        </p>
      </CardBody>
    </Card>
  );
}
