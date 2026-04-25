import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

const DASHBOARD_PORT = 7860;
const STUDIO_PORT = 7870;

export default defineConfig(({ mode }) => {
  const isStudio = mode === "studio";
  const entry = isStudio ? "index.studio.html" : "index.dashboard.html";

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": resolve(__dirname, "src"),
      },
    },
    server: {
      port: isStudio ? 5174 : 5173,
      strictPort: true,
      open: `/${entry}`,
      proxy: {
        "/runs": { target: `http://127.0.0.1:${DASHBOARD_PORT}`, changeOrigin: true },
        "/graph": { target: `http://127.0.0.1:${DASHBOARD_PORT}`, changeOrigin: true },
        "/stream": { target: `http://127.0.0.1:${DASHBOARD_PORT}`, changeOrigin: true },
        "/stats": { target: `http://127.0.0.1:${DASHBOARD_PORT}`, changeOrigin: true },
        "/evolution": { target: `http://127.0.0.1:${DASHBOARD_PORT}`, changeOrigin: true },
        "/_ingest": { target: `http://127.0.0.1:${DASHBOARD_PORT}`, changeOrigin: true },
        "/api": { target: `http://127.0.0.1:${isStudio ? STUDIO_PORT : DASHBOARD_PORT}`, changeOrigin: true },
        "/jobs": { target: `http://127.0.0.1:${STUDIO_PORT}`, changeOrigin: true },
      },
    },
    build: {
      target: "es2022",
      sourcemap: true,
      rollupOptions: {
        input: { main: resolve(__dirname, entry) },
        output: {
          entryFileNames: "assets/[name]-[hash].js",
          chunkFileNames: "assets/[name]-[hash].js",
          assetFileNames: "assets/[name]-[hash][extname]",
        },
      },
    },
  };
});
