// Historial de descargas del robot SRI: normalización de filas y filtros,
// copiados de la pestaña "Reportes e Historial" de la app de escritorio.

export const COLUMNAS_HISTORIAL = [
  ["timestamp", "Fecha y hora"],
  ["ruc", "RUC"],
  ["origen", "Origen"],
  ["periodo", "Período"],
  ["tipo", "Tipo de comprobante"],
  ["estado", "Estado"],
  ["estado_autorizacion", "Estado autorización"],
  ["establecimiento", "Establecimiento"],
  ["punto_emision", "Punto de emisión"],
  ["conteo", "Descargado"],
];

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

function _txt(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  return s === "nan" || s === "None" ? "" : s;
}

// Fila del servidor → fila lista para mostrar (todas las columnas con texto).
export function normalizarFila(h) {
  const dia = _txt(h.dia);
  const mes = Number(h.mes);
  const anio = _txt(h.anio);
  const periodo = _txt(h.fecha_filtro) || [
    MESES[mes - 1] || _txt(h.mes), anio, dia && dia !== "0" && dia !== "Todos" ? `día ${dia}` : "",
  ].filter(Boolean).join(" ");
  const partes = [];
  if (h.n_registros !== undefined && h.n_registros !== null && h.n_registros !== "") partes.push(`${h.n_registros} comprobantes`);
  if (Number(h.n_xml) > 0) partes.push(`${h.n_xml} XML`);
  if (Number(h.n_pdf) > 0) partes.push(`${h.n_pdf} PDF`);
  return {
    timestamp: _txt(h.timestamp || h.fecha),
    ruc: _txt(h.ruc),
    origen: _txt(h.origen),
    periodo,
    anio,
    tipo: _txt(h.tipo_visible) || _txt(h.tipo),
    estado: _txt(h.estado) || "finalizado",
    estado_autorizacion: _txt(h.estado_autorizacion),
    establecimiento: _txt(h.establecimiento),
    punto_emision: _txt(h.punto_emision),
    conteo: partes.join(" · "),
  };
}

export function opcionesDe(filas, campo) {
  const vals = new Set(filas.map((f) => _txt(f[campo])).filter(Boolean));
  const lista = [...vals].sort((a, b) => (campo === "anio" ? Number(b) - Number(a) : a.localeCompare(b)));
  return ["Todos", ...lista];
}

// Filtros exactos por columna + búsqueda libre en todas las columnas.
export function filtrarHistorial(filas, { busqueda = "", ruc = "Todos", origen = "Todos", tipo = "Todos", anio = "Todos" } = {}) {
  const q = busqueda.trim().toLowerCase();
  return filas.filter((f) =>
    (ruc === "Todos" || f.ruc === ruc)
    && (origen === "Todos" || f.origen === origen)
    && (tipo === "Todos" || f.tipo === tipo)
    && (anio === "Todos" || String(f.anio) === String(anio))
    && (!q || Object.values(f).some((v) => String(v).toLowerCase().includes(q))));
}
