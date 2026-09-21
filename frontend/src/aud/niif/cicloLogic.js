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
    const nombres = [f.label, f.key, ...(f.aliases || [])].map(normal);
    const i = cols.findIndex((c) => c && nombres.includes(c));
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

// E8 · Objeto «herramienta» que esperan buildWorkbook/buildHtml del sitio,
// armado con lo que guardó el servidor: el registro de la prueba tiene la
// misma forma que el del sitio; aquí solo se le agregan definición, estado,
// versión y la bitácora con los nombres del sitio (cédula 12).
export function herramientaDePrueba(p) {
  const reg = p.registro || {};
  return {
    ...reg,
    id: String(p.id),
    definition: p.definicion,
    version: p.version,
    state: p.estado,
    // «draft» es, para el sitio, un borrador de ChatGPT con fuentes sin verificar;
    // una prueba del encargo en curso sale como «papel en proceso» por su estado.
    draft: false,
    events: (p.eventos || []).map((e) => ({
      action: e.accion, actor: e.actor, at: e.fecha, previous: e.estado_anterior,
      next: e.estado_nuevo, comment: e.comentario || "", version: p.version,
    })),
  };
}

// Tramos de mora de la PCE del catálogo: se editan como texto y viajan con
// números enteros y el último «sin límite» (null), como los valida el sitio.
export function tramosDeTexto(filas) {
  return filas.map((f, i) => ({
    min: Number(f.min),
    max: i === filas.length - 1 && String(f.max ?? "").trim() === "" ? null : Number(f.max),
    rate: String(f.rate ?? "").trim(),
  }));
}


// --- E10 · vista de trabajo en cuatro bloques ---------------------------------

// Hoja y fila de encabezados donde se reconocen más campos (prefiere «Datos»,
// la hoja del modelo). Devuelve también los campos obligatorios que faltan.
export function mejorEncabezado(sheets, campos) {
  let mejor = null;
  for (const s of sheets || []) {
    const filas = (s.rows || []).slice(0, 30);
    filas.forEach((fila, i) => {
      const mapping = mapeoSugerido(fila, campos);
      const n = Object.keys(mapping).length + (s.name === "Datos" ? 0.5 : 0);
      if (!mejor || n > mejor.n) mejor = { n, sheet: s.name, header: i + 1, mapping };
    });
  }
  if (!mejor) return null;
  const faltan = (campos || []).filter((f) => f.required !== false && !(f.key in mejor.mapping)).map((f) => f.label || f.key);
  return { sheet: mejor.sheet, header: mejor.header, mapping: mejor.mapping, faltan };
}

const SIMBOLO = { add: "+", subtract: "−", multiply: "×", divide: "÷" };

// Cada cálculo de la ficha en lenguaje contable: «Costo total = Cantidad × Costo unitario».
export function formulasLegibles(d) {
  const nombre = {};
  for (const f of d.fields || []) nombre[f.key] = f.label || f.key;
  for (const r of d.rules || []) nombre[r.key] = r.label || r.key;
  const n = (x) => (x === undefined ? "" : x === "corte" && !nombre.corte ? "fecha de corte" : x.startsWith("#") ? x.slice(1) : nombre[x] || x);
  return (d.rules || []).map((r) => {
    const [a, b, c] = [n(r.a), n(r.b), n(r.c)];
    const expr = SIMBOLO[r.op] ? `${a} ${SIMBOLO[r.op]} ${b}`
      : r.op === "min" ? `el menor entre ${a} y ${b}`
      : r.op === "max" ? `el mayor entre ${a} y ${b}`
      : r.op === "gt" ? `1 si ${a} > ${b}; si no, 0`
      : r.op === "gte" ? `1 si ${a} ≥ ${b}; si no, 0`
      : r.op === "lt" ? `1 si ${a} < ${b}; si no, 0`
      : r.op === "lte" ? `1 si ${a} ≤ ${b}; si no, 0`
      : r.op === "eq" ? `1 si ${a} = ${b}; si no, 0`
      : r.op === "if" ? `si ${a} no es cero, ${b}; si no, ${c}`
      : r.op === "days" ? `días desde ${a} hasta ${b}`
      : r.op === "band" ? `tramo de ${a}: ${(r.table || []).map((t) => `desde ${t.from} → ${t.value}`).join("; ")}`
      : r.op;
    return { key: r.key, texto: `${r.label || r.key} = ${expr}`, principal: r.key === d.primary };
  });
}

