// Lógica pura de «Pruebas del encargo» (sin React, para probarla).
//
// Las reglas del ciclo viven en el servidor (backend/app/aud/niif/ciclo). Aquí
// solo se decide cómo pintar: en qué etapa está una prueba y cómo editar el
// vínculo entre fuentes y procedimientos.

// Las 9 etapas de `steps` en auditbrain-site/lib/workflow.mjs.
export const ETAPAS = [
  "Datos del encargo",
  "Selección de prueba",
  "Programa de trabajo",
  "Requerimiento",
  "Documentación",
  "Ejecución",
  "Análisis de resultados",
  "Revisión y aprobación",
  "Descarga final",
];

// Estado del sitio (STATES de domain.mjs) → índice de etapa (0 = primera).
const ETAPA_DE_ESTADO = {
  PRUEBA_SELECCIONADA: 1,
  PROGRAMA_PROPUESTO: 2,
  PROGRAMA_APROBADO: 2,
  REQUERIMIENTO_GENERADO: 3,
  REQUERIMIENTO_APROBADO: 3,
  DOCUMENTACION_RECIBIDA: 4,
  DOCUMENTACION_VALIDADA: 4,
  PRUEBA_CONFIGURADA: 5,
  METODOLOGIA_APROBADA: 5,
  PRUEBA_EJECUTADA: 5,
  RESULTADOS_ANALIZADOS: 6,
  EN_REVISION: 7,
  APROBADO: 8,
};

export const etapaDe = (estado) => ETAPA_DE_ESTADO[estado] ?? 0;

// «PROGRAMA_PROPUESTO» → «Programa propuesto».
// Los estados del sitio van sin tildes (son códigos); al mostrarlos se ponen.
const TILDES = { documentacion: "documentación", metodologia: "metodología", revision: "revisión" };
export const nombreEstado = (estado) => {
  const t = String(estado || "").toLowerCase().split("_").map((w) => TILDES[w] || w).join(" ");
  return t.charAt(0).toUpperCase() + t.slice(1);
};

// Marca o desmarca un procedimiento en una fuente, sin tocar las demás.
export function alternarProcedimiento(fuentes, indice, codigo) {
  return fuentes.map((s, i) => {
    if (i !== indice) return s;
    const actual = s.procedures || [];
    const procedures = actual.includes(codigo) ? actual.filter((c) => c !== codigo) : [...actual, codigo];
    return { ...s, procedures };
  });
}

// Procedimientos que todavía no tienen ninguna fuente verificada: el servidor
// rechaza aprobar el programa mientras quede alguno.
export function procedimientosSinFuente(programa, fuentes) {
  return (programa || [])
    .map((p) => p.code)
    .filter((code) => !(fuentes || []).some((s) => s.verified && (s.procedures || []).includes(code)));
}

// Campos de la ficha del encargo, en el orden del sitio.
export const CAMPOS_FICHA = [
  "client", "ruc", "activity", "year", "cutoff", "preparer", "reviewer", "firm",
  "framework", "edition", "adoption", "country", "currency", "visit", "reuseScope", "deferredTax",
];

export const fichaInicial = (cliente) => ({
  client: cliente || "",
  country: "Ecuador",
  currency: "USD",
  visit: "Final",
  firm: "Audit Consulting",
  reuseScope: "one",
  deferredTax: false,
});

// --- E7: requerimiento y documentación -------------------------------------

// «Quito, Guayaquil» → ["Quito", "Guayaquil"]: sin vacíos ni repetidos.
export const componentesDeTexto = (texto) =>
  [...new Set(String(texto || "").split(/[,;\n]/).map((x) => x.trim()).filter(Boolean))];

// Solo XLSX y CSV sirven como población (la misma regla del lector del sitio).
export const esTabular = (nombre) => /\.(xlsx|csv)$/i.test(String(nombre || ""));

const normal = (t) =>
  String(t ?? "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]/g, "");

// Propone el mapeo campo → columna comparando la etiqueta y el código del campo
// con los encabezados. Es solo una sugerencia: el auditor la revisa.
export function mapeoSugerido(encabezados, campos) {
  const cols = (encabezados || []).map(normal);
  const mapa = {};
  for (const f of campos || []) {
    const i = cols.findIndex((c) => c && (c === normal(f.label) || c === normal(f.key)));
    if (i >= 0) mapa[f.key] = i;
  }
  return mapa;
}

// Los primeros errores de validación, legibles: «Fila 8 · Cantidad: número inválido.»
export const erroresLegibles = (validacion, max = 20) =>
  (validacion?.errors || []).slice(0, max).map((e) => `Fila ${e.row} · ${e.message}`);

// Lo que la ficha dice de cada requerimiento (encargo NIIF): qué reporte es, si
// la herramienta lo procesa, qué período cubre y qué debe traer para aceptarlo.
export function detalleRequerimiento(r) {
  return [
    r.use === "calculo" ? "Alimenta el cálculo" : r.use === "soporte" ? "Soporte" : "",
    r.report ? `Reporte: ${r.report}` : "",
    r.timing ? `Período: ${r.timing}` : "",
    r.content ? `Contenido mínimo: ${r.content}` : "",
  ].filter(Boolean);
}
