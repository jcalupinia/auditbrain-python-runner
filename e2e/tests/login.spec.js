import { test, expect } from "@playwright/test";
import { mockApi, login, ADMIN_USER } from "./helpers.js";

test.describe("Authentication", () => {
  test("shows the login screen when there is no session", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await expect(page.locator("form.login-card")).toBeVisible();
    await expect(page.getByText("Plataforma privada")).toBeVisible();
  });

  test("logs in with valid credentials and lands on the dashboard", async ({
    page,
  }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await expect(
      page.getByRole("heading", { name: "Dashboard" })
    ).toBeVisible();
    await expect(page.getByText(ADMIN_USER.email).first()).toBeVisible();
  });

  test("shows an error message on invalid credentials", async ({ page }) => {
    await mockApi(page, { loginFails: true });
    await page.goto("/");
    const form = page.locator("form.login-card");
    await form.locator('input[type="email"]').fill("nobody@auditbrain.test");
    await form.locator('input[type="password"]').fill("wrongpass");
    await form.getByRole("button", { name: "Entrar" }).click();
    await expect(page.locator(".err")).toContainText(
      "Email o contraseña incorrectos."
    );
    await expect(page.locator("form.login-card")).toBeVisible();
  });

  test("logging out returns to the login screen", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await page.getByRole("button", { name: "Salir" }).click();
    await expect(page.locator("form.login-card")).toBeVisible();
  });
});
