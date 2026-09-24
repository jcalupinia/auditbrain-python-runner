// Papel de trabajo de las pruebas DECLARATIVAS (catálogo y fichas sin
// procesador) en todos los formatos obligatorios: Excel con fórmulas, Word,
// PowerPoint y un HTML sin conexión que lleva dentro los otros tres.
//
// Una sola fuente: las cédulas de `workbookSheets(t)` del exportador del sitio
// (la misma que arma el Excel con fórmulas). Word y PowerPoint presentan el
// valor calculado de cada celda; el Excel conserva la fórmula. El exportador del
// sitio (./sitio/) es una copia que no se edita aquí: este módulo lo consume.
//
// Builders puros (sin DOM): se prueban en Node con Vitest y corren igual en el
// navegador, que es donde se arma el papel de una prueba declarativa (en Render
// no corre Node).
import {
  AlignmentType, BorderStyle, Document, Footer, Header, ImageRun, PageNumber, PageOrientation,
  Packer, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun, WidthType,
} from "docx";
import pptxgen from "pptxgenjs";

import { SHEETS, buildHtml, buildWorkbook, sheetLabels, sheetNames, workbookSheets } from "./sitio/tools/exports.mjs";
import { auditLogoBase64 } from "./sitio/tools/brand.mjs";

const NAVY = "0A2342", DEEP = "071B2F", GOLD = "C7A83C", ZEBRA = "F4F6F9", LINEA = "D9DEE7", TEXTO = "1A1A1A", MUTED = "5B6472";
export const NOTAS = "CÓMO SE PREPARA Y CALCULA";
export const MIME = {
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  html: "text/html;charset=utf-8",
};

