// Espejo de las reglas de DATOS del sitio (E7): validación de definiciones y
// filas, números, conciliación, requerimiento y cobertura, lectura de XLSX/CSV
// y mapeo. Escribe backend/app/aud/niif/ciclo/espejo_datos.json.
//
//   node frontend/src/aud/niif/espejo/generarDatos.mjs
//
// Mismo contrato que generar.mjs: pytest exige que Python dé lo mismo, caso por
// caso; vitest falla si el JSON se desactualiza respecto al JavaScript.
// Los archivos de prueba viajan en base64 para que Python lea los MISMOS bytes.
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { strToU8, zipSync } from "fflate";

import {
  calculate,
  catalog,
  checkBuckets,
  controlTotal,
  createProgram,
  createRequests,
  decimal,
  formatted,
  preliminary,
  reconcile,
  validateDefinition,
  validateFlows,
  validateRows,
} from "../sitio/tools/domain.mjs";
import { parseFormats, requestsAsItems, toolCoverage, toolGaps } from "../sitio/tools/coverage.mjs";
import { mappedRows, parseCsv, readSpreadsheet } from "../sitio/tools/files.mjs";
import { presentationExample } from "../sitio/tools/example.mjs";
import { buildWorkbook } from "../sitio/tools/exports.mjs";

export const DESTINO = fileURLToPath(new URL("../../../../../backend/app/aud/niif/ciclo/espejo_datos.json", import.meta.url));

const intentar = (fn) => {
  try {
    const ok = fn();
    return { ok: typeof ok === "bigint" ? { bigint: ok.toString() } : ok };
  } catch (e) {
    return { error: e.message };
  }
};
const b64 = (u8) => Buffer.from(u8).toString("base64");

// --- definiciones -------------------------------------------------------------
const NIIF16 = {
  id: "custom", name: "Arrendamientos NIIF 16", area: "Arrendamientos",
  fields: [
    { key: "id", label: "Contrato", type: "text" }, { key: "pago", label: "Pago", type: "number" },
    { key: "tasa", label: "Tasa", type: "number" }, { key: "n", label: "Períodos", type: "number" },
  ],
  series: {
    count: "n",
    backward: [
      { key: "pendiente", label: "a", op: "add", a: "@apertura", b: "pago", precision: 6 },
      { key: "factor", label: "b", op: "add", a: "tasa", b: "#1", precision: 6 },
      { key: "apertura", label: "c", op: "divide", a: "pendiente", b: "factor", precision: 6 },
    ],
    forward: [{ key: "interes", label: "d", op: "multiply", a: "apertura", b: "tasa", precision: 2 }],
  },
  rules: [{ key: "pasivo_inicial", label: "e", op: "add", a: "apertura_inicial", b: "#0", precision: 2 }],
  control: "pago", primary: "pasivo_inicial",
};
const FLUJOS = {
  id: "custom", name: "Venta a plazo", area: "Ingresos",
  fields: [
    { key: "id", label: "Contrato", type: "text" }, { key: "medicion", label: "Medición", type: "date" },
    { key: "tasa", label: "Tasa", type: "number" }, { key: "precio", label: "Precio", type: "number" },
  ],
  flows: { date: "medicion", rate: "tasa" },
  rules: [{ key: "vp", label: "VP", op: "add", a: "flujos_vp", b: "#0", precision: 2 }],
  control: "precio", primary: "vp",
};
// Condiciones, fechas y tramos, con programa y requerimientos propios de la ficha.
export const ANTIGUEDAD = {
  id: "custom", name: "Pérdida crediticia por antigüedad", area: "Cuentas por cobrar",
  source: { organization: "IFRS Foundation", document: "NIIF 9, párr. 5.5.15", url: "https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/", type: "Norma contable" },
  source_pymes: { organization: "IFRS Foundation", document: "NIIF para las PYMES, Sección 11", url: "https://www.ifrs.org/issued-standards/ifrs-for-smes/", type: "Norma contable" },
  fields: [
    { key: "id", label: "Factura", type: "text" }, { key: "due_date", label: "Vencimiento", type: "date" },
    { key: "exposure", label: "Saldo", type: "number" }, { key: "recorded_allowance", label: "Provisión", type: "number" },
  ],
  rules: [
    { key: "dias", label: "Días", op: "days", a: "due_date", b: "corte", precision: 2 },
    { key: "mora", label: "Mora", op: "max", a: "dias", b: "#0", precision: 2 },
    { key: "tasa", label: "Tasa", op: "band", a: "mora", table: [{ from: "0", value: "0.01" }, { from: "31", value: "0.05" }, { from: "91", value: "0.2" }], precision: 6 },
    { key: "pce", label: "PCE", op: "multiply", a: "exposure", b: "tasa", precision: 2 },
    { key: "vencida", label: "Vencida", op: "gt", a: "mora", b: "#90", precision: 2 },
    { key: "ajuste", label: "Ajuste", op: "if", a: "vencida", b: "pce", c: "#0", precision: 2 },
  ],
  control: "exposure", primary: "ajuste",
  program: [
    { code: "CXC01-01", objective: "Integridad", risk: "Población incompleta", assertion: "Integridad", procedure: "Conciliar.", evidence: "Auxiliar", criterion: "Sin diferencias", source: "NIA 500" },
    { code: "CXC01-02", objective: "Valorar", risk: "Provisión insuficiente", assertion: "Valoración", procedure: "Recalcular.", evidence: "Antigüedad", criterion: "Recalculado", source: "NIIF 9 párr. 5.5.15" },
  ],
  requests: [
    { id: "RQ-001", document: "Antigüedad de saldos", purpose: "Población", procedure: "CXC01-01", formats: ["xlsx", "csv"], required: true, components: ["Quito", "Guayaquil"], group: "", use: "calculo", report: "Cartera por vencimiento", cutoff: "Al cierre", content: "Una fila por factura" },
    { id: "RQ-002", document: "Política de provisiones", purpose: "Tasas", procedure: "CXC01-02", formats: ["pdf"], required: false },
  ],
};
const mutar = (base, fn) => { const d = structuredClone(base); fn(d); return d; };

