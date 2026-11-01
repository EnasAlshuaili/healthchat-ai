/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Local-only (D-08, D-19, D-20). The browser talks only to this server, which forwards
// /api/* to FastAPI on 127.0.0.1:8000. Requests stay same-origin, so CORS stays off.
const API_PROXY = { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } };

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: API_PROXY,
    // Tests only: read docs/API_CONTRACT.md so fixtures use its exact approved wording.
    // The dev server and build keep Vite's default file access.
    ...(mode === "test" && { fs: { allow: [".", "../docs"] } }),
  },
  preview: { host: "127.0.0.1", port: 4173, strictPort: true, proxy: API_PROXY },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
  },
}));
