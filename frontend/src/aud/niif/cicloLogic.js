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
export const nombreEstado = (estado) => {
  const t = String(estado || "").toLowerCase().replace(/_/g, " ");
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