function definiciones() {
  const casos = [
    ["vnr", catalog.vnr], ["pce", catalog.pce], ["niif16", NIIF16], ["flujos", FLUJOS],
    ["sin nombre", mutar(NIIF16, (d) => { d.name = " "; })],
    ["un campo", mutar(NIIF16, (d) => { d.fields = d.fields.slice(0, 1); })],
    ["sin reglas", mutar(NIIF16, (d) => { d.rules = []; })],
    ["clave con mayúscula", mutar(NIIF16, (d) => { d.fields[1].key = "Pago"; })],
    ["clave __proto__", mutar(NIIF16, (d) => { d.fields[1].key = "__proto__"; })],
    ["tipo raro", mutar(NIIF16, (d) => { d.fields[1].type = "money"; })],
    ["sin id", mutar(NIIF16, (d) => { d.fields[0].key = "codigo"; })],
    ["serie count no numérico", mutar(NIIF16, (d) => { d.series.count = "id"; })],
    ["serie vacía", mutar(NIIF16, (d) => { d.series.backward = []; d.series.forward = []; })],
    ["serie operación rara", mutar(NIIF16, (d) => { d.series.forward[0].op = "pow"; })],
    ["serie @ de otro pase", mutar(NIIF16, (d) => { d.series.forward[0].a = "@apertura"; })],
    ["serie operando ausente", mutar(NIIF16, (d) => { d.series.forward[0].b = "inexistente"; })],
    ["serie semilla ^", mutar(NIIF16, (d) => { d.series.forward[0].seed = "^apertura"; })],
    ["serie semilla ausente", mutar(NIIF16, (d) => { d.series.forward[0].seed = "nada"; })],
    ["serie orden malo", mutar(NIIF16, (d) => { d.series.order = ["forward", "forward"]; })],
    ["serie orden forward primero", mutar(NIIF16, (d) => { d.series.order = ["forward", "backward"]; })],
    ["agregado reservado", mutar(NIIF16, (d) => { d.fields.push({ key: "interes_total", label: "x", type: "number" }); })],
    ["flujos sin fecha", mutar(FLUJOS, (d) => { d.flows.date = "precio"; })],
    ["flujos sin tasa", mutar(FLUJOS, (d) => { d.flows.rate = "medicion"; })],
    ["flujos clave reservada", mutar(FLUJOS, (d) => { d.fields.push({ key: "flujos_vp", label: "x", type: "number" }); })],
    ["regla precisión 3", mutar(NIIF16, (d) => { d.rules[0].precision = 3; })],
    ["regla operando texto", mutar(NIIF16, (d) => { d.rules[0].a = "id"; })],
    ["regla constante mala", mutar(NIIF16, (d) => { d.rules[0].b = "#1e5"; })],
    ["control de texto", mutar(NIIF16, (d) => { d.control = "id"; })],
    ["principal inexistente", mutar(NIIF16, (d) => { d.primary = "nada"; })],
    ["cédulas vacías", mutar(NIIF16, (d) => { d.sheets = []; })],
    ["cédula inventada", mutar(NIIF16, (d) => { d.sheets = ["99_X"]; })],
    ["cédulas válidas", mutar(NIIF16, (d) => { d.sheets = ["02_Programa", "13_Cuadro"]; })],
    ["no es objeto", null],
    ["antigüedad con plan", ANTIGUEDAD],
    ["solo programa", mutar(ANTIGUEDAD, (d) => { delete d.requests; })],
    ["regla operación inventada", mutar(ANTIGUEDAD, (d) => { d.rules[1].op = "pow"; })],
    ["days sobre número", mutar(ANTIGUEDAD, (d) => { d.rules[0].a = "exposure"; })],
    ["days sin segundo operando", mutar(ANTIGUEDAD, (d) => { delete d.rules[0].b; })],
    ["band sin tabla", mutar(ANTIGUEDAD, (d) => { delete d.rules[2].table; })],
    ["band vacía", mutar(ANTIGUEDAD, (d) => { d.rules[2].table = []; })],
    ["band desordenada", mutar(ANTIGUEDAD, (d) => { d.rules[2].table[1].from = "0"; })],
    ["band valor malo", mutar(ANTIGUEDAD, (d) => { d.rules[2].table[1].value = "5%"; })],
    ["band tramo nulo", mutar(ANTIGUEDAD, (d) => { d.rules[2].table[1] = null; })],
    ["band operando fecha", mutar(ANTIGUEDAD, (d) => { d.rules[2].a = "due_date"; })],
    ["if sin c", mutar(ANTIGUEDAD, (d) => { delete d.rules[5].c; })],
    ["if c inexistente", mutar(ANTIGUEDAD, (d) => { d.rules[5].c = "nada"; })],
    ["gt con texto", mutar(ANTIGUEDAD, (d) => { d.rules[4].a = "id"; })],
    ["programa vacío", mutar(ANTIGUEDAD, (d) => { d.program = []; })],
    ["programa nulo", mutar(ANTIGUEDAD, (d) => { d.program = null; })],
    ["procedimiento sin riesgo", mutar(ANTIGUEDAD, (d) => { d.program[1].risk = " "; })],
    ["código con espacio", mutar(ANTIGUEDAD, (d) => { d.program[1].code = "CXC 02"; })],
    ["código repetido", mutar(ANTIGUEDAD, (d) => { d.program[1].code = "CXC01-01"; })],
    ["requerimientos sin programa", mutar(ANTIGUEDAD, (d) => { delete d.program; })],
    ["requerimientos vacíos", mutar(ANTIGUEDAD, (d) => { d.requests = []; })],
    ["requerimiento sin propósito", mutar(ANTIGUEDAD, (d) => { d.requests[1].purpose = ""; })],
    ["requerimiento id repetido", mutar(ANTIGUEDAD, (d) => { d.requests[1].id = "RQ-001"; })],
    ["requerimiento procedimiento ajeno", mutar(ANTIGUEDAD, (d) => { d.requests[1].procedure = "OTRO"; })],
    ["requerimiento formato raro", mutar(ANTIGUEDAD, (d) => { d.requests[0].formats = ["xlsx", "exe"]; })],
    ["requerimiento sin formatos", mutar(ANTIGUEDAD, (d) => { d.requests[0].formats = []; })],
    ["componentes no lista", mutar(ANTIGUEDAD, (d) => { d.requests[0].components = "Quito"; })],
    ["componente vacío", mutar(ANTIGUEDAD, (d) => { d.requests[0].components = ["Quito", " "]; })],
    ["uso raro", mutar(ANTIGUEDAD, (d) => { d.requests[0].use = "otro"; })],
  ];
  return casos.map(([nombre, d]) => ({ nombre, d, esperado: intentar(() => validateDefinition(structuredClone(d))) }));
}

