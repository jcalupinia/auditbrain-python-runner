import { test, expect } from "@playwright/test";
import { mockApi, login, BASIC_USER } from "./helpers.js";

test.describe("Documents panel", () => {
  test("any authenticated user can generate a document and gets a download link", async ({
    page,
  }) => {
    await mockApi(page, {
      user: BASIC_USER,
      documentResult: {
        response: { url: "https://docs.example.test/report.pdf" },
      },
    });
    await login(page, BASIC_USER.email);
    await page.locator("nav.nav").getByRole("button", { name: "Documentos" }).click();
    await expect(
      page.getByRole("heading", { name: "Documentos" })
    ).toBeVisible();

    const card = page.locator(".card").first();
    await card.locator('input').fill("Informe trimestral");
    await card.locator("textarea").fill("Contenido principal del informe.");
    await page.getByRole("button", { name: "Generar documento" }).click();

    const link = page.getByRole("link", { name: "⇩ Descargar documento" });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute(
      "href",
      "https://docs.example.test/report.pdf"
    );
  });

  test("shows the backend error when the document service fails", async ({
    page,
  }) => {
    await mockApi(page, {
      user: BASIC_USER,
      documentResult: { status: "error", error: "Servicio no disponible" },
    });
    await login(page, BASIC_USER.email);
    await page.locator("nav.nav").getByRole("button", { name: "Documentos" }).click();
    const card = page.locator(".card").first();
    await card.locator("input").fill("Reporte");
    await card.locator("textarea").fill("Texto");
    await page.getByRole("button", { name: "Generar documento" }).click();
    await expect(page.locator(".err")).toContainText("Servicio no disponible");
  });
});
