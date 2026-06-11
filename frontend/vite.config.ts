import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // 前端 1688、後端 1689（見 scripts/dev.sh）。後端埠可用 VITE_BACKEND_PORT 覆寫。
    port: 1688,
    proxy: {
      "/api": {
        // 用 127.0.0.1 而非 localhost：Node 18+ 會把 localhost 優先解析為 IPv6 ::1，
        // 但 uvicorn 綁的是 0.0.0.0（僅 IPv4），會導致 ECONNREFUSED ::1:1689
        target: `http://127.0.0.1:${process.env.VITE_BACKEND_PORT ?? 1689}`,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
