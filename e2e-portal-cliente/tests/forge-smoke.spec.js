import { expect, test } from "@playwright/test";

// Smoke: la ruta de Forge Console está protegida (redirige a login sin sesión).
test("Forge Console route is protected (requires login)", async ({ page }) => {
  await page.goto("/tools/FORGE_CONSOLE");
  await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
});
