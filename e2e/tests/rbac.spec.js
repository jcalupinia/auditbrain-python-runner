import { test, expect } from "@playwright/test";
import { mockApi, login, ADMIN_USER, BASIC_USER } from "./helpers.js";

test.describe("Role-based navigation", () => {
  test("admin sees the Python Runner and Usuarios nav entries", async ({
    page,
  }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    const nav = page.locator("nav.nav");
    await expect(nav.getByRole("button", { name: "Python Runner" })).toBeVisible();
    await expect(nav.getByRole("button", { name: "Usuarios" })).toBeVisible();
  });

  test("a basic user does not see admin-only nav entries", async ({ page }) => {
    await mockApi(page, { user: BASIC_USER });
    await login(page, BASIC_USER.email);
    const nav = page.locator("nav.nav");
    await expect(nav.getByRole("button", { name: "Python Runner" })).toHaveCount(
      0
    );
    await expect(nav.getByRole("button", { name: "Usuarios" })).toHaveCount(0);
    await expect(nav.getByRole("button", { name: "Documentos" })).toBeVisible();
  });

  test("admin can run a Python script and see the result", async ({ page }) => {
    await mockApi(page, {
      user: ADMIN_USER,
      runResult: { stdout: "", stderr: "", result: 4 },
    });
    await login(page);
    await page.locator("nav.nav").getByRole("button", { name: "Python Runner" }).click();
    await expect(
      page.getByRole("heading", { name: "Python Runner" })
    ).toBeVisible();
    await page.getByRole("button", { name: "Ejecutar" }).click();
    await expect(page.locator("pre")).toContainText('"result": 4');
  });

  test("admin can create a user from the Usuarios panel", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await page.locator("nav.nav").getByRole("button", { name: "Usuarios" }).click();
    const card = page.locator(".card");
    await card.locator('input[type="email"]').fill("new@auditbrain.test");
    await card.locator('input[type="password"]').fill("password123");
    await page.getByRole("button", { name: "Crear usuario" }).click();
    await expect(page.locator(".ok-msg")).toContainText(
      "Usuario creado: new@auditbrain.test"
    );
  });
});
