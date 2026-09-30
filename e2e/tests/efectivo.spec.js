import { test, expect } from "@playwright/test";
import { mockApi, login, ADMIN_USER } from "./helpers.js";

/*
 * Recorrido de UI real de la vista de 3 pasos de «Efectivo y Equivalentes de
 * Efectivo» (processor efectivo_equivalentes). No hay backend: cada endpoint del
 * ciclo se mockea con page.route(). El objetivo es verificar que:
 *   - se navega AUD → «Generación de herramientas NIIF» → «Pruebas del encargo»,
 *   - se abre una prueba cuya definicion.processor === "efectivo_equivalentes",
 *   - se monta VistaProceso (los 3 pasos) con sus 4 tarjetas primarias y sus 11
 *     tarjetas de ejecución (incluida la de reproceso),
 *   - con estado NO procesado las tarjetas de ejecución muestran «BLOQUEADO»,
 *   - con estado EJECUTADO las tarjetas quedan habilitadas y, como efectivo tiene
 *     `reproceso: true`, la tarjeta de reproceso abre el panel de la matriz
 *     (endpoint /reproceso).
 */

const CLIENTE = "Comercial Andina de Ejemplo S.A.";
const ENCARGO_ID = 601;
const PRUEBA_ID = 801;

// Requerimientos RQ-001..RQ-012 del procesador efectivo (ver definicion() en
// backend/app/aud/niif/procesadores/efectivo_equivalentes.py). Los títulos de las
// tarjetas primarias los pone procesoConfig.js (CONFIG.efectivo); aquí solo importa
// que existan esos ids con su bandera required.
const REQUESTS = [
  { id: "RQ-001", document: "Anexo de cuentas de caja, bancos e inversiones al corte", required: true, formats: ["xlsx"] },
  { id: "RQ-002", document: "Partidas conciliatorias de cada cuenta al corte", required: false, formats: ["xlsx"] },
  { id: "RQ-003", document: "Conciliaciones y estados bancarios del mes de corte", required: true, formats: ["pdf", "xlsx"] },
  { id: "RQ-004", document: "Estados bancarios posteriores al corte", required: true, formats: ["pdf", "xlsx"] },
  { id: "RQ-005", document: "Respuestas de confirmación bancaria recibidas por el auditor", required: true, formats: ["pdf"] },
  { id: "RQ-006", document: "Contratos de garantía, pignoración, embargos o fideicomisos", required: false, formats: ["pdf", "docx"] },
  { id: "RQ-007", document: "Certificados y contratos de inversiones equivalentes", required: false, formats: ["pdf"] },
  { id: "RQ-008", document: "Política contable de efectivo y equivalentes y actas de arqueo", required: true, formats: ["pdf", "docx"] },
  { id: "RQ-009", document: "Libro mayor (auxiliar de bancos) del período", required: false, formats: ["xlsx"] },
  { id: "RQ-010", document: "Estado de cuenta bancario del mes (movimientos)", required: false, formats: ["xlsx"] },
  { id: "RQ-011", document: "Conciliación bancaria del mes anterior (partidas abiertas)", required: false, formats: ["xlsx"] },
  { id: "RQ-012", document: "Arqueo de caja (recuento por denominación)", required: false, formats: ["xlsx"] },
];

// Matriz de reproceso que devuelve el endpoint /reproceso cuando la prueba está
// procesada (una fila por cuenta cruzable).
const MATRIZ_REPROCESO = {
  disponible: true,
  matriz: [
    {
      banco: "Banco del Pacífico · Cta. 100200",
      saldo_extracto: 125430.11, saldo_libros: 125430.11, saldo_auditoria: 125430.11,
      diferencia: 0, estado: "CONCILIADA", coincidencias: 42, n_partidas_reproceso: 3,
    },
    {
      banco: "Banco Pichincha · Cta. 300400",
      saldo_extracto: 80125.5, saldo_libros: 80320.5, saldo_auditoria: 80125.5,
      diferencia: 195, estado: "CON DIFERENCIA", coincidencias: 28, n_partidas_reproceso: 5,
    },
  ],
};

const jsonRoute = (route, body, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

// Prueba de efectivo en el estado pedido. `procesada` decide la cobertura.
function pruebaEfectivo(estado) {
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
    origen: "proc:efectivo_equivalentes",
    archivos: [],
    cobertura,
    eventos: [
      { fecha: "2026-09-26T10:00:00", actor: "admin@auditbrain.test", accion: "create", estado_nuevo: "PRUEBA_SELECCIONADA" },
    ],
    definicion: {
      processor: "efectivo_equivalentes",
      name: "Efectivo y Equivalentes de Efectivo",
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
      { id: PRUEBA_ID, nombre: "Efectivo y Equivalentes de Efectivo", version: 1, estado, origen: "proc:efectivo_equivalentes" },
    ])
  );
  // Catálogo de herramientas (selector de nueva prueba).
  await page.route("**/api/v1/aud/ciclo/herramientas", (route) =>
    jsonRoute(route, [{ origen: "proc:efectivo_equivalentes", nombre: "Efectivo y Equivalentes de Efectivo", tipo: "Procesador" }])
  );
  // Registros del encargo (RegistroEncargo se monta dentro de un <details> colapsado).
  await page.route("**/api/v1/aud/ciclo/proyectos/*/registros", (route) =>
    jsonRoute(route, { registros: [], usuario: { email: ADMIN_USER.email }, ciclos: [], consultas: [] })
  );
  // Piloto guiado (sección por defecto de CentroNIIF antes de cambiar de subpestaña).
  await page.route("**/api/v1/aud/niif/piloto/pruebas", (route) => jsonRoute(route, []));
  // Reproceso de la conciliación del último mes (tarjeta con reproceso: true).
  await page.route(/\/api\/v1\/aud\/ciclo\/pruebas\/\d+\/reproceso$/, (route) =>
    jsonRoute(route, MATRIZ_REPROCESO)
  );
  // Descarga del Excel del reproceso (por si se pulsa el botón de la matriz).
  await page.route(/\/api\/v1\/aud\/ciclo\/pruebas\/\d+\/reproceso-excel$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      body: Buffer.from("PK-reproceso-xlsx-mock"),
    })
  );
  // Lectura de la prueba: dispara el render de VistaProceso.
  await page.route(/\/api\/v1\/aud\/ciclo\/pruebas\/\d+$/, (route) =>
    jsonRoute(route, pruebaEfectivo(estado))
  );
}

