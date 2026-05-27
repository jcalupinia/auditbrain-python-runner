import { test, expect } from "@playwright/test";
import { mockApi, login, ADMIN_USER } from "./helpers.js";

test.describe("Login", () => {
  test("muestra la pantalla de login sin sesión", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
    await expect(page.locator("form.login-card")).toBeVisible();
    await expect(page.getByText(/Enterprise Intelligence OS/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Acceder al Command Center/i })
    ).toBeVisible();
  });

  test("login válido aterriza en el Command Center", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    // Header del Command Center
    await expect(page.getByText("COMMAND CENTER")).toBeVisible();
    // El email del usuario aparece en el chip del header
    await expect(page.getByText(ADMIN_USER.email).first()).toBeVisible();
  });

  test("credenciales inválidas → muestra el error en línea", async ({ page }) => {
    await mockApi(page, { loginFails: true });
    await page.goto("/");
    const form = page.locator("form.login-card");
    await form.locator('input[type="email"]').fill("nobody@auditbrain.test");
    await form.locator('input[type="password"]').fill("wrongpass");
    await form.getByRole("button", { name: /Acceder al Command Center/i }).click();
    await expect(page.locator(".err")).toContainText(/incorrect|inválid/i);
    // No debe haber navegado al shell
    await expect(page.locator("aside.cc-side")).toHaveCount(0);
  });

  test("Salir limpia la sesión y vuelve al login", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await page.getByRole("button", { name: /^Salir$/ }).click();
    await expect(page.locator("form.login-card")).toBeVisible();
  });
});
