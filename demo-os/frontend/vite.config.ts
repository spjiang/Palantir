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
        // 优先走 compose 服务名；如遇 DNS 异常（EAI_AGAIN），可在 compose 里改为：
        // VITE_PROXY_API_TARGET=http://host.docker.internal:7000
        target: process.env.VITE_PROXY_API_TARGET || "http://api:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
        configure: (proxy, _options) => {
          proxy.on("error", (err, _req, res) => {
            console.log("proxy error", err);
          });
          proxy.on("proxyReq", (proxyReq, req, _res) => {
            console.log("Sending Request to the Target:", req.method, req.url);
          });
          proxy.on("proxyRes", (proxyRes, req, _res) => {
            console.log("Received Response from the Target:", proxyRes.statusCode, req.url);
          });
        },
      },
      "/agent": {
        // VITE_PROXY_AGENT_TARGET=http://host.docker.internal:7001
        target: process.env.VITE_PROXY_AGENT_TARGET || "http://agent:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/agent/, ""),
        configure: (proxy, _options) => {
          proxy.on("error", (err, _req, res) => {
            console.log("proxy error", err);
          });
        },
      },
    },
  },
});


