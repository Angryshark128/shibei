import { Shell } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Field, Input, PasswordInput } from "@/components/ui/input";
import { ApiError, AuthError } from "@/lib/api";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

export interface LoginPageProps {
  onLogin: (username: string) => void;
}

/** 登录页（布局 3.2 居中卡片）：不显示导航/侧边栏，保留右下角悬浮组 */
export function LoginPage({ onLogin }: LoginPageProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    if (!username.trim() || !password) {
      setError(t("login.badCredentials"));
      return;
    }
    setSubmitting(true);
    try {
      await api.login(username.trim(), password);
      toast.push("success", t("login.success"));
      onLogin(username.trim());
    } catch (err) {
      if (err instanceof AuthError || (err instanceof ApiError && (err.code === "bad_credentials" || err.status === 401))) {
        setError(t("login.badCredentials"));
      } else {
        toast.push("error", t("login.network"));
      }
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-2 px-4 dark:bg-ink-900">
      <div className="w-full max-w-sm">
        <div className="mx-auto mb-6 flex h-12 w-12 items-center justify-center rounded-lg bg-brand-600 text-white dark:bg-brand-500">
          <Shell className="h-6 w-6" aria-hidden="true" />
        </div>
        <div className="rounded-xl border border-surface-3 bg-surface-0 p-8 shadow-lg dark:border-ink-700 dark:bg-ink-700">
          <h1 className="text-center text-xl font-bold text-ink-900 dark:text-surface-0">{t("login.title")}</h1>
          <p className="mt-1 text-center text-sm text-ink-500 dark:text-surface-4">{t("login.subtitle")}</p>
          <form onSubmit={(e) => void submit(e)} className="mt-6 space-y-4">
            <Field label={t("login.username")} required error={error}>
              <Input
                autoFocus
                autoComplete="username"
                value={username}
                disabled={submitting}
                placeholder={t("login.usernamePh")}
                className={cn(error && "border-rose-500 bg-surface-0")}
                onChange={(e) => {
                  setUsername(e.target.value);
                  if (error) setError(null);
                }}
              />
            </Field>
            <Field label={t("login.password")} required error={error}>
              <PasswordInput
                autoComplete="current-password"
                value={password}
                disabled={submitting}
                placeholder={t("login.passwordPh")}
                className={cn(error && "border-rose-500 bg-surface-0")}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (error) setError(null);
                }}
              />
            </Field>
            <Button type="submit" loading={submitting} disabled={submitting} className="w-full">
              {t("login.submit")}
            </Button>
          </form>
        </div>
        <p className="mt-6 text-center text-xs text-ink-400 dark:text-surface-4">{t("common.appTagline")}</p>
      </div>
    </div>
  );
}
