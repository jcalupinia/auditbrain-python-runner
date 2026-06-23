import { test, expect } from "@playwright/test";
import { mockApi, login, ADMIN_USER } from "./helpers.js";

test.describe("Navegación del Command Center", () => {
  test("sidebar lista módulos sectoriales y nodos operativos", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    const side = page.locator("aside.cc-side");
    // Al menos los 3 primeros módulos sectoriales del mock
    await expect(side.getByRole("button", { name: /Executive Advisory/i })).toBeVisible();
    await expect(side.getByRole("button", { name: /External Audit/i })).toBeVisible();
    await expect(side.getByRole("button", { name: /Tax Structuring/i })).toBeVisible();
    // Nodos operativos
    await expect(side.getByRole("button", { name: /Centro de Operaciones/i })).toBeVisible();
    await expect(side.getByRole("button", { name: /Documentos/i })).toBeVisible();
  });

  test("click en un módulo abre el Workspace Cognitivo", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await page.locator("aside.cc-side")
      .getByRole("button", { name: /Executive Advisory/i }).click();
    // Hero del módulo: saludo personalizado con el email del usuario
    await expect(page.getByRole("heading", { name: /Hola/i }).first()).toBeVisible();
    // Panel del workspace cognitivo
    await expect(page.getByText("Workspace cognitivo")).toBeVisible();
    // Tabs Chat/Análisis/Documentos/Notas
    await expect(page.getByRole("button", { name: /^Chat$/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Documentos$/ }).first()).toBeVisible();
  });

  test("Centro de Operaciones muestra telemetría", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await page.locator("aside.cc-side")
      .getByRole("button", { name: /Centro de Operaciones/i }).click();
    await expect(page.getByRole("heading", { name: /Centro de Operaciones/i })).toBeVisible();
    await expect(page.getByText(/Operativo/).first()).toBeVisible();
    await expect(page.getByText("4.0.0-test").first()).toBeVisible();
  });

  test("Footer muestra el estado operativo en vivo", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    const foot = page.locator("footer.cc-foot");
    await expect(foot).toContainText(/AUDIT-IA/);
    await expect(foot).toContainText("Auth JWT");
    await expect(foot).toContainText("Sandbox Tier 0");
  });
});
