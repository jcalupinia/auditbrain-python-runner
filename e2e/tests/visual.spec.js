import { test, expect } from "@playwright/test";
import { mockApi, login, ADMIN_USER, BASIC_USER } from "./helpers.js";

/**
 * Visual QA: for every key screen we
 *   1. write a human-viewable PNG to screenshots/actual/<project>/ (always,
 *      uploaded as an artifact even when the run is green), and
 *   2. assert against the committed baseline via toHaveScreenshot().
 *
 * Each project (visual-desktop/tablet/mobile) supplies its own viewport,
 * and baselines are stored per project under screenshots/baseline/.
 */
async function capture(page, testInfo, name) {
  const project = testInfo.project.name;
  await page.screenshot({
    path: `screenshots/actual/${project}/${name}.png`,
    fullPage: true,
  });
  await expect(page).toHaveScreenshot(`${name}.png`, { fullPage: true });
}

test.describe("Visual QA", () => {
  test("login screen", async ({ page }, testInfo) => {
    await mockApi(page);
    await page.goto("/");
    await expect(page.locator("form.login-card")).toBeVisible();
    await capture(page, testInfo, "login");
  });

  test("dashboard (admin)", async ({ page }, testInfo) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await expect(page.getByText("Operativo")).toBeVisible();
    await capture(page, testInfo, "dashboard-admin");
  });

  test("dashboard (user)", async ({ page }, testInfo) => {
    await mockApi(page, { user: BASIC_USER });
    await login(page, BASIC_USER.email);
    await expect(page.locator(".notice.warn")).toBeVisible();
    await capture(page, testInfo, "dashboard-user");
  });

  test("documents panel", async ({ page }, testInfo) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await page
      .locator("nav.nav")
      .getByRole("button", { name: "Documentos" })
      .click();
    await expect(
      page.getByRole("heading", { level: 1, name: "Documentos" })
    ).toBeVisible();
    await capture(page, testInfo, "documents");
  });

  test("python runner", async ({ page }, testInfo) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await page
      .locator("nav.nav")
      .getByRole("button", { name: "Python Runner" })
      .click();
    await expect(
      page.getByRole("heading", { level: 1, name: "Python Runner" })
    ).toBeVisible();
    await capture(page, testInfo, "python-runner");
  });

  test("dark mode dashboard", async ({ page }, testInfo) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await page
      .getByRole("button", { name: "Cambiar tema" })
      .click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await capture(page, testInfo, "dark-mode");
  });
});
