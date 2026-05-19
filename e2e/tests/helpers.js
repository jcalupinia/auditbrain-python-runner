import { expect } from "@playwright/test";

/**
 * Default fake users returned by the mocked `/auth/me` endpoint.
 */
export const ADMIN_USER = {
  id: 1,
  email: "admin@auditbrain.test",
  role: "admin",
  is_active: true,
};

export const BASIC_USER = {
  id: 2,
  email: "user@auditbrain.test",
  role: "user",
  is_active: true,
};

const HEALTH_OK = {
  status: "ok",
  service: "AuditBrain Platform v1",
  version: "1.0.0-test",
  auth_enabled: true,
  timestamp: "2026-05-19T00:00:00",
};

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

/**
 * Stub every backend endpoint the frontend touches. Pass options to shape
 * behaviour per test.
 *
 * @param {import('@playwright/test').Page} page
 * @param {object} [opts]
 * @param {object|null} [opts.user]        user returned by GET /auth/me
 * @param {boolean} [opts.loginFails]      make POST /auth/login return 401
 * @param {boolean} [opts.healthDown]      make GET /health return 503
 * @param {object} [opts.runResult]        body for POST /python/run
 * @param {object} [opts.documentResult]   body for POST /documents/generate
 */
export async function mockApi(page, opts = {}) {
  const {
    user = ADMIN_USER,
    loginFails = false,
    healthDown = false,
    runResult = { stdout: "", stderr: "", result: 4 },
    documentResult = {
      response: { url: "https://docs.example.test/report.pdf" },
    },
  } = opts;

  await page.route("**/api/v1/health", (route) =>
    healthDown
      ? json(route, { detail: "unavailable" }, 503)
      : json(route, HEALTH_OK)
  );

  await page.route("**/api/v1/auth/login", (route) => {
    if (loginFails) {
      return json(route, { detail: "Email o contraseña incorrectos." }, 401);
    }
    return json(route, {
      access_token: "fake.jwt.token",
      token_type: "bearer",
      role: user ? user.role : "user",
    });
  });

  await page.route("**/api/v1/auth/me", (route) =>
    user ? json(route, user) : json(route, { detail: "unauthorized" }, 401)
  );

  await page.route("**/api/v1/python/run", (route) =>
    json(route, runResult)
  );

  await page.route("**/api/v1/auth/users", (route) => {
    const post = JSON.parse(route.request().postData() || "{}");
    return json(
      route,
      {
        id: 99,
        email: post.email,
        role: post.role || "user",
        is_active: true,
      },
      201
    );
  });

  await page.route("**/api/v1/documents/generate", (route) =>
    json(route, documentResult)
  );
}

/**
 * Perform the UI login flow and wait until the dashboard shell renders.
 */
export async function login(page, email = ADMIN_USER.email, password = "secret12") {
  await page.goto("/");
  const form = page.locator("form.login-card");
  await form.locator('input[type="email"]').fill(email);
  await form.locator('input[type="password"]').fill(password);
  await form.getByRole("button", { name: "Entrar" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard" })
  ).toBeVisible();
}
