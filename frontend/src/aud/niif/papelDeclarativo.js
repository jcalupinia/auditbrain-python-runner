// Papel de trabajo de las pruebas DECLARATIVAS (catálogo y fichas sin
// procesador) con el MISMO diseño que las pruebas con procesador: portada del
// Excel = panel del HTML, HTML ejecutivo, Word (HTML impreso) y PowerPoint (HTML
// en pantalla), con los logotipos de AuditConsulting y AUDIT-IA.
//
// El diseño vive en un solo lugar, el servidor (procesadores/libro.py). El
// navegador solo aporta las cédulas con fórmulas del exportador del sitio
// (`workbookSheets`), que siguen siendo la fuente de cada fórmula: el servidor
// las escribe en las mismas celdas, así que ninguna referencia cambia. El
// exportador del sitio (./sitio/) es una copia que no se edita aquí.
import { sheetLabels, sheetNames, workbookSheets } from "./sitio/tools/exports.mjs";

export const MIME = {
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  html: "text/html;charset=utf-8",
  pdf: "application/pdf",
};

/**
 * Lo que el servidor necesita para armar el papel: la herramienta sin la
 * población (ya viaja dentro de las cédulas de datos) ni el detalle del motor
 * fila a fila (también está en las cédulas), y las cédulas con sus nombres y
 * rótulos tal como las arma el exportador del sitio.
 */
export function cargaPapel(t) {
  // eslint-disable-next-line no-unused-vars
  const { rows, validation, datasets, flows, ...resto } = t;
  const run = t.run || {};
  return {
    herramienta: { ...resto, run: { engine: run.engine, totals: run.totals || {}, exceptions: run.exceptions || [] } },
    cedulas: { nombres: sheetNames(t.definition), etiquetas: sheetLabels(t.definition), hojas: workbookSheets(t) },
  };
}

export const nombreBase = (t) => `${String(t.definition?.name || "prueba").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^\w-]+/g, "_").slice(0, 60)}_v${t.version}`;