// --- Valores de celda (es-EC) --------------------------------------------------
const fmtNum = (x) => {
  const s = String(x).trim();
  if (!/^-?\d+(\.\d+)?$/.test(s)) return s;
  const n = Number(s);
  const dec = s.includes(".") ? Math.max(2, Math.min(6, s.split(".")[1].replace(/0+$/, "").length)) : 0;
  return new Intl.NumberFormat("es-EC", { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(n);
};
const fmtFecha = (serial) => {
  const n = Number(serial);
  if (!Number.isFinite(n) || n <= 0) return "";
  const d = new Date(Date.UTC(1899, 11, 30) + Math.round(n) * 86400000);
  return `${String(d.getUTCDate()).padStart(2, "0")}/${String(d.getUTCMonth() + 1).padStart(2, "0")}/${d.getUTCFullYear()}`;
};

/** Texto que se ve de una celda del exportador: texto, {n}, {n,date} o {f,v,type}. */
export function texto(c) {
  if (c === null || c === undefined) return "";
  if (typeof c === "string") return c;
  if (typeof c === "number") return fmtNum(c);
  if (typeof c === "object") {
    if ("f" in c) {
      const v = c.v;
      if (v === "" || v === null || v === undefined) return "";
      if (c.type === "date") return fmtFecha(v);
      if (c.type === "text") return String(v);
      return fmtNum(v);
    }
    if ("n" in c) return c.date ? fmtFecha(c.n) : fmtNum(c.n);
  }
  return String(c);
}
const esNumero = (c) => c && typeof c === "object" && (("n" in c && !c.date) || ("f" in c && c.type !== "text" && c.type !== "date" && /^-?\d+(\.\d+)?$/.test(String(c.v ?? "").trim())));

// --- Modelo común --------------------------------------------------------------
/**
 * Cédulas listas para presentar: nombre, etiqueta, títulos, filas (con su texto
 * visible y si la celda es numérica) y la nota «Cómo se prepara y calcula».
 */
export function modeloPapel(t) {
  const d = t.definition;
  const hojas = workbookSheets(t);
  const nombres = sheetNames(d), etiquetas = sheetLabels(d);
  const cedulas = hojas.map((rows, i) => {
    const iNotas = rows.findIndex((r) => r?.[0] === NOTAS);
    const cuerpo = iNotas >= 0 ? rows.slice(0, iNotas) : rows;
    const nota = iNotas >= 0 ? rows.slice(iNotas + 1).map((r) => texto(r?.[0])).filter(Boolean).join("\n") : "";
    const portada = i === 0;
    const desde = portada ? 0 : 4; // fila 4 = encabezado; los datos empiezan en la 5
    const filas = [];
    let separar = false;
    for (const r of cuerpo.slice(desde)) {
      const celdas = (r || []).map((c) => ({ t: texto(c), num: esNumero(c) }));
      if (!celdas.some((c) => c.t !== "")) { separar = true; continue; }
      filas.push({ celdas, sub: separar && celdas.every((c) => !c.num) });
      separar = false;
    }
    return {
      nombre: nombres[i], etiqueta: etiquetas[i], numero: String(i + 1).padStart(2, "0"),
      titulo: portada ? d.name : texto(rows[0]?.[0]), meta: portada ? "" : texto(rows[1]?.[0]), estado: portada ? "" : texto(rows[2]?.[0]),
      encabezado: portada ? [] : (rows[3] || []).map(texto), filas, nota, portada,
    };
  });
  const run = t.run || { totals: {}, exceptions: [], rows: [] };
  const principal = d.rules?.find((r) => r.key === d.primary);
  const e = t.engagement || {};
  const kpis = [
    { etq: "Registros procesados", val: fmtNum(String((t.rows || []).length)) },
    { etq: principal?.label || "Resultado principal", val: fmtNum(run.totals?.[d.primary] ?? "0") },
    { etq: "Conciliación con el mayor", val: t.reconciliation?.within ? "CONFORME" : "REVISAR", det: `Diferencia ${fmtNum(t.reconciliation?.difference ?? "0")}` },
    { etq: "Excepciones", val: fmtNum(String((run.exceptions || []).length)) },
  ];
  const estado = t.demo ? "DEMOSTRACIÓN · DATOS FICTICIOS" : t.draft ? "BORRADOR · PENDIENTE DE REVISIÓN" : t.state === "APROBADO" ? `APROBADO${t.approvedBy ? " · " + t.approvedBy : ""}` : "PAPEL EN PROCESO · PENDIENTE DE REVISIÓN";
  return {
    nombre: d.name, area: d.area || "", firma: e.firm || "AuditConsulting Auditores Cía. Ltda.", cliente: e.client || "Cliente pendiente",
    corte: e.cutoff || "Pendiente", anio: e.year || "", marco: e.framework || "", preparo: e.preparer || "Pendiente", reviso: e.reviewer || "Pendiente",
    version: t.version, estado, kpis, cedulas, analisis: t.analysis || "", conclusion: t.conclusion || "",
  };
}

export const nombreBase = (t) => `${String(t.definition?.name || "prueba").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^\w-]+/g, "_").slice(0, 60)}_v${t.version}`;

// --- Word ------------------------------------------------------------------------
const b64aU8 = (b64) => Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
const borde = { style: BorderStyle.SINGLE, size: 4, color: LINEA };
const bordes = { top: borde, bottom: borde, left: borde, right: borde, insideHorizontal: borde, insideVertical: borde };
const run = (text, o = {}) => new TextRun({ text, font: "Calibri", size: o.size || 16, bold: o.bold, italics: o.italics, color: o.color || TEXTO });
const celdaW = (txt, o = {}) => new TableCell({
  children: [new Paragraph({ alignment: o.num ? AlignmentType.RIGHT : AlignmentType.LEFT, children: [run(txt, { bold: o.head || o.sub, color: o.head ? "FFFFFF" : TEXTO, size: o.size })] })],
  shading: o.head ? { type: ShadingType.CLEAR, color: "auto", fill: NAVY } : o.zebra ? { type: ShadingType.CLEAR, color: "auto", fill: ZEBRA } : o.sub ? { type: ShadingType.CLEAR, color: "auto", fill: "E9EDF3" } : undefined,
  margins: { top: 40, bottom: 40, left: 70, right: 70 },
});
function tablaW(encabezado, filas, size = 15) {
  const ancho = Math.max(1, encabezado.length, ...filas.map((f) => f.celdas.length));
  const pad = (arr) => [...arr, ...Array(Math.max(0, ancho - arr.length)).fill({ t: "" })].slice(0, ancho);
  const rows = [];
  if (encabezado.length) rows.push(new TableRow({ tableHeader: true, children: pad(encabezado.map((x) => ({ t: x }))).map((c) => celdaW(c.t, { head: true, size })) }));
  filas.forEach((f, k) => rows.push(new TableRow({ cantSplit: true, children: pad(f.celdas).map((c) => celdaW(c.t, { num: c.num, sub: f.sub, zebra: !f.sub && k % 2 === 1, size })) })));
  return new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, borders: bordes, rows });
}
const titulo = (txt, size = 26, color = NAVY) => new Paragraph({ spacing: { before: 120, after: 80 }, children: [run(txt, { bold: true, size, color })] });
const parrafo = (txt, o = {}) => new Paragraph({ spacing: { after: 80 }, children: [run(txt, { size: o.size || 18, italics: o.italics, color: o.color, bold: o.bold })] });

