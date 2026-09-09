import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@/i18n";
import "@/styles/index.css";
import App from "@/App";
import { ToastProvider } from "@/components/ui/toast";

// 部署子路径（如 /apps/shibei/）作为路由 basename；根路径部署时为空串
const routeBase = import.meta.env.BASE_URL.replace(/\/+$/, "");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename={routeBase}>
      <ToastProvider>
        <App />
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