// --- números y conciliación ---------------------------------------------------
const NUMEROS = ["0", "1", "-1", "12.5", "0.000001", "123456789012.123456", "1234567890123", "1.1234567",
  "1,5", "1e3", " 7.25 ", "", "-0", "999999999999.999999", "100000000000000.1", "00012.500", "abc", "+5", ".5", "5.", "123456789.123456", "1234567890.123456", "-000123456789.123456"];
const FORMATEAR = ["0", "1", "5000000", "-5000000", "1234567", "-1234567", "999999", "4999999", "-4500000", "123456789012345678"];

function conciliaciones() {
  const casos = [
    ["100.00", "100.00", "0", ""], ["100.00", "99.00", "1", ""], ["100.00", "98.00", "1", ""],
    ["100.00", "98.00", "1", "Diferencia aceptada por partidas en tránsito"], ["100.00", "98.00", "1", "corto"],
    ["-5.50", "-5.5", "0", ""], ["100", "100.001", "0", ""], ["100", "100", "-1", ""], ["100", "abc", "0", ""],
  ];
  return casos.map(([total, ledger, tol, acc]) => ({ total, ledger, tol, acc, esperado: intentar(() => reconcile(total, ledger, tol, acc)) }));
}

// --- filas ---------------------------------------------------------------------
function filas() {
  const vnr = presentationExample().rows.map(({ _file, _sheet, ...r }) => r);
  const base = (cambios = {}) => vnr.map((r) => ({ ...r })).map((r, i) => (i === 0 ? { ...r, ...cambios } : r));
  const pce = [{ id: "F-1", customer: "Cliente", due_date: "2025-10-31", balance: "1000", recorded_allowance: "0", _row: 2 }];
  const casos = [
    ["vnr ok", catalog.vnr, base()],
    ["duplicado exacto", catalog.vnr, [...base(), { ...base()[0], _row: 9 }]],
    ["id repetido", catalog.vnr, [...base(), { ...base()[1], id: "0001", _row: 9 }]],
    ["fórmula sin valor", catalog.vnr, base({ unit_cost: "FORMULA_SIN_VALOR_GUARDADO" })],
    ["error de excel", catalog.vnr, base({ selling_price: "ERROR_EXCEL: #DIV/0!" })],
    ["faltante", catalog.vnr, base({ quantity: " " })],
    ["texto largo", catalog.vnr, base({ description: "x".repeat(1001) })],
    ["negativo", catalog.vnr, base({ quantity: "-1" })],
    ["número inválido", catalog.vnr, base({ unit_cost: "1,5" })],
    ["fila total", catalog.vnr, base({ id: "Total general" })],
    ["subtotal", catalog.vnr, base({ id: "SUBTOTAL" })],
    ["sin filas", catalog.vnr, []],
    ["pce ok", catalog.pce, pce],
    ["pce fecha mala", catalog.pce, [{ ...pce[0], due_date: "2025-02-30" }]],
  ];
  return casos.map(([nombre, d, rs]) => ({ nombre, d, filas: rs, esperado: intentar(() => validateRows(d, rs)) }));
}

