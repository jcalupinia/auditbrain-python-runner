// Export del Dashboard Ejecutivo a PDF, Word (.docx) y PowerPoint (.pptx).
// Reutiliza el PNG del gráfico (Chart.js offscreen) y los datos del dashboard.
// Builders puros (sin navegador) para poder testear en Node; los orquestadores
// renderizan el PNG y descargan el archivo.
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, WidthType, AlignmentType } from "docx";
import pptxgen from "pptxgenjs";
import * as FileSaver from "file-saver";
import { mapToDashboard, buildDetailedBalance } from "./finModel.js";
import { renderChartPng, erRows, PALETTE } from "./excelExport.js";

const saveAs = FileSaver.saveAs || FileSaver.default || FileSaver;
const NAVY = "0A2342", GOLD = "C7A83C";
const nf = new Intl.NumberFormat("es-EC", { maximumFractionDigits: 0 });
const money = (v) => (v < 0 ? "(" : "") + "$" + nf.format(Math.abs(Math.round(v || 0))) + (v < 0 ? ")" : "");

function dataUrlToU8(dataUrl) {
  const b64 = (dataUrl || "").split(",")[1] || "";
  const bin = atob(b64);
  const u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  return u8;
}

// Modelo común para los tres formatos.
export function buildReportModel({ D, periodos, header, nivel }) {
  const erLabels = periodos.map((p) => p.label);
  const esfLabels = periodos.map((p) => p.labelESF || p.label);
  const dash = mapToDashboard(D, erLabels);
  const er = erRows(dash, erLabels);
  const balanceFull = buildDetailedBalance(D, esfLabels);
  // En "resumido" mostramos solo secciones y totales; en "detallado" todo.
  const balance = nivel === "detallado" ? balanceFull : balanceFull.filter((b) => b.t !== "in");
  const lastE = erLabels[erLabels.length - 1];
  const lastB = esfLabels[esfLabels.length - 1];
  const neta = er.find((r) => r.nombre === "Utilidad neta").vals[erLabels.length - 1];
  const ing = dash.ingOrd?.[lastE] || 0;
  const pat = (dash.capital?.[lastB] || 0) + (dash.resLegal?.[lastB] || 0) + (dash.oriAcum?.[lastB] || 0) + (dash.utilAcum?.[lastB] || 0);
  const kpis = [
    ["Ingresos ordinarios", money(ing), lastE],
    ["Utilidad neta", money(neta), lastE],
    ["Patrimonio", money(pat), lastB],
    ["Margen neto", (ing ? (neta / ing) * 100 : 0).toFixed(1) + "%", lastE],
  ];
  return { empresa: header?.empresa || "Empresa", subtitulo: header?.subtitulo || "", pie: header?.pie || "",
    erLabels, esfLabels, er, balance, kpis };
}

const fechaHoy = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const safeName = (s) => String(s || "cliente").replace(/[\s/\\]+/g, "_") || "cliente";

/* ===================== PDF ===================== */
export function buildPdf(model, pngDataUrl) {
  const doc = new jsPDF({ orientation: "p", unit: "pt", format: "a4" });
  const W = doc.internal.pageSize.getWidth();
  doc.setFillColor("#" + NAVY); doc.rect(0, 0, W, 64, "F");
  doc.setTextColor("#" + GOLD); doc.setFontSize(18); doc.setFont(undefined, "bold");
  doc.text("AuditBrain · " + model.empresa, 40, 30);
  doc.setTextColor("#D5D8DC"); doc.setFontSize(10); doc.setFont(undefined, "normal");
  doc.text("Dashboard Ejecutivo · " + model.subtitulo, 40, 48);

  let y = 86;
  doc.setTextColor("#0A2342"); doc.setFontSize(12); doc.setFont(undefined, "bold");
  doc.text("Indicadores clave", 40, y); y += 8;
  autoTable(doc, { startY: y, head: [["Indicador", "Valor", "Período"]], body: model.kpis,
    theme: "grid", headStyles: { fillColor: [10, 35, 66] }, styles: { fontSize: 10 }, margin: { left: 40, right: 40 } });
  y = doc.lastAutoTable.finalY + 16;

  if (pngDataUrl) {
    try { doc.addImage(pngDataUrl, "PNG", 40, y, W - 80, ((W - 80) * 350) / 600); y += ((W - 80) * 350) / 600 + 16; } catch (e) { /* sin imagen */ }
  }

  doc.setFont(undefined, "bold"); doc.setFontSize(12); doc.text("Estado de Resultados", 40, y); y += 6;
  autoTable(doc, { startY: y, head: [["Cuenta", ...model.erLabels]],
    body: model.er.map((r) => [r.nombre, ...r.vals.map(money)]),
    theme: "striped", headStyles: { fillColor: [10, 35, 66] }, styles: { fontSize: 9, halign: "right" },
    columnStyles: { 0: { halign: "left" } }, margin: { left: 40, right: 40 } });

  doc.addPage();
  doc.setFont(undefined, "bold"); doc.setFontSize(12); doc.setTextColor("#0A2342"); doc.text("Balance General", 40, 50);
  autoTable(doc, { startY: 60, head: [["Cuenta", ...model.esfLabels]],
    body: model.balance.map((b) => [b.label, ...(b.t === "sec" ? model.esfLabels.map(() => "") : model.esfLabels.map((l) => money(b.vals[l] || 0)))]),
    theme: "striped", headStyles: { fillColor: [10, 35, 66] }, styles: { fontSize: 9, halign: "right" },
    columnStyles: { 0: { halign: "left" } }, margin: { left: 40, right: 40 } });
  return doc;
}

