import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the AuditBrain React/Vite frontend.
 *
 * The backend is a remote service, so every test stubs the API via
 * `page.route` (see tests/helpers.js). VITE_API_BASE is pinned to the
 * dev-server origin so requests stay same-origin and are easy to match.
 */
const PORT = 5173;
const BASE_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm --prefix ../frontend run dev -- --port " + PORT + " --strictPort",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
    env: {
      VITE_API_BASE: BASE_URL,
    },
  },
});