function totalesControl() {
  const vnr = presentationExample().rows;
  return [
    { d: catalog.vnr, filas: vnr, esperado: intentar(() => controlTotal(catalog.vnr, vnr)) },
    { d: catalog.pce, filas: [{ balance: "1000.10" }, { balance: "-0.10" }], esperado: intentar(() => controlTotal(catalog.pce, [{ balance: "1000.10" }, { balance: "-0.10" }])) },
    { d: catalog.vnr, filas: [{ quantity: "3", unit_cost: "0.3333333" }], esperado: intentar(() => controlTotal(catalog.vnr, [{ quantity: "3", unit_cost: "0.3333333" }])) },
    { d: catalog.vnr, filas: [{ quantity: "3", unit_cost: "0.333333" }], esperado: intentar(() => controlTotal(catalog.vnr, [{ quantity: "3", unit_cost: "0.333333" }])) },
  ];
}

function flujos() {
  const casos = [
    [[{ id: "C-1", fecha: "2026-01-31", importe: "1000" }]], [[]], [[{ id: " ", fecha: "2026-01-31", importe: "1" }]],
    [[{ id: "C-1", fecha: "2026-02-30", importe: "1" }]], [[{ id: "C-1", fecha: "2026-01-31", importe: "1,0" }]], ["no"],
  ];
  return casos.map(([f]) => ({ flujos: f, esperado: intentar(() => validateFlows(f)) }));
}