/** Documento Word del papel (A4 horizontal): portada con indicadores y una sección por cédula. */
export function documentoWord(t) {
  const m = modeloPapel(t);
  const portada = [
    new Paragraph({ children: [new ImageRun({ type: "png", data: b64aU8(auditLogoBase64), transformation: { width: 180, height: 61 } })] }),
    titulo(m.firma.toUpperCase(), 20, GOLD),
    titulo(m.nombre, 40),
    parrafo(`${m.cliente} · ${m.area} · Corte ${m.corte}${m.marco ? " · " + m.marco : ""}`, { size: 20, color: MUTED }),
    parrafo(`${m.estado} · Versión ${m.version} · Preparó: ${m.preparo} · Revisó: ${m.reviso}`, { size: 18, bold: true, color: NAVY }),
    titulo("Indicadores clave", 24),
    tablaW(["Indicador", "Resultado", "Detalle"], m.kpis.map((k) => ({ celdas: [{ t: k.etq }, { t: k.val, num: true }, { t: k.det || "" }] })), 18),
    titulo("Índice de cédulas", 24),
    ...m.cedulas.map((c) => parrafo(`${c.numero} · ${c.etiqueta}`, { size: 18 })),
    parrafo("El Excel del papel conserva las fórmulas de cada importe; este documento presenta sus valores calculados.", { italics: true, color: MUTED }),
    ...(m.cedulas[0]?.nota ? [titulo("Cómo se prepara y calcula", 20, GOLD), parrafo(m.cedulas[0].nota, { size: 16, color: MUTED })] : []),
  ];
  const secciones = m.cedulas.filter((c) => !c.portada).flatMap((c) => [
    new Paragraph({ pageBreakBefore: true, children: [] }),
    titulo(`${c.numero} · ${c.etiqueta}`, 30),
    parrafo(c.meta, { size: 16, color: MUTED }),
    parrafo(c.estado, { size: 16, bold: true, color: NAVY }),
    c.filas.length ? tablaW(c.encabezado, c.filas) : parrafo("Sin registros en esta cédula.", { italics: true, color: MUTED }),
    ...(c.nota ? [titulo("Cómo se prepara y calcula", 20, GOLD), parrafo(c.nota, { size: 16, color: MUTED })] : []),
  ]);
  return new Document({
    creator: m.firma, title: `${m.nombre} · ${m.cliente}`, description: "Papel de trabajo · AUDIT-IA",
    sections: [{
      properties: { page: { size: { orientation: PageOrientation.LANDSCAPE }, margin: { top: 720, bottom: 720, left: 720, right: 720 } } },
      headers: { default: new Header({ children: [parrafo(`${m.nombre} · ${m.cliente} · v${m.version}`, { size: 14, color: MUTED })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
        run(`${m.firma} · Confidencial · AUDIT-IA · Página `, { size: 14, color: MUTED }),
        new TextRun({ children: [PageNumber.CURRENT], font: "Calibri", size: 14, color: MUTED }),
      ] })] }) },
      children: [...portada, ...secciones],
    }],
  });
}

// --- PowerPoint ------------------------------------------------------------------
// Cédulas que se presentan (las de detalle fila a fila quedan en el Excel).
// Programa, fuentes, controles y conciliación, excepciones, sumaria y conclusión.
const EN_DIAPOSITIVA = [1, 3, 7, 8, 9, 10].map((i) => SHEETS[i]);
const MAX_COLS = 7;

