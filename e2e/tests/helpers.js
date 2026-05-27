import { expect } from "@playwright/test";

/**
 * Usuarios mock devueltos por /api/v1/auth/me.
 */
export const ADMIN_USER = {
  id: 1,
  email: "admin@auditbrain.test",
  role: "admin",
  is_active: true,
  organization_id: 1,
  active_project_id: null,
};

export const BASIC_USER = {
  id: 2,
  email: "user@auditbrain.test",
  role: "user",
  is_active: true,
  organization_id: 1,
  active_project_id: null,
};

const HEALTH_OK = {
  status: "ok",
  service: "AuditBrain Platform v1",
  version: "4.0.0-test",
  auth_enabled: true,
  llm: { configured: ["gemini"], primary: "gemini" },
  timestamp: "2026-05-20T00:00:00",
};

const CONTEXT_EMPTY = {
  organization: { id: 1, name: "AuditBrain", slug: "auditbrain" },
  active_project: null,
  active_client: null,
  projects: [],
};

const MODULES_CATALOG = [
  { code: "ADV", label: "Executive Advisory", tagline: "Consejo ejecutivo",
    description: "Asesoría a C-suite.", suggested_actions: [], kpi_hints: [] },
  { code: "AUD", label: "External Audit", tagline: "Auditoría externa",
    description: "NIA/IFRS.", suggested_actions: [], kpi_hints: [] },
  { code: "TAX", label: "Tax Structuring", tagline: "Tributación",
    description: "Tributaria.", suggested_actions: [], kpi_hints: [] },
];

function jsonRoute(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

/**
 * Intercepta todas las peticiones /api/v1/* del frontend y devuelve mocks
 * deterministas. Cualquier ruta no contemplada -> 404 explícito.
 */
export async function mockApi(page, {
  user = ADMIN_USER,
  healthDown = false,
  loginFails = false,
  documentResult = { response: { url: "https://docs.example.test/report.pdf" } },
  runResult = { stdout: "", stderr: "", result: 4 },
  context = CONTEXT_EMPTY,
  modules = MODULES_CATALOG,
} = {}) {
  await page.route("**/api/v1/health", (route) => {
    if (healthDown) return route.fulfill({ status: 503, body: "{}" });
    return jsonRoute(route, HEALTH_OK);
  });

  await page.route("**/api/v1/auth/login", (route) => {
    if (loginFails) return jsonRoute(route, { detail: "Email o contraseña incorrectos." }, 401);
    return jsonRoute(route, { access_token: "tok-test", token_type: "bearer", role: user.role });
  });

  await page.route("**/api/v1/auth/me", (route) => jsonRoute(route, user));
  await page.route("**/api/v1/auth/users", (route) =>
    jsonRoute(route, { id: 99, email: "new@auditbrain.test", role: "user", is_active: true }, 201)
  );

  await page.route("**/api/v1/me/context", (route) => jsonRoute(route, context));
  await page.route("**/api/v1/context/clients", (route) => jsonRoute(route, []));
  await page.route("**/api/v1/context/projects", (route) => jsonRoute(route, []));
  await page.route("**/api/v1/modules", (route) => jsonRoute(route, modules));

  await page.route("**/api/v1/python/run", (route) => jsonRoute(route, runResult));
  await page.route("**/api/v1/documents/generate", (route) =>
    jsonRoute(route, { status: "ok", ...documentResult })
  );

  // Default catch-all para no contaminar con 404s confusos.
  await page.route("**/api/v1/**", (route) => jsonRoute(route, { detail: "not mocked" }, 404));
}

/**
 * Login flujo completo: rellena email/contraseña y pulsa "Acceder al
 * Command Center". Termina cuando el sidebar (cc-side) ya está pintado.
 */
export async function login(page, email = ADMIN_USER.email, password = "Sup3rSecret!") {
  await page.goto("/");
  const form = page.locator("form.login-card");
  await form.locator('input[type="email"]').fill(email);
  await form.locator('input[type="password"]').fill(password);
  await form.getByRole("button", { name: /Acceder al Command Center/i }).click();
  await expect(page.locator("aside.cc-side")).toBeVisible({ timeout: 8_000 });
}