/* ===================== WORD ===================== */
function wcell(text, opts = {}) {
  return new TableCell({ width: { size: opts.w || 2000, type: WidthType.DXA },
    shading: opts.head ? { fill: NAVY } : undefined,
    children: [new Paragraph({ alignment: opts.right ? AlignmentType.RIGHT : AlignmentType.LEFT,
      children: [new TextRun({ text: String(text), bold: !!opts.bold || !!opts.head, color: opts.head ? "FFFFFF" : "000000", size: 18 })] })] });
}
function wtable(head, rows) {
  return new Table({ width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [new TableRow({ tableHeader: true, children: head.map((h, i) => wcell(h, { head: true, right: i > 0 })) }),
      ...rows.map((r) => new TableRow({ children: r.cells.map((c, i) => wcell(c, { right: i > 0, bold: r.bold })) }))] });
}
export function buildWord(model, pngDataUrl) {
  const children = [
    new Paragraph({ children: [new TextRun({ text: "AuditBrain · " + model.empresa, bold: true, size: 32, color: GOLD })] }),
    new Paragraph({ children: [new TextRun({ text: "Dashboard Ejecutivo · " + model.subtitulo, size: 18, color: "666666" })] }),
    new Paragraph({ text: "" }),
    new Paragraph({ children: [new TextRun({ text: "Indicadores clave", bold: true, size: 24 })] }),
    wtable(["Indicador", "Valor", "Período"], model.kpis.map((k) => ({ cells: k }))),
    new Paragraph({ text: "" }),
  ];
  if (pngDataUrl) {
    children.push(new Paragraph({ children: [new ImageRun({ type: "png", data: dataUrlToU8(pngDataUrl), transformation: { width: 520, height: 303 } })] }));
    children.push(new Paragraph({ text: "" }));
  }
  children.push(new Paragraph({ children: [new TextRun({ text: "Estado de Resultados", bold: true, size: 24 })] }));
  children.push(wtable(["Cuenta", ...model.erLabels], model.er.map((r) => ({ cells: [r.nombre, ...r.vals.map(money)], bold: /Utilidad|Total/.test(r.nombre) }))));
  children.push(new Paragraph({ text: "" }));
  children.push(new Paragraph({ children: [new TextRun({ text: "Balance General", bold: true, size: 24 })] }));
  children.push(wtable(["Cuenta", ...model.esfLabels], model.balance.map((b) => ({ cells: [b.label, ...(b.t === "sec" ? model.esfLabels.map(() => "") : model.esfLabels.map((l) => money(b.vals[l] || 0)))], bold: b.t !== "in" }))));
  return new Document({ sections: [{ children }] });
}

