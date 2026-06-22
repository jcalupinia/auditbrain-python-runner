// Export del Dashboard Ejecutivo a Excel REAL (.xlsx) con ExcelJS.
// Genera hojas: Dashboard, Datos, Config, Imagen (PNG del gráfico embebido),
// Instrucciones. El gráfico se renderiza con Chart.js en un canvas offscreen
// y se incrusta como imagen (SheetJS no puede embeber imágenes; ExcelJS sí).
import ExcelJS from "exceljs";
import * as FileSaver from "file-saver";
import Chart from "chart.js/auto";

const saveAs = FileSaver.saveAs || FileSaver.default || FileSaver;
import { mapToDashboard, buildDetailedBalance } from "./finModel.js";

// Paleta ORIGINAL del dashboard AUDIT-IA (tema "ejecutivo"), para que los
// gráficos e informes exportados usen los mismos colores que el HTML.
export const PALETTE = {
  positivo: "#A6C63F", negativo: "#C0392B", acumulado: "#1E5AA8",
  secundario: "#0D7377", neutro: "#2F3640", advertencia: "#D68910",
};
// Colores exactos del gráfico Ingresos/Costo/Utilidad del dashboard.
const DASH = { ingresos: "#0D7377", costo: "#C0392B", utilidad: "#C7A83C" };

// Construye las filas del Estado de Resultados desde el modelo del dashboard.
export function erRows(dash, labels) {
  const at = (k, l) => dash[k]?.[l] || 0;
  const line = (nombre, fn) => ({ nombre, vals: labels.map((l) => fn(l)) });
  return [
    line("Ingresos ordinarios", (l) => at("ingOrd", l)),
    line("Costo de ventas", (l) => at("costoVta", l)),
    line("Utilidad bruta", (l) => at("ingOrd", l) + at("costoVta", l)),
    line("Gastos admin, ventas y otros", (l) => at("gastAdm", l)),
    line("Gastos financieros", (l) => at("gastFin", l)),
    line("Utilidad operativa", (l) => at("ingOrd", l) + at("costoVta", l) + at("gastAdm", l) + at("gastFin", l)),
    line("Ingresos no ordinarios", (l) => at("ingNoOrd", l)),
    line("Utilidad antes de IR", (l) => at("ingOrd", l) + at("costoVta", l) + at("gastAdm", l) + at("gastFin", l) + at("ingNoOrd", l)),
    line("Impuesto a la renta", (l) => at("irCorr", l) + at("irDif", l)),
    line("Utilidad neta", (l) => at("ingOrd", l) + at("costoVta", l) + at("gastAdm", l) + at("gastFin", l) + at("ingNoOrd", l) + at("irCorr", l) + at("irDif", l)),
  ];
}

// Renderiza el gráfico con Chart.js en un canvas offscreen y devuelve el PNG.
// SOLO navegador. style: combo|barras|lineas|area|puntos.
export async function renderChartPng({ labels, ingresos, costo, utilidad, style = "combo" }) {
  const canvas = document.createElement("canvas");
  canvas.width = 600; canvas.height = 350;
  canvas.style.position = "fixed"; canvas.style.left = "-9999px";
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#FFFFFF"; ctx.fillRect(0, 0, 600, 350); // fondo blanco para Excel

  const mk = (label, data, color, forceType) => {
    const base = { label, data, borderColor: color, backgroundColor: color };
    if (style === "barras" || (style === "combo" && !forceType)) return { ...base, type: "bar", borderRadius: 4 };
    if (style === "area") return { ...base, type: "line", fill: true, backgroundColor: color + "33", tension: 0.35, pointRadius: 3 };
    if (style === "puntos") return { ...base, type: "line", showLine: false, pointRadius: 5 };
    return { ...base, type: "line", fill: false, tension: 0.35, pointRadius: 3 };
  };
  const datasets = [
    mk("Ingresos", ingresos, DASH.ingresos),
    mk("Costo de ventas", costo, DASH.costo),
    style === "combo"
      ? { label: "Utilidad neta", data: utilidad, type: "line", borderColor: DASH.utilidad, backgroundColor: DASH.utilidad, tension: 0.35, pointRadius: 4 }
      : mk("Utilidad neta", utilidad, DASH.utilidad, true),
  ];
  const chart = new Chart(ctx, {
    type: style === "barras" || style === "combo" ? "bar" : "line",
    data: { labels, datasets },
    options: { responsive: false, animation: false, plugins: { legend: { position: "bottom" } },
      scales: { y: { ticks: { callback: (v) => "$" + Number(v).toLocaleString() } } } },
  });
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const png = canvas.toDataURL("image/png");
  chart.destroy(); canvas.remove();
  return png;
}

