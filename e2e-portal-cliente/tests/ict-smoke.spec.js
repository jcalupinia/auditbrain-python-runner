import { test, expect } from "@playwright/test";

test("ICT route is protected (requires login)", async ({ page }) => {
  await page.goto("/tools/ICT_2025");
  // Should redirect to login (no session)
  await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
});

test("ICT landing renders when accessed without active session", async ({ page }) => {
  // This test would require login. Skip for now since we'd need test credentials.
  // Marked as a placeholder for future enhancement.
  test.skip(true, "Requires backend test credentials");
});
