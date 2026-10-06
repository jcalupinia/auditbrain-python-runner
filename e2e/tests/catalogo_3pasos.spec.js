import { test, expect } from "@playwright/test";
import { mockApi, login, ADMIN_USER } from "./helpers.js";

/*
 * Recorrido de UI parametrizado de la vista de 3 pasos (VistaProceso) para las
 * herramientas del catálogo que la usan además de efectivo y planificación.
 * La vista es config-driven (procesoConfig.js): un mismo componente y un mismo
 * spec sirven para todas. Por cada herramienta se verifica que:
 *   - se abre una prueba cuyo definicion.processor tiene config,
 *   - se montan los 3 pasos con sus tarjetas primarias del mockup,
 *   - renderizan TODAS sus tarjetas de ejecución (toHaveCount),
 *   - con estado NO procesado la ejecución está BLOQUEADA,
 *   - con estado EJECUTADO la ejecución queda habilitada.
 *
 * Etapa 1 (circulante/operativo): cuentas por cobrar, proveedores, inventarios,
 * ingresos. El backend se mockea con page.route().
 */

const CLIENTE = "Comercial Andina de Ejemplo S.A.";
const ENCARGO_ID = 901;

// Herramientas cubiertas por esta etapa. `primarias` son los títulos exactos de
// las tarjetas de documento (procesoConfig.js) y `nEjec` el número de tarjetas de
// ejecución. `reqIds` son los ids de requerimiento que devuelve el procesador
// (para que las tarjetas primarias, que se casan por id, aparezcan).
const TOOLS = [
  {
    processor: "cxc_cartera",
    nombre: "Cuentas por Cobrar",
    reqIds: ["RQ-001", "RQ-002", "RQ-003", "RQ-004", "RQ-005", "RQ-006", "RQ-007"],
    primarias: ["Cartera por Factura", "Mayor de Cuentas por Cobrar", "Confirmaciones de Clientes"],
    nEjec: 9,
  },
  {
    processor: "proveedores_cxp",
    nombre: "Proveedores y Cuentas por Pagar",
    reqIds: ["RQ-001", "RQ-002", "RQ-003", "RQ-004", "RQ-005", "RQ-006", "RQ-007"],
    primarias: ["Auxiliar de Proveedores", "Mayor de Proveedores", "Confirmaciones de Proveedores"],
    nEjec: 10,
  },
  {
    processor: "inventarios_costos",
    nombre: "Inventarios y Costos",
    reqIds: ["RQ-001", "RQ-002", "RQ-003", "RQ-004", "RQ-005", "RQ-006", "RQ-007", "RQ-008", "RQ-009", "RQ-010"],
    primarias: ["Inventario Valorado (Kardex)", "Actas de Recuento Físico", "Política de Obsolescencia"],
    nEjec: 14,
  },
  {
    processor: "ingresos_contratos",
    nombre: "Ingresos",
    reqIds: ["RQ-001", "RQ-002", "RQ-003", "RQ-004", "RQ-005", "RQ-006", "RQ-007", "RQ-008"],
    primarias: ["Anexo de Contratos por Obligación", "Mayor de Ingresos", "Guías de Remisión / Actas"],
    nEjec: 10,
  },
];

const PRUEBA_ID = 1001;
const PROCESADAS = ["PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS", "EN_REVISION", "APROBADO"];