// Construye el Workbook (lógica pura, testeable en Node). pngDataUrl opcional.
export function buildDashboardWorkbook({ D, periodos, header, detalle, nivel, chartStyle, pngDataUrl, fecha }) {
  const erLabels = periodos.map((p) => p.label);
  const esfLabels = periodos.map((p) => p.labelESF || p.label);
  const dash = mapToDashboard(D, erLabels);
  const balance = buildDetailedBalance(D, esfLabels);
  const er = erRows(dash, erLabels);
  const last = erLabels[erLabels.length - 1];
  const lastEsf = esfLabels[esfLabels.length - 1];

  const wb = new ExcelJS.Workbook();
  wb.creator = "AUDIT-IA · CFO Intelligence";
  const NAVY = "FF0A2342", GOLD = "FFC7A83C", WHITE = "FFFFFFFF", GREY = "FFF2F4F7";
  const money = "#,##0";

  // ── Hoja 1: Dashboard ──
  const ws = wb.addWorksheet("Dashboard");
  ws.columns = [{ width: 34 }, { width: 22 }, { width: 22 }, { width: 22 }];
  const t = ws.addRow([`AUDIT-IA · ${header?.empresa || "Empresa"}`]);
  t.font = { bold: true, size: 16, color: { argb: GOLD } };
  t.getCell(1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: NAVY } };
  ws.mergeCells("A1:D1");
  const sub = ws.addRow([`Dashboard Ejecutivo · ${header?.subtitulo || ""} · Generado ${fecha}`]);
  sub.getCell(1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: NAVY } };
  sub.font = { color: { argb: "FFD5D8DC" }, size: 10 };
  ws.mergeCells("A2:D2");
  ws.addRow([]);
  const pat = (dash.capital?.[lastEsf] || 0) + (dash.resLegal?.[lastEsf] || 0) + (dash.oriAcum?.[lastEsf] || 0) + (dash.utilAcum?.[lastEsf] || 0);
  const neta = er.find((r) => r.nombre === "Utilidad neta").vals[erLabels.length - 1];
  const ing = dash.ingOrd?.[last] || 0;
  const kpis = [
    ["Indicador clave", "Valor", "Período"],
    ["Ingresos ordinarios", ing, last],
    ["Utilidad neta", neta, last],
    ["Patrimonio", pat, lastEsf],
    ["Margen neto", ing ? neta / ing : 0, last],
  ];
  kpis.forEach((r, i) => {
    const row = ws.addRow(r);
    if (i === 0) row.font = { bold: true, color: { argb: WHITE } }, row.eachCell((c) => (c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: NAVY } }));
    else {
      row.getCell(2).numFmt = r[0] === "Margen neto" ? "0.0%" : money;
      row.getCell(2).font = { bold: true };
    }
  });

  // ── Hoja 2: Datos ──
  const wd = wb.addWorksheet("Datos");
  wd.columns = [{ width: 38 }, ...erLabels.map(() => ({ width: 18 }))];
  const hdr = (txt) => { const r = wd.addRow([txt]); r.font = { bold: true, color: { argb: GOLD } }; r.getCell(1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: NAVY } }; wd.mergeCells(r.number, 1, r.number, erLabels.length + 1); };
  const colHead = (labels) => { const r = wd.addRow(["Cuenta", ...labels]); r.font = { bold: true }; r.eachCell((c) => (c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: GREY } })); };
  hdr(`ESTADO DE RESULTADOS (${erLabels.join(" vs ")})`);
  colHead(erLabels);
  er.forEach((r) => { const row = wd.addRow([r.nombre, ...r.vals]); const tot = /Utilidad|Total/.test(r.nombre); if (tot) row.font = { bold: true }; for (let c = 2; c <= erLabels.length + 1; c++) row.getCell(c).numFmt = money; });
  wd.addRow([]);
  hdr(`BALANCE GENERAL (${esfLabels.join(" vs ")})`);
  colHead(esfLabels);
  balance.forEach((b) => {
    if (b.t === "sec") { const r = wd.addRow([b.label]); r.font = { bold: true }; return; }
    const row = wd.addRow([b.label, ...esfLabels.map((l) => b.vals[l] || 0)]);
    if (b.t === "tot") row.font = { bold: true };
    for (let c = 2; c <= esfLabels.length + 1; c++) row.getCell(c).numFmt = money;
  });

  // ── Hoja 3: Config ──
  const wc = wb.addWorksheet("Config");
  wc.columns = [{ width: 26 }, { width: 60 }];
  [["Atributo", "Valor"], ["Empresa", header?.empresa || ""], ["Tipo de gráfico", chartStyle],
   ["Nivel de detalle", nivel], ["Períodos ER", erLabels.join(" · ")], ["Períodos Balance", esfLabels.join(" · ")],
   ["Unidad", "USD"], ["Eje X", "Período"], ["Eje Y", "Monto (USD)"],
   ["Color positivo", PALETTE.positivo], ["Color negativo", PALETTE.negativo], ["Color acumulado", PALETTE.acumulado],
  ].forEach((r, i) => { const row = wc.addRow(r); if (i === 0) { row.font = { bold: true, color: { argb: WHITE } }; row.eachCell((c) => (c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: NAVY } })); } });

  // ── Hoja 4: Imagen ──
  const wi = wb.addWorksheet("Imagen");
  wi.getCell("A1").value = "Imagen del gráfico (respaldo visual del dashboard)";
  wi.getCell("A1").font = { bold: true };
  if (pngDataUrl) {
    const imgId = wb.addImage({ base64: pngDataUrl, extension: "png" });
    wi.addImage(imgId, { tl: { col: 1, row: 2 }, ext: { width: 600, height: 350 } });
  } else {
    wi.getCell("A3").value = "(No se pudo capturar el gráfico)";
  }

  // ── Hoja 5: Instrucciones ──
  const wins = wb.addWorksheet("Instrucciones");
  wins.columns = [{ width: 100 }];
  [
    "CÓMO RECREAR LOS GRÁFICOS EN EXCEL / POWER BI",
    "",
    "1. La hoja 'Datos' contiene todas las cifras del dashboard (Estado de Resultados y Balance).",
    "2. La hoja 'Imagen' tiene el gráfico tal como se ve en el dashboard (respaldo).",
    "3. Para recrearlo nativo en Excel:",
    "   • Selecciona el rango de la hoja 'Datos' (Cuenta + columnas de período).",
    "   • Insertar > Gráfico recomendado > elige el tipo indicado en la hoja 'Config'.",
    "   • Líneas = tendencias · Barras = comparación · Área = volumen · Combinado = barras+línea.",
    "4. Para Waterfall/Radar/Sankey (no nativos): usa Power BI o el snippet Chart.js del asistente Skill 051.",
    "5. Paleta AUDIT-IA — positivo #1D9E75 · negativo #E24B4A · acumulado #378ADD.",
    "",
    "Generado por AUDIT-IA · CFO Intelligence · Skill 051.",
  ].forEach((l, i) => { const r = wins.addRow([l]); if (i === 0) r.font = { bold: true, size: 13 }; });

  return wb;
}

