// Lógica pura del Motor de Ingesta (presentación/etiquetas). Sin React ni DOM:
// se testea con Vitest-node igual que vnr/logic.js. El componente .jsx solo la
// consume para pintar. El contrato de datos lo define el backend
// (backend/app/ingesta/contract.py): niveles de confianza, métodos de
// extracción, evidencia hasta el origen.

// Niveles de confianza del contrato, de mejor a peor (coincide con el orden de
// severidad del backend: HIGH < MEDIUM < LOW < REVIEW_REQUIRED).
export const NIVELES = ["HIGH", "MEDIUM", "LOW", "REVIEW_REQUIRED"];

const NIVEL_ETIQUETA = {
  HIGH: "Alta",
  MEDIUM: "Media",
  LOW: "Baja",
  REVIEW_REQUIRED: "Revisar",
};

const NIVEL_CLASE = {
  HIGH: "ing-nivel-alta",
  MEDIUM: "ing-nivel-media",
  LOW: "ing-nivel-baja",
  REVIEW_REQUIRED: "ing-nivel-revisar",
};

const METODO_ETIQUETA = {
  nativo: "Nativo",
  parser: "Parser SRI",
  regla: "Regla",
  regex: "Regex",
  tabla: "Tabla",
  ocr: "OCR",
  ia: "IA",
  manual: "Manual",
};

const TIPO_ETIQUETA = {
  f101: "Formulario 101 · Renta",
  f103: "Formulario 103 · Retenciones",
  f104: "Formulario 104 · IVA",
  ats: "ATS",
  balance: "Balance",
  mayor: "Libro Mayor",
  kardex: "Kardex",
  facturacion: "Facturación",
  comprobante_sri: "Comprobante SRI",
  estado_financiero: "Estado financiero",
  carta_control_interno: "Carta de control interno",
  informe_auditoria: "Informe de auditoría",
  notas_eeff: "Notas a los EEFF",
  contrato: "Contrato",
  desconocido: "Desconocido",
};

// Normaliza un nivel desconocido/ausente al más conservador (nunca oculta la
// incertidumbre: la regla del contrato es que la duda escala, no se pierde).
export function nivelNormalizado(nivel) {
  return NIVELES.includes(nivel) ? nivel : "REVIEW_REQUIRED";
}

export function nivelEtiqueta(nivel) {
  return NIVEL_ETIQUETA[nivelNormalizado(nivel)];
}

export function nivelClase(nivel) {
  return NIVEL_CLASE[nivelNormalizado(nivel)];
}

export function metodoEtiqueta(metodo) {
  return METODO_ETIQUETA[metodo] || metodo || "—";
}

export function tipoEtiqueta(tipo) {
  return TIPO_ETIQUETA[tipo] || tipo || "Desconocido";
}

// "archivo.pdf · p. 3 · hoja 1 Disenio · fila 12 · celda B4" — la trazabilidad
// al origen tal como la trae Evidencia. Devuelve "" si no hay evidencia.
export function evidenciaTexto(ev) {
  if (!ev) return "";
  const partes = [ev.source_file];
  if (ev.source_page != null) partes.push("p. " + ev.source_page);
  if (ev.source_sheet) partes.push("hoja " + ev.source_sheet);
  if (ev.source_row != null) partes.push("fila " + ev.source_row);
  if (ev.source_cell) partes.push("celda " + ev.source_cell);
  return partes.filter((p) => p != null && p !== "").join(" · ");
}

// Valor a mostrar de un campo: el normalizado si existe, si no el crudo.
export function formatValor(campo) {
  const v = campo && campo.normalized_value;
  if (v === null || v === undefined || v === "") {
    return (campo && campo.raw_value) || "";
  }
  return String(v);
}

// quality_score (0..1) -> entero 0..100 para la barra de calidad.
export function qualityPct(score) {
  const n = Number(score);
  if (!isFinite(n)) return 0;
  return Math.round(Math.max(0, Math.min(1, n)) * 100);
}

// Distribución de confianza de los campos (para el panel-resumen). No sustituye
// al resumen del backend; es una vista rápida del lado cliente.
export function resumenCampos(campos) {
  const por = { HIGH: 0, MEDIUM: 0, LOW: 0, REVIEW_REQUIRED: 0 };
  const lista = Array.isArray(campos) ? campos : [];
  for (const c of lista) {
    por[nivelNormalizado(c && c.confidence)] += 1;
  }
  const total = lista.length;
  const dudosos = por.LOW + por.REVIEW_REQUIRED;
  return {
    total,
    por,
    dudosos,
    pct_dudosos: total ? dudosos / total : 0,
  };
}
