// Lógica pura del agente guía «NIIF Piloto» (sin React ni red), para poder
// probarla en aislamiento (pilotoLogic.test.js). El componente PilotoGuiado.jsx
// solo orquesta estado y llamadas a la API con estos helpers.

// Agrupa las pruebas por rubro conservando el orden de llegada (la matriz del socio).
export function agruparPorRubro(pruebas) {
  const grupos = [];
  const indice = new Map();
  for (const p of pruebas || []) {
    const rubro = p.rubro || "General";
    if (!indice.has(rubro)) {
      indice.set(rubro, grupos.length);
      grupos.push({ rubro, pruebas: [] });
    }
    grupos[indice.get(rubro)].pruebas.push(p);
  }
  return grupos;
}

// Filtro por texto sobre id, nombre y rubro (sin tildes, sin distinguir mayúsculas).
export function filtrarPruebas(pruebas, texto) {
  const q = _norm(texto);
  if (!q) return pruebas || [];
  return (pruebas || []).filter((p) =>
    _norm(`${p.id} ${p.nombre} ${p.rubro}`).includes(q)
  );
}

function _norm(s) {
  return String(s || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

// Las columnas (keys) de un dataset de los requisitos.
export function columnasDe(dsSpec) {
  return (dsSpec?.campos || []).map((c) => c.key);
}

// Una fila en blanco con todas las columnas del dataset.
export function filaVacia(dsSpec) {
  const fila = {};
  for (const key of columnasDe(dsSpec)) fila[key] = "";
  return fila;
}

// ¿Todos los valores de la fila están vacíos? (para descartarla al enviar).
export function filaEstaVacia(fila) {
  return Object.values(fila || {}).every((v) => String(v ?? "").trim() === "");
}

// Toma el molde (ejemplo del manifiesto) y devuelve, por dataset, filas que solo
// conservan las columnas declaradas en los requisitos (ignora claves extra).
export function filasDesdeMolde(requisitos, molde) {
  const out = {};
  for (const ds of requisitos?.datasets || []) {
    const cols = columnasDe(ds);
    const filas = (molde?.datasets?.[ds.dataset] || []).map((f) => {
      const limpia = {};
      for (const k of cols) limpia[k] = f?.[k] ?? "";
      return limpia;
    });
    out[ds.dataset] = filas.length ? filas : [filaVacia(ds)];
  }
  return out;
}

// Estado inicial del grid: una fila vacía por dataset.
export function gridInicial(requisitos) {
  const out = {};
  for (const ds of requisitos?.datasets || []) out[ds.dataset] = [filaVacia(ds)];
  return out;
}

// Construye el payload {corte, datasets, parametros, encargo} para la API.
// - descarta filas totalmente vacías;
// - envía solo parámetros con valor no vacío (sobre los del defecto ya en backend);
// - envía solo campos del encargo con valor.
export function cuerpoEjecucion({ corte, grid, parametros, encargo }) {
  const datasets = {};
  for (const [ds, filas] of Object.entries(grid || {})) {
    const utiles = (filas || []).filter((f) => !filaEstaVacia(f));
    if (utiles.length) datasets[ds] = utiles;
  }
  const params = {};
  for (const [k, v] of Object.entries(parametros || {})) {
    if (v !== null && v !== undefined && String(v).trim() !== "") params[k] = v;
  }
  const enc = {};
  for (const [k, v] of Object.entries(encargo || {})) {
    if (v !== null && v !== undefined && String(v).trim() !== "") enc[k] = v;
  }
  const cuerpo = { corte: (corte || "").trim(), datasets, parametros: params };
  if (Object.keys(enc).length) cuerpo.encargo = enc;
  return cuerpo;
}

// Valida lo mínimo antes de ejecutar: corte y al menos una fila con datos.
export function faltantesParaEjecutar(cuerpo) {
  const faltan = [];
  if (!cuerpo.corte) faltan.push("la fecha de corte");
  const hayFilas = Object.values(cuerpo.datasets || {}).some((f) => f.length);
  if (!hayFilas) faltan.push("al menos una fila de datos");
  return faltan;
}

// Formatos que el backend arma (para los botones de descarga).
export const FORMATOS_PAPEL = [
  { ext: "xlsx", etiqueta: "Excel" },
  { ext: "html", etiqueta: "HTML" },
  { ext: "docx", etiqueta: "Word" },
  { ext: "pptx", etiqueta: "PowerPoint" },
  { ext: "pdf", etiqueta: "PDF" },
  { ext: "zip", etiqueta: "Todo (ZIP)" },
];
