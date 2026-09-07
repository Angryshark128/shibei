import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 部署在 nginx 子路径（如 /shibei/）下，base 用环境变量控制：
//   VITE_BASE=/shibei/ npm run build
const base = process.env.VITE_BASE || "/shibei/";

export default defineConfig({
  base,
  plugins: [react()],
  resolve: {
    alias: { "@": resolve(import.meta.dirname, "src") },
  },
  server: {
    port: 5173,
    proxy: {
      // 开发模式：前端请求 /shibei/api 也转发到本地后端（后端本身无前缀）
      "/shibei/api": {
        target: "http://127.0.0.1:8000",
        rewrite: (p) => p.replace(/^\/shibei\/api/, "/api"),
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