// --- requerimiento y cobertura ------------------------------------------------
function requerimientos() {
  const eng = { framework: "NIIF completas" };
  const custom = { ...NIIF16 };
  return [
    { definicion: "vnr", corte: "2025-12-31", esperado: createRequests(createProgram(catalog.vnr, eng), "2025-12-31", catalog.vnr) },
    { definicion: "pce", corte: "2025-12-31", esperado: createRequests(createProgram(catalog.pce, eng), "2025-12-31", catalog.pce) },
    { definicion: custom, corte: "2025-06-30", esperado: createRequests(createProgram(custom, eng), "2025-06-30", custom) },
    { definicion: ANTIGUEDAD, corte: "2025-12-31", esperado: createRequests(createProgram(ANTIGUEDAD, eng), "2025-12-31", ANTIGUEDAD) },
  ];
}

const FORMATOS = ["XLSX / CSV", "XLSX / DOCX / CSV / XML / PDF / TXT / ZIP / imágenes", "pdf", "Excel o PDF", "", "Imagenes JPG", "md, txt; xml"];

function coberturas() {
  const reqs = createRequests(createProgram(catalog.vnr, { framework: "NIIF completas" }), "2025-12-31", catalog.vnr);
  reqs[0].components = ["Bodega Quito", "Bodega Guayaquil"];
  reqs[2].group = "Costos"; reqs[3].group = "Costos";
  const f = (id, requestId, component) => ({ id, requestId, component });
  const escenarios = [
    ["nada", [], []],
    ["una bodega", [f("a", "RQ-001", "Bodega Quito")], []],
    ["completo", [f("a", "RQ-001", "Bodega Quito"), f("b", "RQ-001", "Bodega Guayaquil"), f("c", "RQ-002"), f("d", "RQ-003")], []],
    ["rechazado", [f("a", "RQ-001", "Bodega Quito"), f("b", "RQ-001", "Bodega Guayaquil"), f("c", "RQ-002"), f("d", "RQ-003")], ["b"]],
    ["otra alternativa", [f("a", "RQ-001", "Bodega Quito"), f("b", "RQ-001", "Bodega Guayaquil"), f("c", "RQ-002"), f("e", "RQ-VNR-04")], []],
  ];
  return {
    requerimientos: reqs,
    items: requestsAsItems(reqs),
    escenarios: escenarios.map(([nombre, files, rechazados]) => ({
      nombre, archivos: files, rechazados,
      huecos: toolGaps(reqs, files, rechazados), cobertura: toolCoverage(reqs, files, rechazados),
    })),
  };
}