// Orquestador: renderiza el PNG y descarga el .xlsx.
export async function exportDashboardExcel({ D, periodos, header, detalle, nivel, chartStyle }) {
  const erLabels = periodos.map((p) => p.label);
  const dash = mapToDashboard(D, erLabels);
  const at = (k, l) => dash[k]?.[l] || 0;
  let pngDataUrl = null;
  try {
    pngDataUrl = await renderChartPng({
      labels: erLabels,
      ingresos: erLabels.map((l) => at("ingOrd", l)),
      costo: erLabels.map((l) => Math.abs(at("costoVta", l))),
      utilidad: erLabels.map((l) => at("ingOrd", l) + at("costoVta", l) + at("gastAdm", l) + at("gastFin", l) + at("ingNoOrd", l) + at("irCorr", l) + at("irDif", l)),
      style: chartStyle || "combo",
    });
  } catch (e) { console.warn("No se pudo renderizar el gráfico:", e); }

  const d = new Date();
  const fecha = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const wb = buildDashboardWorkbook({ D, periodos, header, detalle, nivel, chartStyle, pngDataUrl, fecha });
  const buf = await wb.xlsx.writeBuffer();
  const safe = String(header?.empresa || "cliente").replace(/[\s/\\]+/g, "_") || "cliente";
  saveAs(new Blob([buf], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
    `AuditBrain_Dashboard_${safe}_${fecha}.xlsx`);
}
