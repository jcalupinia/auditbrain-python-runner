import { test, expect } from "@playwright/test";
import { mockApi, login, ADMIN_USER } from "./helpers.js";

/*
 * Recorrido de UI real de la vista de 3 pasos de «Planificación de la auditoría»
 * (processor planificacion_nia). No hay backend: cada endpoint del ciclo se mockea
 * con page.route(). El objetivo es verificar que:
 *   - se navega AUD → «Generación de herramientas NIIF» → «Pruebas del encargo»,
 *   - se abre una prueba cuya definicion.processor === "planificacion_nia",
 *   - se monta VistaProceso (los 3 pasos) con sus tarjetas primarias y de ejecución,
 *   - con estado NO procesado las tarjetas de ejecución muestran «BLOQUEADO»,
 *   - con estado EJECUTADO las tarjetas quedan habilitadas.
 */

const CLIENTE = "Comercial Andina de Ejemplo S.A.";
const ENCARGO_ID = 501;
const PRUEBA_ID = 701;

// Requerimientos RQ-001..RQ-009 (document + required). Los títulos de las tarjetas
// primarias los pone procesoConfig.js; aquí solo importa que existan esos ids.
const REQUESTS = [
  { id: "RQ-001", document: "Estados Financieros del Año Anterior", required: true, formats: ["xlsx"] },
  { id: "RQ-002", document: "Estados Financieros del Año Actual", required: true, formats: ["xlsx"] },
  { id: "RQ-003", document: "Estado de Resultados del Año Anterior", required: false, formats: ["xlsx"] },
  { id: "RQ-004", document: "Carta de Control Interno del Año Anterior", required: true, formats: ["xlsx", "pdf"] },
  { id: "RQ-005", document: "Informe de Auditoría del Año Anterior", required: true, formats: ["pdf"] },
  { id: "RQ-006", document: "Notas a los Estados Financieros del Año Anterior", required: true, formats: ["xlsx"] },
  { id: "RQ-007", document: "Balance de Comprobación del Corte", required: false, formats: ["xlsx"] },
  { id: "RQ-008", document: "Certificado del RUC", required: true, formats: ["pdf", "xlsx"] },
  { id: "RQ-009", document: "Composición / Notas detalle", required: false, formats: ["xlsx"] },
];

