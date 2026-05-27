import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E para AuditBrain v2.
 *
 * Arranca el frontend en modo dev (Vite) con VITE_API_BASE apuntando al
 * propio origen, así api.js emite rutas relativas y las peticiones del
 * navegador se interceptan con page.route() en cada spec (sin Render).
 *
 * Esto mantiene los tests deterministas y los hace correr offline.
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    actionTimeout: 5_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev -- --port 5173 --strictPort",
    cwd: "../frontend",
    port: 5173,
    timeout: 60_000,
    reuseExistingServer: !process.env.CI,
    env: {
      VITE_API_BASE: "",
    },
  },
});
