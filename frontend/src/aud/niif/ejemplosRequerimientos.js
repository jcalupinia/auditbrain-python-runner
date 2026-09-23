/*
 * Ejemplos «formato válido con datos ficticios» por procesador y requerimiento.
 *
 * Los archivos son estáticos y viven en
 *   frontend/public/ejemplos/<processor>/<archivo>
 * (se generan con scripts/ejemplos_<procesador>.py). El manifiesto solo mapea
 * processor → { requerimiento: nombre de archivo }.
 *
 * Cuando una herramienta no tenga ejemplos propios aquí, la flecha de la vista
 * usa el modelo en blanco del propio requerimiento (bajarModelo) si alimenta el
 * cálculo (req.dataset); si no, no se muestra flecha y solo quedan los formatos.
 */
export const EJEMPLOS_REQUERIMIENTOS = {
  perdidas_incurridas_s11: {
    "RQ-001": "RQ-001_cartera_2025.xlsx",
    "RQ-002": "RQ-002_cartera_2024.xlsx",
    "RQ-003": "RQ-003_cartera_2023.xlsx",
    "RQ-004": "RQ-004_provision_inicial_2025.xlsx",
    "RQ-005": "RQ-005_movimiento_provision_3_ejercicios.xlsx",
    "RQ-006": "RQ-006_cobros_posteriores_al_cierre.xlsx",
    "RQ-007": "RQ-007_politica_credito_cobranza.docx",
    "RQ-008": "RQ-008_ventas_por_factura_3_ejercicios.xlsx",
  },
};

/**
 * Qué ofrece la flecha «↓ Ejemplo» para un requerimiento:
 *   { tipo: "ejemplo", archivo, url } → hay un ejemplo lleno en el manifiesto (descarga estática)
 *   { tipo: "modelo" }                → no hay ejemplo, pero el requerimiento alimenta el cálculo
 *                                        (req.dataset) → se baja el modelo en blanco con bajarModelo
 *   null                              → no hay ninguno; la vista solo muestra los formatos aceptados
 *
 * `base` es el prefijo público (import.meta.env.BASE_URL) para armar la URL estática.
 */
export function ejemploDe(processor, req, manifest = EJEMPLOS_REQUERIMIENTOS, base = "") {
  if (!req) return null;
  const archivo = processor && manifest[processor] && manifest[processor][req.id];
  if (archivo) return { tipo: "ejemplo", archivo, url: `${base}ejemplos/${processor}/${archivo}` };
  if (req.dataset) return { tipo: "modelo" };
  return null;
}

/** Formatos aceptados en mayúsculas para la vista, p. ej. «XLSX · CSV». */
export function formatosTexto(req) {
  return (req?.formats || []).map((f) => String(f).toUpperCase()).join(" · ");
}
