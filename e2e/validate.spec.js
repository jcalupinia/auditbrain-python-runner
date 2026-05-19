// Validación visual del frontend AuditBrain SaaS v2.
// Credenciales y URL por entorno:
//   BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD, USER_EMAIL, USER_PASSWORD
// Screenshots -> e2e/screenshots/

const { test, expect } = require("@playwright/test");
const path = require("path");

const SHOT_DIR = path.join(__dirname, "screenshots");
const ADMIN_EMAIL = process.env.ADMIN_EMAIL || "admin@example.com";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "Sup3rSecret!";
const USER_EMAIL = process.env.USER_EMAIL || "user@example.com";
const USER_PASSWORD = process.env.USER_PASSWORD || "abcdefgh";

const consoleErrors = [];

async function login(page, email, password) {
  await page.goto("/");
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
  // Espera al shell autenticado (sidebar con marca AuditBrain).
  await expect(page.locator(".sidebar .brand")).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  page.on("pageerror", (e) => consoleErrors.push(String(e)));
});

test("admin: dashboard + documentos PDF/Word", async ({ page }) => {
  await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);

  await expect(page.getByRole("button", { name: "Python Runner" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Usuarios" })).toBeVisible();
  await page.screenshot({ path: `${SHOT_DIR}/01-admin-dashboard.png`, fullPage: true });

  await page.getByRole("button", { name: "Documentos" }).click();
  await expect(page.getByRole("heading", { name: "Documentos" })).toBeVisible();
  await page.screenshot({ path: `${SHOT_DIR}/02-admin-documentos.png`, fullPage: true });

  for (const [fmt, tag] of [["pdf", "03-doc-pdf"], ["word", "04-doc-word"]]) {
    await page.locator("select").first().selectOption(fmt);
    await page.getByPlaceholder("Informe trimestral").fill(`E2E ${fmt}`);
    await page
      .getByPlaceholder("Texto principal del documento…")
      .fill(`Contenido de prueba ${fmt}`);
    await page.getByRole("button", { name: "Generar documento" }).click();
    // Resultado: tarjeta de éxito o mensaje de error (ambos válidos para el shot).
    await Promise.race([
      page.getByRole("heading", { name: "Documento generado" }).waitFor(),
      page.locator(".err").waitFor(),
    ]);
    await page.screenshot({ path: `${SHOT_DIR}/${tag}.png`, fullPage: true });
  }
});

test("user: sin Runner ni Usuarios", async ({ page }) => {
  await login(page, USER_EMAIL, USER_PASSWORD);

  await expect(page.getByRole("button", { name: "Python Runner" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Usuarios" })).toHaveCount(0);
  // Documentos SÍ disponible para user.
  await expect(page.getByRole("button", { name: "Documentos" })).toBeVisible();
  await page.screenshot({ path: `${SHOT_DIR}/05-user-dashboard.png`, fullPage: true });

  await page.getByRole("button", { name: "Documentos" }).click();
  await expect(page.getByRole("heading", { name: "Documentos" })).toBeVisible();
  await page.screenshot({ path: `${SHOT_DIR}/06-user-documentos.png`, fullPage: true });
});

test.afterAll(() => {
  if (consoleErrors.length) {
    console.log("\n⚠️ Errores de consola/página detectados:");
    for (const e of consoleErrors) console.log("  -", e);
  } else {
    console.log("\n✓ Sin errores de consola/página (incluye CORS).");
  }
});
