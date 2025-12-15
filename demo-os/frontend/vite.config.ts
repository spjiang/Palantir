import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 8080,
    /**
     * 容器内运行 Vite dev server 时，浏览器访问的是宿主机:7080。
     * 为避免必须对外开放 7000/7001 端口，这里把同源的 /api、/agent 反代到 compose 网络内服务。
     */
    proxy: {
      "/api": {
        target: "http://api:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/agent": {
        target: "http://agent:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/agent/, ""),
      },
    },
  },
});


