import { test, expect } from "@playwright/test";
import { mockApi, login, ADMIN_USER, BASIC_USER } from "./helpers.js";

test.describe("Gating de roles", () => {
  test("admin ve los nodos restringidos (Runner / Cuentas / Workspaces)", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    const side = page.locator("aside.cc-side");
    await expect(side.getByRole("button", { name: /Motor de Ejecución/i })).toBeVisible();
    await expect(side.getByRole("button", { name: /^Cuentas$/ })).toBeVisible();
    await expect(side.getByRole("button", { name: /Workspaces/i })).toBeVisible();
  });

  test("user no ve los nodos admin-only", async ({ page }) => {
    await mockApi(page, { user: BASIC_USER });
    await login(page, BASIC_USER.email);
    const side = page.locator("aside.cc-side");
    await expect(side.getByRole("button", { name: /Motor de Ejecución/i })).toHaveCount(0);
    await expect(side.getByRole("button", { name: /^Cuentas$/ })).toHaveCount(0);
    await expect(side.getByRole("button", { name: /Workspaces/i })).toHaveCount(0);
    // Pero sí ve los que están disponibles para todos
    await expect(side.getByRole("button", { name: /Centro de Operaciones/i })).toBeVisible();
    await expect(side.getByRole("button", { name: /Documentos/i }).first()).toBeVisible();
    await expect(side.getByRole("button", { name: /Seguridad/i })).toBeVisible();
  });

  test("user ve banner de acceso limitado en Centro de Operaciones", async ({ page }) => {
    await mockApi(page, { user: BASIC_USER });
    await login(page, BASIC_USER.email);
    await page.locator("aside.cc-side")
      .getByRole("button", { name: /Centro de Operaciones/i }).click();
    await expect(page.locator(".notice.warn"))
      .toContainText(/Acceso limitado según rol/);
  });

  test("admin ejecuta Python y ve el resultado", async ({ page }) => {
    await mockApi(page, {
      user: ADMIN_USER,
      runResult: { stdout: "", stderr: "", result: 4 },
    });
    await login(page);
    await page.locator("aside.cc-side")
      .getByRole("button", { name: /Motor de Ejecución/i }).click();
    await expect(page.getByRole("heading", { name: /Motor de Ejecución Python/i }))
      .toBeVisible();
    await page.getByRole("button", { name: /^Ejecutar$/ }).click();
    await expect(page.getByText(/"result": 4/)).toBeVisible();
  });
});
