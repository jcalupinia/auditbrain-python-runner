import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: process.env.E2E_BASE_URL || "https://auditbrain-clientes.onrender.com",
    headless: true,
    screenshot: "only-on-failure",
  },
  reporter: "list",
  timeout: 30_000,
});
