import { test, expect } from "@playwright/test";
import { mockApi, login, ADMIN_USER } from "./helpers.js";

/*
 * Recorrido de UI parametrizado de la vista de 3 pasos (VistaProceso) para el
 * resto de herramientas del catálogo que la adoptaron (Etapas 2-5). Un mismo
 * spec sirve para todas porque la vista es config-driven (procesoConfig.js).
 * Por cada herramienta se verifica que se montan los 3 pasos con sus tarjetas
 * primarias, que renderizan TODAS sus tarjetas de ejecución (toHaveCount), y el
 * estado bloqueado/habilitado. Efectivo y planificación tienen sus propios
 * specs (efectivo.spec.js, planificacion.spec.js) y la Etapa 1 el suyo
 * (catalogo_3pasos.spec.js).
 */

const CLIENTE = "Cliente Demo S.A.";
const ENCARGO_ID = 950;
const PRUEBA_ID = 1200;
const PROCESADAS = ["PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS", "EN_REVISION", "APROBADO"];

// nEjec = número de tarjetas de ejecución de cada config; primarias = 2 títulos
// de tarjetas primarias que deben renderizar (procesoConfig.js).
const TOOLS = [
  { processor: "ppe_propiedad_planta", nombre: "Propiedad, Planta y Equipo", nEjec: 12, primarias: ["Variaciones de Cuentas (Sumaria)", "Libro Mayor de Activos Fijos"] },
  { processor: "propiedades_inversion", nombre: "Propiedades de Inversión", nEjec: 11, primarias: ["Registro de Propiedades de Inversión", "Escrituras y Certificados del Registro"] },
  { processor: "intangibles_goodwill", nombre: "Intangibles y Goodwill", nEjec: 9, primarias: ["Auxiliar de Intangibles y Goodwill", "Contratos de Licencias, Marcas y Patentes"] },
  { processor: "activos_biologicos", nombre: "Activos Biológicos", nEjec: 8, primarias: ["Anexo de Activos Biológicos por Lote", "Actas de Conteo y Registros de Campo"] },
  { processor: "prestamos_obligaciones", nombre: "Préstamos y Obligaciones Financieras", nEjec: 10, primarias: ["Anexo de Préstamos al Corte", "Contratos y Tablas de Amortización"] },
  { processor: "inversiones_instrumentos", nombre: "Inversiones e Instrumentos Financieros", nEjec: 9, primarias: ["Anexo de Inversiones por Instrumento", "Estados de Cuenta y Confirmaciones"] },
  { processor: "patrimonio", nombre: "Patrimonio", nEjec: 9, primarias: ["Movimiento de Cuentas Patrimoniales", "Actas y Transacciones Patrimoniales"] },
  { processor: "provisiones_contingencias", nombre: "Provisiones y Contingencias", nEjec: 11, primarias: ["Detalle de Provisiones y Contingencias", "Respuestas de los Abogados"] },
  { processor: "nomina_beneficios", nombre: "Nómina y Beneficios a Empleados", nEjec: 11, primarias: ["Anexo de Empleados del Ejercicio", "Resumen del Informe Actuarial"] },
  { processor: "impuesto_corriente_diferido", nombre: "Impuesto Corriente y Diferido", nEjec: 11, primarias: ["Conciliación Tributaria (F-101)", "Anexo de Diferencias Temporarias"] },
  { processor: "gastos_analisis", nombre: "Análisis de Gastos", nEjec: 11, primarias: ["Sumaria de Cuentas de Gasto", "Muestra de Transacciones de Gasto"] },
  { processor: "seguros_cobertura", nombre: "Seguros y Cobertura", nEjec: 9, primarias: ["Maestro de Activos Asegurables", "Detalle de Pólizas Vigentes y Vencidas"] },
  { processor: "arrendamientos", nombre: "Arrendamientos", nEjec: 11, primarias: ["Anexo de Contratos de Arrendamiento", "Contratos Firmados y Adendas"] },
  { processor: "pce_simplificada_niif9", nombre: "Pérdida Crediticia Esperada (NIIF 9)", nEjec: 10, primarias: ["Cartera por Factura al Corte", "Cartera por Factura del Corte Anterior"] },
  { processor: "perdidas_incurridas_s11", nombre: "Pérdidas Incurridas (Sección 11)", nEjec: 10, primarias: ["Cartera por Factura al Cierre Corriente", "Cartera por Factura del Cierre Anterior"] },
];

const jsonRoute = (route, body, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

function pruebaDe(tool, estado) {
  const procesada = PROCESADAS.includes(estado);
  // Superset de requerimientos RQ-001..RQ-012 para que cualquier primaria se case por id.
  const requests = Array.from({ length: 12 }, (_, i) => ({
    id: `RQ-0${String(i + 1).padStart(2, "0")}`,
    document: `Documento ${i + 1}`,
    required: i < 4,
    formats: ["xlsx"],
  }));
  const cobertura = requests.map((r, i) => ({ id: r.id, complete: procesada ? true : i < 2, rejected: false }));
  return {
    id: PRUEBA_ID, version: 1, revision: 0, estado, origen: `proc:${tool.processor}`, archivos: [], cobertura,
    eventos: [{ fecha: "2026-09-26T10:00:00", actor: ADMIN_USER.email, accion: "create", estado_nuevo: "PRUEBA_SELECCIONADA" }],
    definicion: { processor: tool.processor, name: tool.nombre, requests, parametros: {} },
    registro: { methodologyVersion: "NIA-2026.1", engagement: { client: CLIENTE, framework: "NIIF para las PYMES" }, requests, parameters: {}, run: { exceptions: [] } },
  };
}

async function mockCiclo(page, tool, estado) {
  await page.route("**/api/v1/aud/ciclo/encargos", (route) =>
    jsonRoute(route, [{ id: ENCARGO_ID, cliente: CLIENTE, nombre: "Auditoría 2025", marco: "NIIF para las PYMES", pruebas: 1 }]));
  await page.route("**/api/v1/aud/ciclo/proyectos/*/ficha", (route) =>
    jsonRoute(route, { ficha: { client: CLIENTE, ruc: "1790012345001", framework: "NIIF para las PYMES", edition: "2015", cutoff: "2025-12-31", currency: "USD", visit: "Final", preparer: "A. Auditor", reviewer: "B. Revisor", firm: "AuditConsulting Auditores Cía. Ltda." } }));
  await page.route("**/api/v1/aud/ciclo/proyectos/*/pruebas", (route) =>
    jsonRoute(route, [{ id: PRUEBA_ID, nombre: tool.nombre, version: 1, estado, origen: `proc:${tool.processor}` }]));
  await page.route("**/api/v1/aud/ciclo/herramientas", (route) =>
    jsonRoute(route, [{ origen: `proc:${tool.processor}`, nombre: tool.nombre, tipo: "Procesador" }]));
  await page.route("**/api/v1/aud/ciclo/proyectos/*/registros", (route) =>
    jsonRoute(route, { registros: [], usuario: { email: ADMIN_USER.email }, ciclos: [], consultas: [] }));
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
