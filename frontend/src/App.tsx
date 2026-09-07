import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { FloatingControls } from "@/components/layout/floating-controls";
import { TopBar } from "@/components/layout/topbar";
import { api } from "@/lib/api";
import { HelpView } from "@/pages/help-view";
import { LoginPage } from "@/pages/login-page";
import { ReportsView } from "@/pages/reports-view";
import { SettingsView } from "@/pages/settings-view";
import { TasksView } from "@/pages/tasks-view";
import type { ViewId } from "@/types";

export default function App() {
  const [user, setUser] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [view, setView] = useState<ViewId>("reports");

  // 启动时校验会话
  useEffect(() => {
    void (async () => {
      try {
        const me = await api.me();
        setUser(me.username);
      } catch {
        setUser(null);
      } finally {
        setChecking(false);
      }
    })();
  }, []);

  // 任意 API 401（会话过期）→ 回登录页
  const handleUnauthorized = useCallback(() => {
    setUser(null);
    setView("reports");
  }, []);
  useEffect(() => {
    window.addEventListener("shibei:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("shibei:unauthorized", handleUnauthorized);
  }, [handleUnauthorized]);

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-2 dark:bg-ink-900">
        <Loader2 className="h-6 w-6 animate-spin text-brand-600 dark:text-brand-400" aria-hidden="true" />
      </div>
    );
  }

  if (!user) {
    return (
      <>
        <LoginPage onLogin={(name) => setUser(name)} />
        {/* 登录页保留悬浮组（主题/明暗/语言），无退出按钮（规范布局 3.3） */}
        <FloatingControls showLogout={false} onLoggedOut={() => setUser(null)} />
      </>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar view={view} onNavigate={setView} username={user} />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        {view === "reports" && <ReportsView onGoTasks={() => setView("tasks")} />}
        {view === "tasks" && <TasksView />}
        {view === "settings" && <SettingsView />}
        {view === "help" && <HelpView onBack={() => setView("reports")} />}
      </main>
      <FloatingControls onLoggedOut={() => setUser(null)} />
    </div>
  );
}