// --- lectura de hojas y mapeo -------------------------------------------------
const XML = (s) => strToU8('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + s);
function libro({ date1904 = false, absoluto = false, hojas }) {
  const ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"';
  const z = {
    "[Content_Types].xml": XML("<Types/>"),
    "xl/workbook.xml": XML(`<workbook ${ns}>${date1904 ? '<workbookPr date1904="1"/>' : ""}<sheets>${hojas.map((h, i) => `<sheet name="${h.nombre}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join("")}</sheets></workbook>`),
    "xl/_rels/workbook.xml.rels": XML(`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${hojas.map((h, i) => `<Relationship Id="rId${i + 1}" Type="x" Target="${absoluto ? "/xl/" : ""}worksheets/sheet${i + 1}.xml"/>`).join("")}</Relationships>`),
    "xl/sharedStrings.xml": XML(`<sst ${ns}><si><t>  Código  </t></si><si><r><t>Des</t></r><r><t xml:space="preserve">cripción </t></r></si><si><t>A&amp;B &lt;ok&gt;</t></si><si><t/></si></sst>`),
  };
  hojas.forEach((h, i) => { z[`xl/worksheets/sheet${i + 1}.xml`] = XML(`<worksheet ${ns}><sheetData>${h.filas}</sheetData></worksheet>`); });
  return zipSync(z, { mtime: new Date("2026-01-01T00:00:00Z") });
}
function archivos() {
  const raro = libro({
    hojas: [{
      nombre: "Datos",
      filas: '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="s"><v>1</v></c><c r="D1" t="s"><v>2</v></c></row>' +
        '<row r="2"><c r="A2" t="inlineStr"><is><t> P-1 </t></is></c><c r="B2"><v>1.5E-3</v></c><c r="C2"><f>A1*2</f></c><c r="D2" t="e"><v>#DIV/0!</v></c><c r="E2" t="b"><v>1</v></c></row>' +
        '<row r="4"><c r="B4"><v>45657</v></c><c r="AA4"><v>0.30000000000000004</v></c><c r="C4" t="s"><v>3</v></c></row>' +
        '<row r="5"><c r="A5" t="inlineStr"><is><r><t>ri</t></r><r><t>co</t></r></is></c><c r="B5"><f>B4+1</f><v>45658</v></c></row>' +
        // Referencias numéricas, como escriben openpyxl y muchos ERP (&#243; = ó).
        '<row r="6"><c r="A6" t="inlineStr"><is><t>C&#243;digo &#xE1; &#8364;</t></is></c><c r="B6" t="inlineStr"><is><t xml:space="preserve"></t></is></c></row>',
    }, { nombre: "Vacía", filas: "" }],
  });
  const f1904 = libro({ date1904: true, absoluto: true, hojas: [{ nombre: "H", filas: '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>X</t></is></c><c r="B2"><v>44196</v></c></row>' }] });
  const vnr = buildWorkbook(presentationExample());
  const csvs = [
    ["coma.csv", "id,cantidad\n0001,10\n0002,\"1,5\"\n"],
    ["punto_y_coma.csv", "﻿id;cantidad;nota\r\n0001;10;\"dijo \"\"hola\"\"\"\r\n\r\n0002;5;x"],
    ["comillas.csv", 'a,b\n"sin cerrar,1\n'],
  ];
  const casos = [
    { nombre: "raro.xlsx", bytes: raro }, { nombre: "fecha1904.xlsx", bytes: f1904 }, { nombre: "vnr_del_sitio.xlsx", bytes: vnr },
    ...csvs.map(([n, t]) => ({ nombre: n, bytes: strToU8(t) })),
    { nombre: "doc.pdf", bytes: strToU8("%PDF") },
  ];
  return casos.map((c) => ({ nombre: c.nombre, b64: b64(c.bytes), esperado: intentar(() => readSpreadsheet(c.bytes, c.nombre)) }));
}

function mapeos() {
  const leer = (bytes, n) => readSpreadsheet(bytes, n);
  const raro = archivos()[0];
  const hoja = leer(Buffer.from(raro.b64, "base64"), "raro.xlsx").sheets[0];
  const hoja1904 = leer(Buffer.from(archivos()[1].b64, "base64"), "fecha1904.xlsx").sheets[0];
  const defFecha = { fields: [{ key: "id", label: "Código", type: "text" }, { key: "fecha", label: "Fecha", type: "date" }] };
  const vnrLibro = leer(buildWorkbook(presentationExample()), "vnr.xlsx").sheets.find((s) => s.name === "05_Data_Original");
  const mapaVnr = Object.fromEntries(catalog.vnr.fields.map((f, i) => [f.key, i]));
  const archivo = { id: "f-1", name: "origen.xlsx" };
  const casos = [
    ["fechas 1900", hoja, 1, { id: 0, fecha: 1 }, defFecha],
    ["fechas 1904", hoja1904, 1, { id: 0, fecha: 1 }, defFecha],
    ["vnr del sitio", vnrLibro, 4, mapaVnr, catalog.vnr],
    ["encabezado malo", hoja, 0, { id: 0, fecha: 1 }, defFecha],
    ["falta mapear", hoja, 1, { id: 0 }, defFecha],
    ["columna fuera", hoja, 1, { id: 0, fecha: 40 }, defFecha],
  ];
  return casos.map(([nombre, sheet, header, mapping, d]) => ({ nombre, sheet, header, mapping, d, archivo, esperado: intentar(() => mappedRows(sheet, header, mapping, d, archivo)) }));
}

// --- E8: tramos de mora, excepciones y análisis preliminar ---------------------
const TRAMOS = [{ min: 0, max: 30, rate: "0.01" }, { min: 31, max: 90, rate: "0.05" }, { min: 91, max: null, rate: "0.5" }];

function tramos() {
  const t = (buckets, cutoff = "2025-12-31") => ({ cutoff, buckets });
  const casos = [
    ["válidos", t(TRAMOS)],
    ["uno solo sin límite", t([{ min: 0, max: null, rate: 1 }])],
    ["sin corte", t(TRAMOS, "")],
    ["corte inválido", t(TRAMOS, "2025-02-30")],
    ["sin tramos", t([])],
    ["no es lista", t("x")],
    ["no empieza en cero", t([{ min: 1, max: null, rate: "0.1" }])],
    ["hueco", t([{ min: 0, max: 30, rate: "0.1" }, { min: 32, max: null, rate: "0.2" }])],
    ["superpuestos", t([{ min: 0, max: 30, rate: "0.1" }, { min: 30, max: null, rate: "0.2" }])],
    ["máximo menor que mínimo", t([{ min: 0, max: -1, rate: "0.1" }, { min: 0, max: null, rate: "0.2" }])],
    ["sin límite en medio", t([{ min: 0, max: null, rate: "0.1" }, { min: 1, max: null, rate: "0.2" }])],
    ["último con límite", t([{ min: 0, max: 30, rate: "0.1" }])],
    ["máximo ausente", t([{ min: 0, rate: "0.1" }])],
    ["mínimo decimal", t([{ min: 0.5, max: null, rate: "0.1" }])],
    ["mínimo entero en decimal", t([{ min: 0.0, max: 30.0, rate: "0.1" }, { min: 31, max: null, rate: "0.2" }])],
    ["tasa mayor a uno", t([{ min: 0, max: null, rate: "1.5" }])],
    ["tasa negativa", t([{ min: 0, max: null, rate: "-0.1" }])],
    ["tasa inválida", t([{ min: 0, max: null, rate: "5%" }])],
    ["mínimo booleano", t([{ min: false, max: null, rate: "0.1" }])],
  ];
  return casos.map(([nombre, par]) => ({ nombre, p: par, esperado: intentar(() => checkBuckets(par)) }));
}

// Cada caso corre calculate() del sitio: Python recibe las mismas filas, corre
// su motor y debe sacar exactamente estas excepciones.
function excepcionesCasos() {
  const vnr = [
    { id: "N", description: "VNR negativo", quantity: "2", unit_cost: "10", selling_price: "5", completion_cost: "4", selling_cost: "3", recorded_allowance: "0", _row: 7 },
    { id: "R", description: "Reverso", quantity: "1", unit_cost: "10", selling_price: "20", completion_cost: "0", selling_cost: "0", recorded_allowance: "3" },
    { id: "S", description: "Sin hallazgo", quantity: "1", unit_cost: "10", selling_price: "20", completion_cost: "0", selling_cost: "0", recorded_allowance: "0" },
  ];
  const pce = [
    { id: "F-1", due_date: "2025-12-20", exposure: "1000", recorded_allowance: "0", subsequent_collection: "0" },
    { id: "F-2", due_date: "2025-01-15", exposure: "400", recorded_allowance: "500", subsequent_collection: "0" },
  ];
  const cuadro = {
    id: "custom", name: "Cuadro", area: "Préstamos",
    fields: [{ key: "id", label: "Contrato", type: "text" }, { key: "pago", label: "Pago", type: "number" }, { key: "n", label: "Períodos", type: "number" }],
    series: { count: "n", forward: [{ key: "cierre", label: "Saldo final", op: "add", a: "pago", b: "#0", precision: 2 }] },
    rules: [{ key: "total", label: "Total", op: "add", a: "cierre_total", b: "#0", precision: 2 }],
    control: "pago", primary: "total",
  };
  const casos = [
    ["vnr", catalog.vnr, vnr, {}],
    ["vnr del ejemplo del sitio", catalog.vnr, presentationExample().rows, {}],
    ["pce con tramos", catalog.pce, pce, { cutoff: "2025-12-31", buckets: TRAMOS }],
    ["cuadro que no cierra", cuadro, [{ id: "A", pago: "0", n: "3" }, { id: "B", pago: "5", n: "2", _row: 9 }], {}],
    ["antigüedad con condiciones", ANTIGUEDAD, [
      { id: "A", due_date: "2025-12-15", exposure: "1000", recorded_allowance: "0" },
      { id: "B", due_date: "2025-01-01", exposure: "500", recorded_allowance: "40" },
    ], { cutoff: "2025-12-31" }],
  ];
  return casos.map(([nombre, d, rows, par]) => ({ nombre, d, filas: rows, p: par, esperado: calculate(d, rows, par, []).exceptions }));
}

function preliminares() {
  const t = (totals, excepciones, rec) => ({
    definition: { name: "Valor neto de realización" },
    run: { engine: "3.0.0", rows: [{}, {}, {}], totals, exceptions: excepciones },
    reconciliation: rec,
  });
  const casos = [
    t({ cost: "470.00", impairment: "50.00" }, [{}], { difference: "0.00", within: true, acceptance: "" }),
    t({}, [], { difference: "-10.00", within: false, acceptance: "Partidas en tránsito documentadas al corte" }),
  ];
  return casos.map((c) => ({ t: c, esperado: preliminary(c) }));
}

export function contenido() {
  return {
    _origen: "Generado por frontend/src/aud/niif/espejo/generarDatos.mjs desde las copias intactas del sitio. No editar a mano.",
    definiciones: definiciones(),
    decimales: NUMEROS.map((v) => ({ v, esperado: intentar(() => decimal(v)) })),
    formateados: FORMATEAR.map((v) => ({ v, esperado: intentar(() => formatted(BigInt(v))) })),
    conciliaciones: conciliaciones(),
    filas: filas(),
    totales_control: totalesControl(),
    flujos: flujos(),
    requerimientos: requerimientos(),
    formatos: FORMATOS.map((v) => ({ v, esperado: parseFormats(v) })),
    cobertura: coberturas(),
    csv_directo: [["x;y\n1;2", undefined], ["a\tb\n1\t2", "\t"], ["a|b", "|"]].map(([t, sep]) => ({ texto: t, sep: sep ?? null, esperado: intentar(() => parseCsv(t, sep)) })),
    archivos: archivos(),
    mapeos: mapeos(),
    tramos: tramos(),
    excepciones: excepcionesCasos(),
    preliminares: preliminares(),
  };
}

export const serializar = (c) => JSON.stringify(c, null, 1) + "\n";

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const c = contenido();
  writeFileSync(DESTINO, serializar(c));
  console.log(`espejo_datos.json: ${c.definiciones.length} definiciones, ${c.filas.length} poblaciones, ${c.archivos.length} archivos, ${c.mapeos.length} mapeos`);
}