const OFICIAL = { NIIF: /(^|\.)ifrs\.org$/, NIA: /(^|\.)(iaasb|ifac)\.org$/ };
const host = (u) => { try { return new URL(u).hostname; } catch { return ""; } };

// Fuentes oficiales confirmadas con la referencia de la ficha: el auditor que
// pulsa «Confirmar base técnica» da fe de haberla revisado (queda en la bitácora).
export function fuentesConfirmadas(p) {
  const d = p.definicion, reg = p.registro;
  const pymes = reg.engagement?.framework === "NIIF para las PYMES";
  const codigos = (reg.program || []).map((x) => x.code);
  const refs = (reg.program || []).map((x) => x.reference).filter(Boolean);
  const vigencia = `Vigente al ${reg.engagement?.cutoff || "corte"}`;
  return (reg.sources || []).map((s) => {
    if (s.category === "NIIF") {
      const f = (pymes ? d.source_pymes : d.source) || {};
      const url = f.url && OFICIAL.NIIF.test(host(f.url)) ? f.url : s.url;
      return { ...s, url, document: f.document || s.document, section: refs.find((r) => !/^NIA/i.test(r)) || f.document || "Según programa de la ficha", date: vigencia, verified: true, procedures: codigos };
    }
    if (s.category === "NIA") {
      return { ...s, document: (d.nia || []).join(", ") || s.document, section: refs.filter((r) => /^NIA/i.test(r)).join("; ") || "Según programa de la ficha", date: vigencia, verified: true, procedures: codigos };
    }
    return { ...s, section: s.section || "Según tratamiento tributario descrito", date: s.date || vigencia, verified: true };
  });
}

// Siguiente paso de «Confirmar base técnica y preparar el requerimiento», o null.
export function pasoPreparar(p, taxScope = "") {
  const reg = p.registro;
  switch (p.estado) {
    case "PRUEBA_SELECCIONADA": return reg.researchedAt ? ["generate_program", {}] : ["research", {}];
    case "PROGRAMA_PROPUESTO": return ["approve_program", { program: reg.program, sources: fuentesConfirmadas(p), taxScope: taxScope || reg.taxScope || "" }];
    case "PROGRAMA_APROBADO": return ["generate_request", {}];
    case "REQUERIMIENTO_GENERADO": return ["approve_request", { requests: reg.requests }];
    default: return null;
  }
}

// Archivos que alimentan el cálculo: los no rechazados, tabulares, de cada requerimiento de cálculo.
export const archivosDe = (p, requerimiento) =>
  (p.archivos || []).filter((a) => a.requerimiento === requerimiento && a.estado !== "rechazado" && esTabular(a.nombre));

// Problemas que la vista de trabajo muestra junto al resultado.
export function problemasDe(p) {
  const reg = p.registro, lista = [];
  const c = reg.reconciliation;
  if (c && !c.within) lista.push(Number(c.ledger) === 0 ? `Saldo del mayor no ingresado: la población suma ${reg.controlTotal}; concilie antes de aprobar.` : `Diferencia con el mayor: ${c.difference} (población ${reg.controlTotal}, mayor ${c.ledger}).`);
  const adv = reg.validation?.warnings || [];
  if (adv.length) lista.push(`${adv.length} advertencia(s) de validación: ${adv.slice(0, 3).map((w) => `fila ${w.row} · ${w.message}`).join("; ")}`);
  const exc = reg.run?.exceptions || [];
  if (exc.length) lista.push(`${exc.length} excepción(es) por partida para evaluar.`);
  return lista;
}