/* ===================== PPTX ===================== */
export function buildPptx(model, pngDataUrl) {
  const p = new pptxgen();
  p.defineLayout({ name: "WIDE", width: 13.333, height: 7.5 });
  p.layout = "WIDE";
  const NV = "0A2342", GD = "C7A83C";
  // Slide 1 — portada + KPIs
  let s = p.addSlide(); s.background = { color: NV };
  s.addText("AuditBrain · " + model.empresa, { x: 0.5, y: 0.5, w: 12.3, fontSize: 28, bold: true, color: GD });
  s.addText("Dashboard Ejecutivo · " + model.subtitulo, { x: 0.5, y: 1.2, w: 12.3, fontSize: 13, color: "D5D8DC" });
  s.addTable([[{ text: "Indicador", options: { bold: true, color: "FFFFFF", fill: { color: "1E5AA8" } } }, { text: "Valor", options: { bold: true, color: "FFFFFF", fill: { color: "1E5AA8" } } }, { text: "Período", options: { bold: true, color: "FFFFFF", fill: { color: "1E5AA8" } } }],
    ...model.kpis.map((k) => k.map((c) => ({ text: String(c), options: { color: "FFFFFF" } })))],
    { x: 0.5, y: 2.2, w: 8, fontSize: 14, border: { type: "solid", color: "33415A" } });
  if (pngDataUrl) s.addImage({ data: pngDataUrl, x: 8.7, y: 2.2, w: 4.1, h: 2.4 });
  // Slide 2 — Estado de Resultados
  let s2 = p.addSlide();
  s2.addText("Estado de Resultados", { x: 0.5, y: 0.3, fontSize: 20, bold: true, color: NV });
  s2.addTable([[ "Cuenta", ...model.erLabels].map((h) => ({ text: h, options: { bold: true, color: "FFFFFF", fill: { color: NV } } })),
    ...model.er.map((r) => [{ text: r.nombre, options: { bold: /Utilidad|Total/.test(r.nombre) } }, ...r.vals.map((v) => ({ text: money(v), options: { align: "right" } }))])],
    { x: 0.5, y: 1.0, w: 12.3, fontSize: 11, border: { type: "solid", color: "DDDDDD" } });
  // Slide 3 — Balance
  let s3 = p.addSlide();
  s3.addText("Balance General", { x: 0.5, y: 0.3, fontSize: 20, bold: true, color: NV });
  s3.addTable([["Cuenta", ...model.esfLabels].map((h) => ({ text: h, options: { bold: true, color: "FFFFFF", fill: { color: NV } } })),
    ...model.balance.map((b) => [{ text: b.label, options: { bold: b.t !== "in" } }, ...(b.t === "sec" ? model.esfLabels.map(() => ({ text: "" })) : model.esfLabels.map((l) => ({ text: money(b.vals[l] || 0), options: { align: "right" } })))])],
    { x: 0.5, y: 1.0, w: 12.3, fontSize: 10, border: { type: "solid", color: "DDDDDD" } });
  return p;
}

/* ===================== Orquestadores (navegador) ===================== */
async function chartPngFor({ D, periodos, chartStyle }) {
  const erLabels = periodos.map((p) => p.label);
  const dash = mapToDashboard(D, erLabels);
  const at = (k, l) => dash[k]?.[l] || 0;
  try {
    return await renderChartPng({ labels: erLabels,
      ingresos: erLabels.map((l) => at("ingOrd", l)),
      costo: erLabels.map((l) => Math.abs(at("costoVta", l))),
      utilidad: erLabels.map((l) => at("ingOrd", l) + at("costoVta", l) + at("gastAdm", l) + at("gastFin", l) + at("ingNoOrd", l) + at("irCorr", l) + at("irDif", l)),
      style: chartStyle || "combo" });
  } catch (e) { console.warn("chart png:", e); return null; }
}

export async function exportDashboardPDF(args) {
  const model = buildReportModel(args);
  const png = await chartPngFor(args);
  const doc = buildPdf(model, png);
  doc.save(`AuditBrain_Dashboard_${safeName(model.empresa)}_${fechaHoy()}.pdf`);
}
export async function exportDashboardWord(args) {
  const model = buildReportModel(args);
  const png = await chartPngFor(args);
  const blob = await Packer.toBlob(buildWord(model, png));
  saveAs(blob, `AuditBrain_Dashboard_${safeName(model.empresa)}_${fechaHoy()}.docx`);
}
export async function exportDashboardPPTX(args) {
  const model = buildReportModel(args);
  const png = await chartPngFor(args);
  await buildPptx(model, png).writeFile({ fileName: `AuditBrain_Dashboard_${safeName(model.empresa)}_${fechaHoy()}.pptx` });
}
