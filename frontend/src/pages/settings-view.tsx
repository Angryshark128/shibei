import { KeyRound, Save, ShieldCheck, Zap } from "lucide-react";
import type { TFunction } from "i18next";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Input, PasswordInput } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { PageHeader } from "@/components/layout/page-header";
import { ErrorBlock } from "@/components/ui/error";
import { ScheduleCard } from "@/components/business/schedule-card";
import { WebhookCard } from "@/components/business/webhook-card";
import { TIMEZONES } from "@/config/theme";
import { setTimezonePref } from "@/hooks/usePrefs";
import { ApiError, api } from "@/lib/api";
import type { AppConfig } from "@/types";
import { cn } from "@/lib/utils";

function errCodeText(code: string, t: TFunction): string {
  switch (code) {
    case "bad_credentials":
      return t("settings.wrongPassword");
    case "weak_password":
      return t("settings.passwordTooShort");
    case "bad_url":
      return t("settings.badUrl");
    default:
      return t("errors.server");
  }
}

/** 设置页（布局 4.4）：AI 模型 / 账号 / 数据来源 / 显示时区 */
export function SettingsView() {
  const { t } = useTranslation();
  const toast = useToast();

  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loadError, setLoadError] = useState(false);

  // LLM 表单
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [maxTokens, setMaxTokens] = useState("4096");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);

  // 密码表单
  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [changingPwd, setChangingPwd] = useState(false);

  // 来源开关（按 name 记录保存中状态）
  const [toggling, setToggling] = useState<Record<string, boolean>>({});

  // 报告语言（新分析生成报告的语言）
  const [reportLang, setReportLang] = useState<"zh" | "en">("zh");

  useEffect(() => {
    void api
      .reportLang()
      .then((d) => setReportLang(d.lang))
      .catch(() => {
        // 读取失败保持默认中文
      });
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const data = await api.getConfig();
        setConfig(data);
        setBaseUrl(data.llm.base_url);
        setModel(data.llm.model);
        setMaxTokens(String(data.llm.max_tokens));
        setLoadError(false);
      } catch {
        setLoadError(true);
      }
    })();
  }, []);

  const saveLlm = async (e: FormEvent) => {
    e.preventDefault();
    setLlmError(null);
    if (saving) return;
    if (!baseUrl.trim() || !model.trim()) {
      setLlmError(t("settings.badUrl"));
      return;
    }
    setSaving(true);
    try {
      const payload: {
        llm: { base_url: string; model: string; max_tokens: number };
        api_key?: string;
      } = {
        llm: { base_url: baseUrl.trim(), model: model.trim(), max_tokens: Math.max(256, Number(maxTokens) || 4096) },
      };
      if (apiKey.trim()) {
        payload.api_key = apiKey.trim();
      }
      await api.saveConfig(payload);
      toast.push("success", t("settings.saveSuccess"));
      setApiKey("");
      const fresh = await api.getConfig();
      setConfig(fresh);
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "";
      toast.push("error", errCodeText(code, t), err instanceof ApiError ? err.message : undefined);
    } finally {
      setSaving(false);
    }
  };

  const testLlm = async () => {
    setLlmError(null);
    if (!baseUrl.trim() || !model.trim()) {
      setLlmError(t("settings.badUrl"));
      return;
    }
    setTesting(true);
    try {
      const res = await api.testConfig({
        llm: { base_url: baseUrl.trim(), model: model.trim() },
        api_key: apiKey.trim() || undefined,
      });
      toast.push("success", t("settings.llmTestOk", { ms: res.latency_ms }));
    } catch (err) {
      if (err instanceof ApiError) {
        toast.push("error", t("settings.llmTestFail"), err.message || undefined);
      } else {
        toast.push("error", t("settings.llmTestFail"));
      }
    } finally {
      setTesting(false);
    }
  };

  const changePassword = async (e: FormEvent) => {
    e.preventDefault();
    setPwdError(null);
    if (newPwd.length < 8) {
      setPwdError(t("settings.passwordTooShort"));
      return;
    }
    if (newPwd !== confirmPwd) {
      setPwdError(t("settings.passwordMismatch"));
      return;
    }
    setChangingPwd(true);
    try {
      await api.changePassword(currentPwd, newPwd);
      toast.push("success", t("settings.passwordChanged"));
      setCurrentPwd("");
      setNewPwd("");
      setConfirmPwd("");
    } catch (err) {
      if (err instanceof ApiError) {
        setPwdError(errCodeText(err.code, t));
        if (err.code !== "bad_credentials" && err.code !== "weak_password") {
          toast.push("error", errCodeText(err.code, t));
        }
      } else {
        toast.push("error", t("settings.saveFailedNetwork"));
      }
    } finally {
      setChangingPwd(false);
    }
  };

  const toggleSource = async (name: string, enabled: boolean) => {
    setToggling((m) => ({ ...m, [name]: true }));
    try {
      await api.setSource(name, enabled);
      setConfig((c) => (c ? { ...c, sources: c.sources.map((s) => (s.name === name ? { ...s, enabled } : s)) } : c));
    } catch {
      toast.push("error", t("settings.saveFailedNetwork"));
    } finally {
      setToggling((m) => ({ ...m, [name]: false }));
    }
  };

  if (loadError && !config) {
    return <ErrorBlock title={t("settings.title")} desc={t("errors.server")} onRetry={() => window.location.reload()} />;
  }
  if (!config) {
    return (
      <div className="space-y-3 py-4" aria-busy="true">
        <div className="h-40 w-full animate-pulse rounded-xl bg-surface-2 dark:bg-ink-900" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title={t("settings.title")} desc={t("settings.desc")} />

      {/* AI 模型 */}
      <Card>
        <CardHeader title={t("settings.llmSection")} desc={t("settings.llmDesc")} />
        <CardBody>
          <form onSubmit={(e) => void saveLlm(e)} className="space-y-4">
            <Field label={t("settings.baseUrl")} required hint={config.llm.base_url || t("common.notConfigured")}>
              <Input
                value={baseUrl}
                placeholder={t("settings.baseUrlPh")}
                onChange={(e) => setBaseUrl(e.target.value)}
                className={cn(llmError && "border-rose-500 bg-surface-0")}
              />
            </Field>
            <Field label={t("settings.model")} required>
              <Input value={model} placeholder={t("settings.modelPh")} onChange={(e) => setModel(e.target.value)} />
            </Field>
            <Field label={t("settings.maxTokens")}>
              <Input
                type="number"
                min={256}
                step={256}
                value={maxTokens}
                onChange={(e) => setMaxTokens(e.target.value)}
                className="max-w-48"
              />
            </Field>
            <Field
              label={t("settings.apiKey")}
              hint={config.llm.has_api_key ? t("settings.apiKeyPh", { hint: config.llm.api_key_hint }) : t("settings.apiKeyEmpty")}
            >
              <PasswordInput
                value={apiKey}
                autoComplete="new-password"
                placeholder={t("settings.apiKeyPh", { hint: config.llm.has_api_key ? config.llm.api_key_hint : "****" })}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </Field>
            {llmError && (
              <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">
                {llmError}
              </p>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="secondary"
                icon={<Zap className="h-4 w-4" aria-hidden="true" />}
                loading={testing}
                onClick={() => void testLlm()}
              >
                {t("settings.llmTest")}
              </Button>
              <Button type="submit" loading={saving} icon={<Save className="h-4 w-4" aria-hidden="true" />}>
                {t("common.save")}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>

      {/* 每日定时 + Webhook */}
      <ScheduleCard />
      <WebhookCard />

      {/* 数据来源 */}
      <Card>
        <CardHeader
          title={t("settings.sourcesSection")}
          desc={t("settings.sourcesDesc")}
          actions={<KeyRound className="h-4 w-4 text-ink-400" aria-hidden="true" />}
        />
        <CardBody className="divide-y divide-surface-3 dark:divide-ink-900">
          {config.sources.map((s) => (
            <div key={s.name} className="flex items-start justify-between gap-4 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink-900 dark:text-surface-0">{s.name}</p>
                <p className="mt-0.5 break-words text-xs leading-5 text-ink-400 dark:text-surface-4">
                  {s.nodes.join(" · ")}
                  {!s.enabled && (
                    <span className="ml-2 rounded bg-surface-2 px-1.5 py-0.5 text-ink-400 dark:bg-ink-900">{t("settings.sourceDisabled")}</span>
                  )}
                </p>
              </div>
              <Switch
                checked={s.enabled}
                disabled={toggling[s.name]}
                onCheckedChange={(next) => void toggleSource(s.name, next)}
                aria-label={`${s.name} ${t("settings.sourceEnabled")}`}
              />
            </div>
          ))}
        </CardBody>
      </Card>

      {/* 账号 */}
      <Card>
        <CardHeader title={t("settings.accountSection")} desc={t("settings.accountDesc")} />
        <CardBody>
          <form onSubmit={(e) => void changePassword(e)} className="space-y-4">
            <Field label={t("settings.newPassword")} required>
              <PasswordInput
                value={newPwd}
                autoComplete="new-password"
                onChange={(e) => setNewPwd(e.target.value)}
                className={cn(pwdError && "border-rose-500 bg-surface-0")}
              />
            </Field>
            <Field label={t("settings.confirmPassword")} required>
              <PasswordInput
                value={confirmPwd}
                autoComplete="new-password"
                onChange={(e) => setConfirmPwd(e.target.value)}
                className={cn(pwdError && "border-rose-500 bg-surface-0")}
              />
            </Field>
            <Field label={t("settings.currentPassword")} required>
              <PasswordInput
                value={currentPwd}
                autoComplete="current-password"
                onChange={(e) => setCurrentPwd(e.target.value)}
              />
            </Field>
            {pwdError && (
              <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">
                {pwdError}
              </p>
            )}
            <div className="flex justify-end pt-2">
              <Button type="submit" variant="secondary" loading={changingPwd} icon={<ShieldCheck className="h-4 w-4" aria-hidden="true" />}>
                {t("settings.changePassword")}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>

      {/* 显示时区 */}
      <Card>
        <CardHeader title={t("settings.timezoneSection")} desc={t("settings.timezoneDesc")} />
        <CardBody>
          <div className="max-w-xs">
            <Select
              aria-label={t("settings.timezoneSection")}
              alignUp
              value={(() => {
                const saved = localStorage.getItem("timezone");
                return saved && TIMEZONES.some((z) => z.value === saved) ? saved : "Asia/Shanghai";
              })()}
              options={TIMEZONES}
              onChange={(v) => {
                setTimezonePref(v);
                toast.push("success", t("settings.saveSuccess"));
              }}
            />
          </div>
        </CardBody>
      </Card>

      {/* 报告语言 */}
      <Card>
        <CardHeader title={t("settings.reportLangSection")} desc={t("settings.reportLangDesc")} />
        <CardBody>
          <p className="mb-2 text-xs leading-5 text-ink-400 dark:text-surface-4">{t("settings.reportLangHint")}</p>
          <div className="max-w-xs">
            <Select
              aria-label={t("settings.reportLangSection")}
              alignUp
              value={reportLang}
              options={[
                { value: "zh", label: t("settings.reportLangZh") },
                { value: "en", label: t("settings.reportLangEn") },
              ]}
              onChange={(v) => {
                const lang = v as "zh" | "en";
                setReportLang(lang);
                void api
                  .saveReportLang(lang)
                  .then(() => toast.push("success", t("settings.saveSuccess")))
                  .catch(() => toast.push("error", t("settings.saveFailedNetwork")));
              }}
            />
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