// Navega desde el login hasta abrir la prueba de efectivo.
async function abrirEfectivo(page) {
  await login(page);
  // AUD → Workspace cognitivo.
  await page.locator("aside.cc-side").getByRole("button", { name: /External Audit/i }).click();
  // Pestaña «Generación de herramientas NIIF».
  await page.getByRole("button", { name: /Generación de herramientas NIIF/i }).click();
  // Subpestaña «Pruebas del encargo» dentro de CentroNIIF.
  await page.locator("nav.nf-subtabs").getByRole("button", { name: /^Pruebas del encargo$/ }).click();
  // Desplegar la lista de pruebas y abrir la de efectivo.
  await page.locator("details.nf-registro-colapsado > summary").first().click();
  await page.getByRole("button", { name: /Efectivo y Equivalentes de Efectivo · v1/ }).click();
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

  // Las 4 tarjetas primarias de CONFIG.efectivo (encabezados h4 del paso 1).
  await expect(page.getByRole("heading", { name: "Anexo de Caja y Bancos", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Conciliaciones Bancarias", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Estados de Cuenta Bancarios", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mayores Contables", exact: true })).toBeVisible();

  // Las 11 tarjetas de ejecución del paso 3 se renderizan (una por clave de
  // CONFIG.efectivo.ejecuciones).
  await expect(page.locator("button.nf-ef-ejec-card")).toHaveCount(11);

  // Verificación puntual de al menos 5 tarjetas de ejecución, incluida la de reproceso.
  await expect(page.locator("button.nf-ef-ejec-card", { hasText: "Sumaria" })).toBeVisible();
  await expect(page.locator("button.nf-ef-ejec-card", { hasText: "Corte de Documentos" })).toBeVisible();
  await expect(page.locator("button.nf-ef-ejec-card", { hasText: "Confirmaciones Bancarias" })).toBeVisible();
  await expect(page.locator("button.nf-ef-ejec-card", { hasText: "Arqueo de Caja" })).toBeVisible();
  await expect(page.locator("button.nf-ef-ejec-card", { hasText: /Reproceso de Conciliación Bancaria/ })).toBeVisible();
}

test.describe("Efectivo y Equivalentes de Efectivo · vista de 3 pasos (efectivo_equivalentes)", () => {
  test("estado NO procesado: se renderizan los 3 pasos y la ejecución está BLOQUEADA", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await mockCiclo(page, "REQUERIMIENTO_APROBADO");
    await abrirEfectivo(page);

    await verificarVistaTresPasos(page);

    // Sin procesar: las tarjetas de ejecución muestran «BLOQUEADO» y están deshabilitadas.
    await expect(page.getByText(/BLOQUEADO/).first()).toBeVisible();
    const sumaria = page.locator("button.nf-ef-ejec-card", { hasText: "Sumaria" });
    await expect(sumaria).toBeDisabled();
    // La tarjeta de reproceso también está bloqueada.
    const reproceso = page.locator("button.nf-ef-ejec-card", { hasText: /Reproceso de Conciliación Bancaria/ });
    await expect(reproceso).toBeDisabled();
  });

  test("estado EJECUTADO: las tarjetas de ejecución quedan habilitadas y el reproceso aparece habilitado", async ({ page }) => {
    await mockApi(page, { user: ADMIN_USER });
    await mockCiclo(page, "PRUEBA_EJECUTADA");
    await abrirEfectivo(page);

    await verificarVistaTresPasos(page);

    // Procesada: no hay «BLOQUEADO» y las tarjetas de ejecución están habilitadas.
    await expect(page.getByText(/BLOQUEADO/)).toHaveCount(0);
    const sumaria = page.locator("button.nf-ef-ejec-card", { hasText: "Sumaria" });
    await expect(sumaria).toBeEnabled();

    // efectivo tiene reproceso: true. La tarjeta de reproceso muestra su texto y queda
    // habilitada (lista para abrir el panel de la matriz que sirve el endpoint /reproceso,
    // ya mockeado en mockCiclo).
    const reproceso = page.locator("button.nf-ef-ejec-card", { hasText: /Reproceso de Conciliación Bancaria/ });
    await expect(reproceso).toBeVisible();
    await expect(reproceso).toBeEnabled();
  });
});
