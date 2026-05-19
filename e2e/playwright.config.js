import { defineConfig } from "@playwright/test";

/**
 * E2E + visual-QA config for the AuditBrain React/Vite frontend.
 *
 * The backend is a remote service, so every test stubs the API via
 * `page.route` (see tests/helpers.js). VITE_API_BASE is pinned to the
 * dev-server origin so requests stay same-origin and are easy to match.
 *
 * Projects:
 *  - functional      : runs the behavioural specs (desktop viewport).
 *  - visual-desktop   : visual-regression spec at desktop size.
 *  - visual-tablet    : visual-regression spec at tablet size.
 *  - visual-mobile    : visual-regression spec at mobile size.
 *
 * Visual baselines live in e2e/screenshots/baseline/<project>/ and are
 * compared with toHaveScreenshot(). Human-viewable captures are written
 * to e2e/screenshots/actual/<project>/ for artifact upload.
 */
const PORT = 5173;
const BASE_URL = `http://localhost:${PORT}`;

const VIEWPORTS = {
  desktop: { width: 1280, height: 800 },
  tablet: { width: 768, height: 1024 },
  mobile: { width: 390, height: 844 },
};

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  snapshotPathTemplate: "screenshots/baseline/{projectName}/{arg}{ext}",
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.02,
      animations: "disabled",
    },
  },
  use: {
    baseURL: BASE_URL,
    trace: "on",
    screenshot: "on",
    video: "on",
  },
  projects: [
    {
      name: "functional",
      testIgnore: /visual\.spec\.js/,
      use: { browserName: "chromium", viewport: VIEWPORTS.desktop },
    },
    {
      name: "visual-desktop",
      testMatch: /visual\.spec\.js/,
      use: { browserName: "chromium", viewport: VIEWPORTS.desktop },
    },
    {
      name: "visual-tablet",
      testMatch: /visual\.spec\.js/,
      use: { browserName: "chromium", viewport: VIEWPORTS.tablet },
    },
    {
      name: "visual-mobile",
      testMatch: /visual\.spec\.js/,
      use: { browserName: "chromium", viewport: VIEWPORTS.mobile },
    },
  ],
  webServer: {
    command:
      "npm --prefix ../frontend run dev -- --port " + PORT + " --strictPort",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
    env: {
      VITE_API_BASE: BASE_URL,
    },
  },
});