const jsonRoute = (route, body, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

function pruebaDe(tool, estado) {
  const procesada = PROCESADAS.includes(estado);
  const requests = tool.reqIds.map((id, i) => ({
    id,
    document: `Documento ${id}`,
    required: i < 3,
    formats: ["xlsx"],
  }));
  const cobertura = requests.map((r, i) => ({ id: r.id, complete: procesada ? true : i < 2, rejected: false }));
  return {
    id: PRUEBA_ID,
    version: 1,
    revision: 0,
    estado,
    origen: `proc:${tool.processor}`,
    archivos: [],
    cobertura,
    eventos: [
      { fecha: "2026-09-26T10:00:00", actor: ADMIN_USER.email, accion: "create", estado_nuevo: "PRUEBA_SELECCIONADA" },
    ],
    definicion: { processor: tool.processor, name: tool.nombre, requests, parametros: {} },
    registro: {
      methodologyVersion: "NIA-2026.1",
      engagement: { client: CLIENTE, framework: "NIIF para las PYMES" },
      requests,
      parameters: {},
      run: { exceptions: [] },
    },
  };
}

async function mockCiclo(page, tool, estado) {
  await page.route("**/api/v1/aud/ciclo/encargos", (route) =>
    jsonRoute(route, [{ id: ENCARGO_ID, cliente: CLIENTE, nombre: "Auditoría 2025", marco: "NIIF para las PYMES", pruebas: 1 }])
  );
  await page.route("**/api/v1/aud/ciclo/proyectos/*/ficha", (route) =>
    jsonRoute(route, {
      ficha: {
        client: CLIENTE, ruc: "1790012345001", framework: "NIIF para las PYMES", edition: "2015",
        cutoff: "2025-12-31", currency: "USD", visit: "Final",
        preparer: "A. Auditor", reviewer: "B. Revisor", firm: "AuditConsulting Auditores Cía. Ltda.",
      },
    })
  );
  await page.route("**/api/v1/aud/ciclo/proyectos/*/pruebas", (route) =>
    jsonRoute(route, [{ id: PRUEBA_ID, nombre: tool.nombre, version: 1, estado, origen: `proc:${tool.processor}` }])
  );
  await page.route("**/api/v1/aud/ciclo/herramientas", (route) =>
    jsonRoute(route, [{ origen: `proc:${tool.processor}`, nombre: tool.nombre, tipo: "Procesador" }])
  );
  await page.route("**/api/v1/aud/ciclo/proyectos/*/registros", (route) =>
    jsonRoute(route, { registros: [], usuario: { email: ADMIN_USER.email }, ciclos: [], consultas: [] })
  );
  await page.route("**/api/v1/aud/niif/piloto/pruebas", (route) => jsonRoute(route, []));
  await page.route(/\/api\/v1\/aud\/ciclo\/pruebas\/\d+$/, (route) => jsonRoute(route, pruebaDe(tool, estado)));
}

async function abrir(page, tool) {
  await login(page);
  await page.locator("aside.cc-side").getByRole("button", { name: /External Audit/i }).click();
  await page.getByRole("button", { name: /Generación de herramientas NIIF/i }).click();
  await page.locator("nav.nf-subtabs").getByRole("button", { name: /^Pruebas del encargo$/ }).click();
  await page.locator("details.nf-registro-colapsado > summary").first().click();
  await page.getByRole("button", { name: new RegExp(`${tool.nombre.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")} · v1`) }).click();
  await expect(page.getByRole("heading", { name: /Requerimientos de información/i })).toBeVisible({ timeout: 10_000 });
}

async function verificarVistaTresPasos(page, tool) {
  await expect(page.getByRole("heading", { name: /Requerimientos de información/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Procesamiento de información/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Ejecución de auditoría/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Procesar/ }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Encerar/ }).first()).toBeVisible();
  for (const titulo of tool.primarias) {
    await expect(page.getByRole("heading", { name: titulo, exact: true })).toBeVisible();
  }
  await expect(page.locator("button.nf-ef-ejec-card")).toHaveCount(tool.nEjec);
}

for (const tool of TOOLS) {
  test.describe(`Vista de 3 pasos · ${tool.nombre} (${tool.processor})`, () => {
    test("estado NO procesado: 3 pasos renderizados y ejecución BLOQUEADA", async ({ page }) => {
      await mockApi(page, { user: ADMIN_USER });
      await mockCiclo(page, tool, "REQUERIMIENTO_APROBADO");
      await abrir(page, tool);
      await verificarVistaTresPasos(page, tool);
      await expect(page.getByText(/BLOQUEADO/).first()).toBeVisible();
      await expect(page.locator("button.nf-ef-ejec-card").first()).toBeDisabled();
    });

    test("estado EJECUTADO: las tarjetas de ejecución quedan habilitadas", async ({ page }) => {
      await mockApi(page, { user: ADMIN_USER });
      await mockCiclo(page, tool, "PRUEBA_EJECUTADA");
      await abrir(page, tool);
      await verificarVistaTresPasos(page, tool);
      await expect(page.getByText(/BLOQUEADO/)).toHaveCount(0);
      await expect(page.locator("button.nf-ef-ejec-card").first()).toBeEnabled();
    });
  });
}
