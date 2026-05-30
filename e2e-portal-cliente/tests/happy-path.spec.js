import { test, expect } from "@playwright/test";

test("landing → login redirect", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/Audit Consulting Group/i).first()).toBeVisible();
  await page.getByRole("button", { name: /Ingresar/i }).first().click();
  await expect(page).toHaveURL(/\/login/);
});

test("login with invalid credentials shows error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel(/Correo/i).fill("noexiste@example.com");
  await page.getByLabel(/Contraseña/i).fill("wrong");
  await page.getByRole("button", { name: /Ingresar/i }).click();
  // El mensaje puede decir "Credenciales incorrectas" u otro texto de error.
  await expect(page.getByText(/Credenciales|Error|incorrect/i)).toBeVisible({
    timeout: 5000,
  });
});
