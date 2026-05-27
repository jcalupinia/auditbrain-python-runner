import { test, expect } from "@playwright/test";
import { mockApi, login, BASIC_USER } from "./helpers.js";

test.describe("Generación de Documentos", () => {
  test("usuario autenticado genera un documento y recibe enlace", async ({ page }) => {
    await mockApi(page, {
      user: BASIC_USER,
      documentResult: { response: { url: "https://docs.example.test/report.pdf" } },
    });
    await login(page, BASIC_USER.email);
    await page.locator("aside.cc-side")
      .getByRole("button", { name: /Documentos/i }).first().click();
    await expect(page.getByRole("heading", { name: /Generación Documental/i }))
      .toBeVisible();

    // Form de generación
    await page.getByPlaceholder("Informe trimestral").fill("Informe trimestral");
    await page.getByPlaceholder("Texto principal del documento…")
      .fill("Contenido principal del informe.");
    await page.getByRole("button", { name: /Generar documento/i }).click();

    const link = page.getByRole("link", { name: /Descargar documento/i });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", "https://docs.example.test/report.pdf");
  });
});
