import { test, expect } from "@playwright/test";
import { mockApi, login, ADMIN_USER, BASIC_USER } from "./helpers.js";

test.describe("Dashboard", () => {
  test("reports the backend as operational when health is OK", async ({
    page,
  }) => {
    await mockApi(page, { user: ADMIN_USER });
    await login(page);
    await expect(page.getByText("Operativo")).toBeVisible();
    await expect(page.getByText("1.0.0-test")).toBeVisible();
  });

  test("reports the backend as unavailable when health is down", async ({
    page,
  }) => {
    await mockApi(page, { user: ADMIN_USER, healthDown: true });
    await login(page);
    await expect(page.getByText("No disponible")).toBeVisible();
  });

  test("a non-admin user sees the restricted-access notice", async ({
    page,
  }) => {
    await mockApi(page, { user: BASIC_USER });
    await login(page, BASIC_USER.email);
    await expect(page.locator(".notice.warn")).toContainText(
      "Acceso limitado según rol"
    );
    await expect(page.getByText("Restringido")).toBeVisible();
  });
});