/** Presentación ejecutiva (16:9): portada, indicadores, cédulas clave y detalle disponible. */
export function presentacion(t) {
  const m = modeloPapel(t);
  const p = new pptxgen();
  p.layout = "LAYOUT_WIDE";
  p.title = `${m.nombre} · ${m.cliente}`;
  p.company = m.firma;
  const pie = (s) => s.addText(`${m.firma} · Confidencial · AUDIT-IA`, { x: 0.5, y: 7.05, w: 9, h: 0.3, fontSize: 9, color: "8A94A6", fontFace: "Calibri" });

  let s = p.addSlide();
  s.background = { color: DEEP };
  s.addShape(p.ShapeType.rect, { x: 0, y: 0, w: 0.18, h: 7.5, fill: { color: GOLD } });
  s.addImage({ data: "image/png;base64," + auditLogoBase64, x: 0.6, y: 0.5, w: 2.4, h: 0.81 });
  s.addText(m.firma.toUpperCase(), { x: 0.6, y: 1.6, w: 12, h: 0.4, fontSize: 13, color: GOLD, bold: true, fontFace: "Calibri", charSpacing: 2 });
  s.addText(m.nombre, { x: 0.6, y: 2.1, w: 12, h: 1.2, fontSize: 36, color: "FFFFFF", bold: true, fontFace: "Calibri" });
  s.addText(`${m.cliente} · ${m.area} · Corte ${m.corte}`, { x: 0.6, y: 3.4, w: 12, h: 0.5, fontSize: 16, color: "D5D8DC", fontFace: "Calibri" });
  s.addText(`${m.estado} · Versión ${m.version}`, { x: 0.6, y: 4.1, w: 12, h: 0.4, fontSize: 13, color: GOLD, bold: true, fontFace: "Calibri" });
  s.addText(`Preparó: ${m.preparo}   ·   Revisó: ${m.reviso}`, { x: 0.6, y: 6.4, w: 12, h: 0.4, fontSize: 11, color: "A9B4C4", fontFace: "Calibri" });

  s = p.addSlide();
  s.background = { color: "FFFFFF" };
  s.addText("Resumen de la prueba", { x: 0.5, y: 0.3, w: 12, h: 0.6, fontSize: 24, bold: true, color: NAVY, fontFace: "Calibri" });
  m.kpis.forEach((k, i) => {
    const x = 0.5 + i * 3.1;
    s.addShape(p.ShapeType.roundRect, { x, y: 1.2, w: 2.9, h: 1.9, fill: { color: NAVY }, line: { color: GOLD, width: 1 }, rectRadius: 0.12 });
    s.addText(k.etq.toUpperCase(), { x: x + 0.15, y: 1.3, w: 2.6, h: 0.5, fontSize: 10, color: "C9D1DD", bold: true, fontFace: "Calibri", fit: "shrink" });
    s.addText(k.val, { x: x + 0.15, y: 1.85, w: 2.6, h: 0.7, fontSize: 24, color: k.val === "REVISAR" ? "F2A33A" : GOLD, bold: true, fontFace: "Calibri", fit: "shrink" });
    if (k.det) s.addText(k.det, { x: x + 0.15, y: 2.55, w: 2.6, h: 0.4, fontSize: 10, color: "C9D1DD", fontFace: "Calibri" });
  });
  s.addText("Cédulas del papel", { x: 0.5, y: 3.5, w: 12, h: 0.4, fontSize: 14, bold: true, color: NAVY, fontFace: "Calibri" });
  const idx = m.cedulas.map((c) => `${c.numero} · ${c.etiqueta}`);
  const mitad = Math.ceil(idx.length / 2);
  s.addText(idx.slice(0, mitad).join("\n"), { x: 0.5, y: 3.95, w: 6, h: 2.9, fontSize: 12, color: TEXTO, fontFace: "Calibri", valign: "top" });
  s.addText(idx.slice(mitad).join("\n"), { x: 6.7, y: 3.95, w: 6, h: 2.9, fontSize: 12, color: TEXTO, fontFace: "Calibri", valign: "top" });
  pie(s);

  for (const c of m.cedulas.filter((x) => EN_DIAPOSITIVA.includes(x.nombre))) {
    const ancho = Math.min(MAX_COLS, Math.max(1, c.encabezado.length, ...c.filas.map((f) => f.celdas.length)));
    const cabeza = [...c.encabezado, ...Array(ancho).fill("")].slice(0, ancho).map((h) => ({ text: h, options: { bold: true, color: "FFFFFF", fill: { color: NAVY } } }));
    const filas = c.filas.map((f, k) => [...f.celdas, ...Array(ancho).fill({ t: "" })].slice(0, ancho).map((x) => ({
      text: x.t.length > 160 ? x.t.slice(0, 157) + "…" : x.t,
      options: { align: x.num ? "right" : "left", bold: f.sub, fill: { color: f.sub ? "E9EDF3" : k % 2 ? ZEBRA : "FFFFFF" } },
    })));
    s = p.addSlide();
    s.addText(`${c.numero} · ${c.etiqueta}`, { x: 0.5, y: 0.3, w: 12.3, h: 0.6, fontSize: 22, bold: true, color: NAVY, fontFace: "Calibri" });
    s.addText(c.estado, { x: 0.5, y: 0.85, w: 12.3, h: 0.3, fontSize: 10, color: MUTED, fontFace: "Calibri" });
    if (filas.length) {
      s.addTable([cabeza, ...filas], {
        x: 0.5, y: 1.3, w: 12.3, fontSize: 10, fontFace: "Calibri", color: TEXTO, border: { type: "solid", pt: 0.5, color: LINEA },
        autoPage: true, autoPageRepeatHeader: true, autoPageLineWeight: 0.5, autoPageCharWeight: 0.1, newSlideStartY: 0.6, margin: 0.05,
      });
    } else {
      s.addText("Sin registros en esta cédula.", { x: 0.5, y: 1.4, w: 12.3, h: 0.4, fontSize: 12, italic: true, color: MUTED, fontFace: "Calibri" });
    }
    pie(s);
  }

  const detalle = m.cedulas.filter((c) => !c.portada && !EN_DIAPOSITIVA.includes(c.nombre));
  s = p.addSlide();
  s.addText("Detalle completo en el Excel con fórmulas", { x: 0.5, y: 0.3, w: 12.3, h: 0.6, fontSize: 22, bold: true, color: NAVY, fontFace: "Calibri" });
  s.addText("Cada importe del Excel es una fórmula que remite a su origen; si cambia un parámetro o un saldo, el libro recalcula.", { x: 0.5, y: 0.95, w: 12.3, h: 0.4, fontSize: 12, color: MUTED, fontFace: "Calibri" });
  s.addTable([["Cédula", "Contenido", "Filas"].map((h) => ({ text: h, options: { bold: true, color: "FFFFFF", fill: { color: NAVY } } })),
    ...detalle.map((c) => [{ text: `${c.numero} · ${c.nombre}` }, { text: c.etiqueta }, { text: fmtNum(String(c.filas.length)), options: { align: "right" } }])],
  { x: 0.5, y: 1.5, w: 12.3, colW: [3.5, 7, 1.8], fontSize: 12, fontFace: "Calibri", color: TEXTO, border: { type: "solid", pt: 0.5, color: LINEA } });
  pie(s);
  return p;
}

