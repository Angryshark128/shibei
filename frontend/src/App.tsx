import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { FloatingControls } from "@/components/layout/floating-controls";
import { TopBar } from "@/components/layout/topbar";
import { api } from "@/lib/api";
import { AdminOverview } from "@/pages/admin-overview";
import { HelpView } from "@/pages/help-view";
import { LoginPage } from "@/pages/login-page";
import { ReportsIndex, ReportsView } from "@/pages/reports-view";
import { SettingsView } from "@/pages/settings-view";
import { TasksView } from "@/pages/tasks-view";

/** 公开页外壳：页面背景容器（报告页自带侧边栏品牌区与导航） */
function PublicShell({ children }: { children: ReactNode }) {
  return <div className="min-h-screen bg-surface-2 dark:bg-ink-900">{children}</div>;
}

/** /admin/*：登录守卫 + 管理壳（总览/运行历史/设置/帮助） */
function AdminRoute() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<"checking" | "anon" | "authed">("checking");
  const [username, setUsername] = useState("");

  const handleUnauthorized = useCallback(() => {
    setStatus("anon");
    setUsername("");
  }, []);

  useEffect(() => {
    let mounted = true;
    void api
      .me()
      .then((me) => {
        if (!mounted) return;
        setUsername(me.username);
        setStatus("authed");
      })
      .catch(() => {
        if (mounted) setStatus("anon");
      });
    window.addEventListener("shibei:unauthorized", handleUnauthorized);
    return () => {
      mounted = false;
      window.removeEventListener("shibei:unauthorized", handleUnauthorized);
    };
  }, [handleUnauthorized]);

  if (status === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-2 dark:bg-ink-900">
        <Loader2 className="h-6 w-6 animate-spin text-brand-600 dark:text-brand-400" aria-hidden="true" />
      </div>
    );
  }

  if (status === "anon") {
    return (
      <>
        <LoginPage
          onLogin={(name) => {
            setUsername(name);
            setStatus("authed");
          }}
        />
        {/* 登录页保留悬浮组（主题/明暗/语言），无退出按钮 */}
        <FloatingControls showLogout={false} onLoggedOut={() => undefined} />
      </>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar username={username} />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        <Routes>
          <Route index element={<AdminOverview />} />
          <Route path="tasks" element={<TasksView />} />
          <Route path="settings" element={<SettingsView />} />
          <Route path="help" element={<HelpView onBack={() => navigate("/admin")} />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </main>
      <FloatingControls onLoggedOut={handleUnauthorized} />
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/reports" replace />} />
      <Route
        path="/reports"
        element={
          <PublicShell>
            <ReportsIndex />
          </PublicShell>
        }
      />
      <Route
        path="/reports/:name"
        element={
          <PublicShell>
            <ReportsView />
          </PublicShell>
        }
      />
      <Route path="/admin/*" element={<AdminRoute />} />
      <Route path="*" element={<Navigate to="/reports" replace />} />
    </Routes>
  );
}
