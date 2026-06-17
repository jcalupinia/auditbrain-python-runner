// Generador del Dashboard Ejecutivo autocontenido (CFO Intelligence).
// Reutiliza la plantilla HTML validada (artefacto Galápagos) e inyecta los
// datos reales del cliente. El archivo resultante abre con doble clic, sin
// servidor ni internet, y es interactivo (editar, filtrar año, exportar).

import TEMPLATE from "./dashboard_template.html?raw";
import { mapToDashboard, FIN_YRS, buildDetailedBalance } from "./finModel.js";

// Escapa una cadena para incrustarla como literal JS seguro.
const jsStr = (s) =>
  JSON.stringify(s == null ? "" : String(s)).slice(1, -1).replace(/<\/script/gi, "<\\/script");

// Construye el HTML autocontenido a partir del modelo `D` + cabecera + detalle.
// `periodos` (opcional) define las columnas/etiquetas; si falta, usa FIN_YRS.
// `D` debe venir ya normalizado (ER prorrateado) por el llamador.
export function buildStandaloneHTML({ D, header, detalle, nivel, periodos, cuentas }) {
  const labels = periodos && periodos.length ? periodos.map((p) => p.label) : FIN_YRS;
  // Etiquetas propias del balance (fechas de corte distintas a las del ER si aplica).
  const labelsESF = periodos && periodos.length ? periodos.map((p) => p.labelESF || p.label) : labels;
  const dash = mapToDashboard(D, labels);
  const balDet = buildDetailedBalance(D, labels);
  const det = {
    gastos: (detalle?.gastos || []).filter((r) => (r.concepto || "").trim()),
    atipicos: (detalle?.atipicos || []).filter((r) => (r.concepto || "").trim()),
    activos: (detalle?.activos || []).filter((r) => (r.desc || "").trim()),
    inversiones: (detalle?.inversiones || []).filter((r) => (r.instrumento || "").trim()),
  };
  const niv = nivel === "detallado" ? "detallado" : "resumido";
  return TEMPLATE
    .replace("__DATA__", JSON.stringify(dash))
    .replace("__DETALLE__", JSON.stringify(det))
    .replace("__BALANCE_DET__", JSON.stringify(balDet))
    .replace("__CUENTAS__", JSON.stringify(Array.isArray(cuentas) ? cuentas : []))
    .replace("__LBL_ESF__", JSON.stringify(labelsESF))
    .replace("__THEME__", JSON.stringify(header?.theme || "ejecutivo"))
    .replace("__LAYOUT__", JSON.stringify(header?.layout || "ejecutivo"))
    .replace("__CHART__", JSON.stringify(header?.chart || "combo"))
    .replace("__NIVEL__", JSON.stringify(niv))
    .replace("__YRS__", JSON.stringify(labels))
    .replace("__MESES__", JSON.stringify(periodos && periodos.length ? periodos.map((p) => p.meses || 12) : labels.map(() => 12)))
    .replace(/__EMPRESA__/g, jsStr(header?.empresa || "Empresa"))
    .replace("__SUBTITULO__", jsStr(header?.subtitulo || ""))
    .replace("__PIE__", jsStr(header?.pie || ""));
}

// Genera y descarga el archivo .html.
export function downloadStandaloneHTML(args) {
  const html = buildStandaloneHTML(args);
  const empresa = args?.header?.empresa || "cliente";
  const safe = String(empresa).replace(/[\s/\\]+/g, "_") || "cliente";
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Dashboard_Ejecutivo_${safe}.html`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