// --- Bytes y HTML con adjuntos -------------------------------------------------------
export async function bytesWord(t) {
  const blob = await Packer.toBlob(documentoWord(t));
  return new Uint8Array(await blob.arrayBuffer());
}
export async function bytesPowerPoint(t) {
  const out = await presentacion(t).write({ outputType: "uint8array" });
  return out instanceof Uint8Array ? out : new Uint8Array(out);
}
const aBase64 = (u8) => {
  let s = "";
  for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
  return btoa(s);
};
const escAttr = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const IMPRIMIR = '<button class="action secondary" id="print">Imprimir informe</button>';

/**
 * El HTML del sitio con los demás formatos DENTRO (enlaces data: que descargan
 * sin conexión) y «Guardar como PDF» (imprime con el formato del sitio).
 */
export function htmlConAdjuntos(t, adjuntos) {
  const base = nombreBase(t);
  const enlaces = adjuntos.map(([ext, etiqueta, bytes]) =>
    `<a class="action secondary" style="text-decoration:none" download="${escAttr(`${base}.${ext}`)}" href="data:${MIME[ext].split(";")[0]};base64,${aBase64(bytes)}">⬇ ${escAttr(etiqueta)}</a>`).join("");
  let html = buildHtml(t);
  if (html.includes(IMPRIMIR)) {
    html = html.replace(IMPRIMIR, `<button class="action secondary" id="print" title="Elija «Guardar como PDF» como impresora">Guardar como PDF</button>${enlaces}`);
  } else {
    html = html.replace("</main>", `<section class="panel"><div class="panel-title"><h2>Descargas del papel</h2></div><div class="body"><div class="actions">${enlaces}</div></div></section></main>`);
  }
  return html;
}

/** Los cuatro archivos del papel de una prueba declarativa. */
export async function papelDeclarativo(t) {
  const xlsx = buildWorkbook(t);
  const [docx, pptx] = await Promise.all([bytesWord(t), bytesPowerPoint(t)]);
  const html = htmlConAdjuntos(t, [["xlsx", "Excel con fórmulas", xlsx], ["docx", "Word", docx], ["pptx", "PowerPoint", pptx]]);
  return { xlsx, docx, pptx, html };
}
