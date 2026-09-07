import { Loader2, Send, Webhook } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Input, PasswordInput } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { WebhookConfig } from "@/types";
import { cn } from "@/lib/utils";

/** Webhook 通知卡：地址 + Header 名 + Token；任务完成自动通知，可发测试 */
export function WebhookCard() {
  const { t } = useTranslation();
  const toast = useToast();
  const [cfg, setCfg] = useState<WebhookConfig | null>(null);
  const [url, setUrl] = useState("");
  const [headerKey, setHeaderKey] = useState("");
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const data = await api.webhook();
        setCfg(data);
        setUrl(data.url);
        setHeaderKey(data.header_key);
      } catch {
        toast.push("error", t("errors.server"));
      }
    })();
  }, [t, toast]);

  const save = async () => {
    setError(null);
    if (!url.trim()) {
      setError(t("settings.badUrl"));
      return;
    }
    if (!/^https?:\/\//i.test(url.trim())) {
      setError(t("settings.badUrl"));
      return;
    }
    setSaving(true);
    try {
      const saved = await api.saveWebhook({
        url: url.trim(),
        header_key: headerKey.trim(),
        token: token.trim() ? token.trim() : undefined,
      });
      setCfg(saved);
      setToken("");
      toast.push("success", t("settings.saveSuccess"));
    } catch {
      toast.push("error", t("settings.saveFail"));
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    if (!cfg?.url) {
      toast.push("warn", t("settings.webhookSaveFirst"));
      return;
    }
    setTesting(true);
    try {
      await api.testWebhook();
      toast.push("success", t("settings.webhookTestOk"));
    } catch {
      toast.push("error", t("settings.webhookTestFail"));
    } finally {
      setTesting(false);
    }
  };

  if (!cfg) {
    return (
      <Card className="flex items-center justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin text-brand-600 dark:text-brand-400" aria-hidden="true" />
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title={t("settings.webhookSection")}
        desc={t("settings.webhookDesc")}
        actions={<Webhook className="h-4 w-4 text-ink-400" aria-hidden="true" />}
      />
      <CardBody className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-ink-700 dark:text-surface-4">{t("settings.webhookEnabled")}</p>
          <Switch
            checked={cfg.enabled}
            disabled={saving}
            onCheckedChange={async (next) => {
              setSaving(true);
              try {
                const saved = await api.saveWebhook({ enabled: next });
                setCfg(saved);
              } catch {
                toast.push("error", t("settings.saveFail"));
              } finally {
                setSaving(false);
              }
            }}
            aria-label={t("settings.webhookSection")}
          />
        </div>

        <Field label={t("settings.webhookUrl")} required error={error}>
          <Input
            value={url}
            placeholder={t("settings.webhookUrlPh")}
            className={cn(error && "border-rose-500 bg-surface-0")}
            onChange={(e) => {
              setUrl(e.target.value);
              if (error) setError(null);
            }}
          />
        </Field>
        <Field label={t("settings.webhookHeaderKey")} hint={t("settings.webhookHeaderKeyPh")}>
          <Input
            value={headerKey}
            placeholder={t("settings.webhookHeaderKeyPh")}
            onChange={(e) => setHeaderKey(e.target.value)}
          />
        </Field>
        <Field
          label={t("settings.webhookToken")}
          hint={cfg.has_token ? t("settings.webhookTokenPh", { hint: cfg.token_hint }) : t("settings.webhookTokenEmpty")}
        >
          <PasswordInput
            value={token}
            autoComplete="new-password"
            placeholder={t("settings.webhookTokenPh", { hint: cfg.has_token ? cfg.token_hint : "****" })}
            onChange={(e) => setToken(e.target.value)}
          />
        </Field>

        <div className="flex justify-end gap-2 pt-2">
          <Button
            variant="secondary"
            icon={<Send className="h-4 w-4" aria-hidden="true" />}
            loading={testing}
            onClick={() => void test()}
          >
            {t("settings.webhookTest")}
          </Button>
          <Button loading={saving} icon={<Webhook className="h-4 w-4" aria-hidden="true" />} onClick={() => void save()}>
            {t("common.save")}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