const jsonRoute = (route, body, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

// Prueba de planificación en el estado pedido. `procesada` decide la cobertura.
function pruebaPlanificacion(estado) {
  const procesada = ["PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS", "EN_REVISION", "APROBADO"].includes(estado);
  const cobertura = REQUESTS.map((r, i) => ({
    id: r.id,
    // En estado procesado todo está completo; antes, solo un par de documentos.
    complete: procesada ? true : i < 2,
    rejected: false,
  }));
  return {
    id: PRUEBA_ID,
    version: 1,
    revision: 0,
    estado,
    origen: "proc:planificacion_nia",
    archivos: [],
    cobertura,
    eventos: [
      { fecha: "2026-09-26T10:00:00", actor: "admin@auditbrain.test", accion: "create", estado_nuevo: "PRUEBA_SELECCIONADA" },
    ],
    definicion: {
      processor: "planificacion_nia",
      name: "Planificación de la auditoría",
      requests: REQUESTS,
      parametros: {},
    },
    registro: {
      methodologyVersion: "NIA-2026.1",
      engagement: { client: CLIENTE, framework: "NIIF para las PYMES" },
      requests: REQUESTS,
      parameters: {},
      run: { exceptions: [] },
    },
  };
}

// Mockea los endpoints del ciclo. `estado` fija el estado de la prueba abierta.
async function mockCiclo(page, estado) {
  // Encargos (barra superior de PruebasEncargo).
  await page.route("**/api/v1/aud/ciclo/encargos", (route) =>
    jsonRoute(route, [
      { id: ENCARGO_ID, cliente: CLIENTE, nombre: "Auditoría 2025", marco: "NIIF para las PYMES", pruebas: 1 },
    ])
  );
  // Ficha del encargo.
  await page.route("**/api/v1/aud/ciclo/proyectos/*/ficha", (route) =>
    jsonRoute(route, {
      ficha: {
        client: CLIENTE, ruc: "1790012345001", framework: "NIIF para las PYMES", edition: "2015",
        cutoff: "2025-12-31", currency: "USD", visit: "Final",
        preparer: "A. Auditor", reviewer: "B. Revisor", firm: "AuditConsulting Auditores Cía. Ltda.",
      },
    })
  );
  // Lista de pruebas del encargo.
  await page.route("**/api/v1/aud/ciclo/proyectos/*/pruebas", (route) =>
    jsonRoute(route, [
      { id: PRUEBA_ID, nombre: "Planificación de la auditoría", version: 1, estado, origen: "proc:planificacion_nia" },
    ])
  );
  // Catálogo de herramientas (selector de nueva prueba).
  await page.route("**/api/v1/aud/ciclo/herramientas", (route) =>
    jsonRoute(route, [{ origen: "proc:planificacion_nia", nombre: "Planificación de la auditoría", tipo: "Procesador" }])
  );
  // Registros del encargo (RegistroEncargo se monta dentro de un <details> colapsado).
  await page.route("**/api/v1/aud/ciclo/proyectos/*/registros", (route) =>
    jsonRoute(route, { registros: [], usuario: { email: ADMIN_USER.email }, ciclos: [], consultas: [] })
  );
  // Piloto guiado (sección por defecto de CentroNIIF antes de cambiar de subpestaña).
  await page.route("**/api/v1/aud/niif/piloto/pruebas", (route) => jsonRoute(route, []));
  // Lectura de la prueba: dispara el render de VistaProceso.
  await page.route(/\/api\/v1\/aud\/ciclo\/pruebas\/\d+$/, (route) =>
    jsonRoute(route, pruebaPlanificacion(estado))
  );
}

// Navega desde el login hasta abrir la prueba de planificación.
async function abrirPlanificacion(page) {
  await login(page);
  // AUD → Workspace cognitivo.
  await page.locator("aside.cc-side").getByRole("button", { name: /External Audit/i }).click();
  // Pestaña «Generación de herramientas NIIF».
  await page.getByRole("button", { name: /Generación de herramientas NIIF/i }).click();
  // Subpestaña «Pruebas del encargo» dentro de CentroNIIF.
  await page.locator("nav.nf-subtabs").getByRole("button", { name: /^Pruebas del encargo$/ }).click();
  // Desplegar la lista de pruebas y abrir la de planificación.
  await page.locator("details.nf-registro-colapsado > summary").first().click();
  await page.getByRole("button", { name: /Planificación de la auditoría · v1/ }).click();
  // VistaProceso montada: el paso 1 confirma que la vista se renderizó.
  await expect(page.getByRole("heading", { name: /Requerimientos de información/i })).toBeVisible({ timeout: 10_000 });
}

// Asserts comunes de que la vista de 3 pasos se renderizó con su contenido.
async function verificarVistaTresPasos(page) {
  // Los 3 encabezados de paso.
  await expect(page.getByRole("heading", { name: /Requerimientos de información/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Procesamiento de información/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Ejecución de auditoría/i })).toBeVisible();

  // Botones del paso 2.
  await expect(page.getByRole("button", { name: /Procesar/ }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Encerar/ }).first()).toBeVisible();

  // Al menos 3 de los 6 títulos de tarjetas primarias del mockup.
  await expect(page.getByRole("heading", { name: /Estados Financieros Año Actual/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Informe de Auditoría Año Anterior/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Certificado del RUC/i })).toBeVisible();

  // Al menos 4 de las 11 tarjetas de ejecución. Coincidencia exacta: los subtítulos
  // repiten estas palabras (p. ej. «…de situación financiera», «…de materialidad»).
  await expect(page.getByText("Tablero Ejecutivo", { exact: true })).toBeVisible();
  await expect(page.getByText("Situación Financiera", { exact: true })).toBeVisible();
  await expect(page.getByText("Materialidad", { exact: true })).toBeVisible();
  await expect(page.getByText("Programa", { exact: true })).toBeVisible();
}

test.describe("Planificación de la auditoría · vista de 3 pasos (planificacion_nia)", () => {
  test("estado NO procesado: se renderizan los 3 pasos y la ejecución está BLOQUEADA", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await mockCiclo(page, "REQUERIMIENTO_APROBADO");
    await abrirPlanificacion(page);

    await verificarVistaTresPasos(page);

    // Sin procesar: las tarjetas de ejecución muestran «BLOQUEADO» y están deshabilitadas.
    await expect(page.getByText(/BLOQUEADO/).first()).toBeVisible();
    const tablero = page.locator("button.nf-ef-ejec-card", { hasText: "Tablero Ejecutivo" });
    await expect(tablero).toBeDisabled();
  });

  test("estado EJECUTADO: las tarjetas de ejecución quedan habilitadas", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await mockCiclo(page, "PRUEBA_EJECUTADA");
    await abrirPlanificacion(page);

    await verificarVistaTresPasos(page);

    // Procesada: no hay «BLOQUEADO» y las tarjetas de ejecución están habilitadas.
    await expect(page.getByText(/BLOQUEADO/)).toHaveCount(0);
    const tablero = page.locator("button.nf-ef-ejec-card", { hasText: "Tablero Ejecutivo" });
    await expect(tablero).toBeEnabled();
    const materialidad = page.locator("button.nf-ef-ejec-card", { hasText: "Materialidad" });
    await expect(materialidad).toBeEnabled();
  });
});
