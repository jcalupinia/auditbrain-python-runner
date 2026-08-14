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

  test("el chat ofrece el botón de dictado por voz (micrófono)", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await page.locator("aside.cc-side")
      .getByRole("button", { name: /Executive Advisory/i }).click();
    // Chromium expone webkitSpeechRecognition, así que el botón debe renderizar.
    const mic = page.locator("button.cw-mic");
    await expect(mic).toBeVisible();
    await expect(mic).toContainText(/Voz/i);
    await expect(mic).toHaveAttribute("aria-pressed", "false");
  });

  test("adjuntar un documento muestra el chip y habilita Enviar", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    // El backend extrae el texto del archivo subido.
    await page.route("**/api/v1/chat/attachments/extract", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          name: "balance.csv",
          kind: "csv",
          chars: 42,
          truncated: false,
          text: "Cuenta\tSaldo\nCaja\t1500",
        }),
      })
    );
    await login(page);
    await page.locator("aside.cc-side")
      .getByRole("button", { name: /Executive Advisory/i }).click();

    // Sin texto ni adjuntos, Enviar está deshabilitado.
    const enviar = page.getByRole("button", { name: /^Enviar$/ });
    await expect(enviar).toBeDisabled();

    // Adjuntar dispara el input file oculto; lo llenamos directamente.
    await page.locator('input[type="file"]').setInputFiles({
      name: "balance.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("Cuenta,Saldo\nCaja,1500\n"),
    });

    // Aparece el chip del documento y Enviar se habilita (solo-adjunto permitido).
    const chip = page.locator(".cw-chip", { hasText: "balance.csv" });
    await expect(chip).toBeVisible();
    await expect(enviar).toBeEnabled();

    // Quitar el chip vuelve a deshabilitar Enviar.
    await chip.getByRole("button", { name: /Quitar/i }).click();
    await expect(chip).toHaveCount(0);
    await expect(enviar).toBeDisabled();
  });

  test("pestaña Imagen genera con confirmación (puente ComfyUI)", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    // PNG 1x1 base64 de prueba que devuelve el puente.
    const png1x1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
    await page.route("https://bridge.test/generate", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ model: "flux", filename: "x.png", seconds: 12.3,
                               image_base64: png1x1, mime: "image/png" }),
      })
    );
    await login(page);
    await page.locator("aside.cc-side")
      .getByRole("button", { name: /Executive Advisory/i }).click();

    // La pestaña Imagen aparece porque el puente está configurado (env de test).
    await page.getByRole("button", { name: /^Imagen$/ }).click();
    await page.locator("textarea.cw-img-prompt").fill("póster navy y gold AUDITCONSULTING");
    await page.getByRole("button", { name: /Generar imagen/i }).click();

    // Sale el diálogo de confirmación (honestidad del trade-off).
    await expect(page.getByText(/el chat seguirá funcionando con el respaldo/i)).toBeVisible();
    await page.getByRole("button", { name: /Sí, generar/i }).click();

    // Aparece la imagen generada y el botón de descarga.
    await expect(page.locator(".cw-img-result img")).toBeVisible();
    await expect(page.getByRole("link", { name: /Descargar/i })).toBeVisible();
  });
});
