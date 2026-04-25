import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": resolve(__dirname, "src") },
  },
  test: {
    environment: "happy-dom",
    globals: false,
    css: false,
    setupFiles: [],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
