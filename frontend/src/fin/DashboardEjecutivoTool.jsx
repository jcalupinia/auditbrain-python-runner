import { useMemo, useState } from "react";
import {
  extractTaxPlan,
  exportTaxPlan,
  generarPresentacionTax,
  downloadTaxPlantilla,
} from "../api.js";
import { fmt, f0, m } from "../tax/format.js";
import {
  ESF_SCHEMA,
  ER_SCHEMA,
  ANIOS,
  PROJ,
  EX,
  DEFAULT_CTRL,
  DEFAULT_PARAMS,
  INPUT_KEYS,
} from "../tax/seed.js";
import {
  tAC, tActivo, tPC, tPasivo, tPat, ub, ebit, uai, neta, projectFinancials,
} from "../tax/engine.js";
import "../tax/tax.css";
import {
  DEFAULT_HEADER,
  EMPTY_DETALLE,
  BLANK_ROW,
  PERIODO_MESES,
  PARSER_TO_DASH,
  mapToDashboard,
  buildDetailedBalance,
  checkBalance,
  normalizarER,
} from "./finModel.js";
import { downloadStandaloneHTML, buildStandaloneHTML } from "./dashboardExport.js";
import { comparacionFilas, construirParesEri } from "./finComparaciones.js";
import { alinearPorIdentidad, tienePeriodosTipados } from "./finPeriodos.js";

// Claves de input por estado (para detectar presencia de ESF/ER tras alinear).
const ESF_INPUT = ESF_SCHEMA.filter((r) => r[0] === "in" || r[0] === "det").map((r) => r[1]);
const ER_INPUT = ER_SCHEMA.filter((r) => r[0] === "in" || r[0] === "det").map((r) => r[1]);
import ChartSelectorModal from "./ChartSelectorModal.jsx";
import { exportDashboardExcel } from "./excelExport.js";
import { exportDashboardPDF, exportDashboardWord, exportDashboardPPTX } from "./reportExport.js";

// Mapea el código del gráfico recomendado por el Skill 051 al estilo soportado
// por el dashboard (combo|barras|lineas|area|puntos). Los no soportados como
// estilo de tendencia devuelven null (se informa al usuario).
const SKILL051_TO_STYLE = {
  line: "lineas", vbar: "barras", hbar: "barras", stacked: "barras",
  area: "area", combo: "combo", scatter: "puntos",
};

const clone = (o) => JSON.parse(JSON.stringify(o));
let _pid = 0;
const nextId = () => `p${++_pid}`;

const SECTIONS = [
  ["ingesta", "i", "Datos e ingesta"],
  ["periodos", "P", "Períodos"],
  ["eeff", "1", "Estados financieros"],
  ["comparaciones", "Δ", "Comparaciones"],
  ["detalle", "2", "Detalle CFO"],
  ["proyeccion", "3", "Proyección 3 estados"],
  ["preview", "★", "Dashboard ejecutivo"],
];

// Modelo D vacío con `n` columnas (períodos).
function emptyD(n) {
  const D = {};
  INPUT_KEYS.forEach((k) => (D[k] = Array(n).fill(0)));
  D.dna = Array(n).fill(0);
  return D;
}

// Líneas calculadas (espejo del tool de Planificación).
function calcLine(D, sp, c) {
  switch (sp[1]) {
    case "totalAC": return tAC(D, c);
    case "totalANC": return D.ppe[c] + D.actImpDif[c];
    case "totalActivo": return tActivo(D, c);
    case "totalPC": return tPC(D, c);
    case "totalPNC": return D.benefPost[c] + D.cxpRel[c] + D.pasImpDif[c];
    case "totalPasivo": return tPasivo(D, c);
    case "totalPat": return tPat(D, c);
    case "ub": return ub(D, c);
    case "ebit": return ebit(D, c);
    case "uai": return uai(D, c);
    case "neta": return neta(D, c);
    default: return 0;
  }
}

// Períodos iniciales: ejemplo SIGMANSERVICES, 3 años completos.
const initPeriodos = () =>
  ANIOS.map((y) => ({ id: nextId(), label: String(y), labelESF: String(y), meses: 12, normalizar: true }));

export default function DashboardEjecutivoTool({ initialSection = "ingesta" } = {}) {
  const [periodos, setPeriodos] = useState(initPeriodos);
  const [D, setD] = useState(() => clone(EX));
  const [header, setHeader] = useState(() => ({ ...DEFAULT_HEADER, empresa: DEFAULT_PARAMS.empresa }));
  const [detalle, setDetalle] = useState(() => clone(EMPTY_DETALLE));
  const [params] = useState(() => ({ ...DEFAULT_PARAMS }));
  const [section, setSection] = useState(initialSection);
  const [nivel, setNivel] = useState("resumido");
  const [chartStyle, setChartStyle] = useState("combo"); // estilo de gráfico del dashboard
  const [periodoTipo, setPeriodoTipo] = useState("anual"); // meses por defecto al cargar

  // Recibe el gráfico recomendado por el asistente Skill 051 y lo aplica.
  const aplicarChartSkill051 = (chart) => {
    const estilo = SKILL051_TO_STYLE[chart?.code];
    if (estilo) {
      setChartStyle(estilo);
      setSection("preview");
    } else {
      alert(
        `El gráfico recomendado "${chart?.name}" es ideal según el Skill 051, pero el ` +
        `dashboard ejecutivo soporta como estilo de tendencia: barras, líneas, área, ` +
        `puntos y combinado. Para ${chart?.name} usa Power BI / Chart.js con el snippet del asistente.`
      );
    }
  };

  // Ingesta
  const [cuentas, setCuentas] = useState([]); // detalle por cuenta (drill-down)
  // Resultados crudos del backend (para las comparaciones período-a-período,
  // que necesitan los períodos SIN fusionar por año — la fusión colapsa los
  // cortes parciales). Solo se pueblan cuando el backend devuelve `comparaciones`.
  const [cmpResults, setCmpResults] = useState([]);
  const [fuente, setFuente] = useState(null);
  const [files, setFiles] = useState([]);
  const [ingBusy, setIngBusy] = useState(false);
  const [ingMsg, setIngMsg] = useState(null);
  const [busyX, setBusyX] = useState(false);
  const [busyP, setBusyP] = useState(false);

  /* ---------- derivados de períodos ---------- */
  const labels = useMemo(() => periodos.map((p) => p.label), [periodos]);
  const baseMeses = useMemo(
    () => (periodos.length ? Math.min(...periodos.map((p) => p.meses || 12)) : 12),
    [periodos]
  );
  const hayProrrateo = useMemo(
    () => periodos.some((p) => p.normalizar && (p.meses || 12) !== baseMeses),
    [periodos, baseMeses]
  );
  const todosAnuales = useMemo(() => periodos.every((p) => (p.meses || 12) === 12), [periodos]);
  // D con el Estado de Resultados normalizado a la base común (balance intacto).
  const Dnorm = useMemo(() => normalizarER(D, periodos, baseMeses), [D, periodos, baseMeses]);

  /* ---------- mutadores de datos ---------- */
  const setCell = (key, c, val) =>
    setD((prev) => ({ ...prev, [key]: prev[key].map((v, i) => (i === c ? parseFloat(val) || 0 : v)) }));

  // Reemplaza TODOS los períodos por 3 años fijos (para F-101 / balance resumido).
  const cargarFijos3 = (data, empresa) => {
    const next = emptyD(3);
    Object.entries(data || {}).forEach(([k, arr]) => {
      if (next[k] && Array.isArray(arr)) next[k] = arr.map((v) => (v == null ? 0 : v));
    });
    setD(next);
    setPeriodos(ANIOS.map((y) => ({ id: nextId(), label: String(y), labelESF: String(y), meses: 12, normalizar: true })));
    if (empresa) setHeader((h) => ({ ...h, empresa }));
  };

  // Carga balances internos/auditados FUSIONANDO todos los archivos por año.
  // El cliente suele tener el Balance (ESF) y el Estado de Resultados (ER) en
  // archivos SEPARADOS, cada uno con comparativo de varios años. Aquí se unen:
  // ESF + ER del mismo año = UN período. Reemplaza el dataset (la data de
  // ejemplo es solo un placeholder). `label`=fecha del ER, `labelESF`=del balance.
  const cargarInternos = (items, mesesDefault) => {
    const num = (v) => (v == null ? 0 : (+v || 0));
    // Camino NUEVO: los balances resumidos por nombre traen períodos tipados
    // (label/tipo/meses/anio). Se alinean por IDENTIDAD (año-mes) en vez de por
    // año extraído — así el corte parcial may-26 y los cierres anuales quedan en
    // su columna correcta (la fusión por año los desalineaba). El eje lo define
    // el Balance; los cortes solo-ER (may-25) se usan aparte en Comparaciones.
    const typed = items.map((it) => it.res || it).filter(tienePeriodosTipados);
    if (typed.length && typed.length === items.length) {
      const { D: aD, periodos: aPer } = alinearPorIdentidad(typed[0]);
      const nz = (arr) => (arr || []).some((v) => num(v));
      const hasESF = ESF_INPUT.some((k) => nz(aD[k]));
      const hasER = ER_INPUT.some((k) => nz(aD[k]));
      const patInc = aPer.some((_p, c) => {
        const t = num(aD.capital[c]) + num(aD.reservas[c]) + num(aD.ori[c]) + num(aD.resAcum[c]);
        return t > 0 && num(aD.capital[c]) === 0 && num(aD.reservas[c]) === 0;
      });
      setD(aD);
      // normalizar:false → el dashboard muestra las cifras REALES por período
      // (may-26 sus 5 meses, los anuales sus 12); la comparación 5m-vs-anual se
      // resuelve en el panel Comparaciones, no prorrateando el estado completo.
      setPeriodos(aPer.map((p) => ({ id: nextId(), label: p.label, labelESF: p.labelESF, meses: p.meses, normalizar: false })));
      setCuentas([]); // el resumido por nombre no trae detalle por cuenta
      return { count: aPer.length, patInc, hasESF, hasER };
    }
    const yearOf = (s) => { const m = String(s == null ? "" : s).match(/20\d{2}/); return m ? m[0] : null; };
    const byYear = new Map();
    const order = [];
    const cuentasMap = new Map(); // detalle por cuenta (drill-down), fusionado por año
    items.forEach((it, fileIdx) => {
      const res = it.res || it;            // compat: {res,name} o res directo
      const fname = it.name || "";
      const d = res.data || {};
      const anios =
        res.anios_detectados && res.anios_detectados.length
          ? res.anios_detectados.map(String)
          : ((res.labels_er && res.labels_er.length ? res.labels_er : res.labels_esf) || []).map(String);
      const lblESF = res.labels_esf || [];
      const lblER = res.labels_er || [];
      const n =
        anios.length ||
        Math.max(0, ...Object.values(d).map((a) => (Array.isArray(a) ? a.length : 0)));
      const fnYear = yearOf(fname); // p.ej. "BALANCE 2023.xlsx" -> 2023
      const colYear = []; // columna j -> año (clave de período) de ESTE archivo
      for (let j = 0; j < n; j++) {
        // Clave de período por AÑO: del contenido (anios/labels), o del nombre del
        // archivo si trae 1 sola columna; si no hay forma, clave única por archivo
        // (no se mezcla con otros archivos sin año).
        const yr =
          yearOf(anios[j]) ||
          yearOf(lblESF[j]) ||
          yearOf(lblER[j]) ||
          (n === 1 && fnYear ? fnYear : null) ||
          `arch${fileIdx}-${j}`;
        colYear[j] = yr;
        if (!byYear.has(yr)) {
          byYear.set(yr, { data: {}, labelESF: null, labelER: null, fname: fname.replace(/\.(xlsx|xls)$/i, "") });
          order.push(yr);
        }
        const slot = byYear.get(yr);
        Object.keys(d).forEach((k) => {
          const v = Array.isArray(d[k]) ? num(d[k][j]) : 0;
          if (v !== 0) slot.data[k] = v; // overlay: ESF del balance, ER del resultado
        });
        if (lblESF[j]) slot.labelESF = lblESF[j];
        if (lblER[j]) slot.labelER = lblER[j];
      }
      // Fusión del detalle por cuenta: clave (sec|rubroDash|codigo|nombre); los
      // valores se acumulan por año usando el mapeo columna→año de este archivo.
      (res.detalle || []).forEach((acc) => {
        const dk = PARSER_TO_DASH[acc.key] || acc.key;
        const ck = acc.sec + "|" + dk + "|" + (acc.codigo || "") + "|" + acc.nombre;
        let cm = cuentasMap.get(ck);
        if (!cm) { cm = { sec: acc.sec, key: dk, codigo: acc.codigo || "", nombre: acc.nombre, byYear: {} }; cuentasMap.set(ck, cm); }
        (acc.vals || []).forEach((v, j) => {
          const yr = colYear[j];
          if (yr == null) return;
          cm.byYear[yr] = (cm.byYear[yr] || 0) + num(v);
        });
      });
    });
    // Años primero (ascendente); las claves sin año ("arch…") al final.
    order.sort((a, b) => {
      const ya = /^20\d{2}$/.test(a), yb = /^20\d{2}$/.test(b);
      if (ya && yb) return a < b ? -1 : a > b ? 1 : 0;
      if (ya) return -1;
      if (yb) return 1;
      return a < b ? -1 : 1;
    });
    const baseKeys = INPUT_KEYS.concat(["dna"]);
    const nextD = {};
    baseKeys.forEach((k) => (nextD[k] = []));
    const nextPer = order.map((yr) => {
      const slot = byYear.get(yr);
      baseKeys.forEach((k) => nextD[k].push(num(slot.data[k])));
      const fallback = /^20\d{2}$/.test(yr) ? yr : slot.fname || yr;
      return {
        id: nextId(),
        label: slot.labelER || slot.labelESF || fallback,
        labelESF: slot.labelESF || slot.labelER || fallback,
        meses: mesesDefault,
        normalizar: true,
      };
    });
    setD(nextD);
    setPeriodos(nextPer);
    // Cuentas (detalle) alineadas al orden de períodos; descarta filas todo-cero.
    const cuentasOut = [...cuentasMap.values()]
      .map((cm) => ({ sec: cm.sec, key: cm.key, codigo: cm.codigo, nombre: cm.nombre, vals: order.map((yr) => Math.round(num(cm.byYear[yr]))) }))
      .filter((c) => c.vals.some((v) => v !== 0));
    setCuentas(cuentasOut);
    let patInc = false;
    order.forEach((yr) => {
      const dd = byYear.get(yr).data;
      const tot = num(dd.capital) + num(dd.reservas) + num(dd.ori) + num(dd.resAcum);
      if (tot > 0 && num(dd.capital) === 0 && num(dd.reservas) === 0) patInc = true;
    });
    const hasESF = order.some((yr) => {
      const dd = byYear.get(yr).data;
      return num(dd.efectivo) || num(dd.ppe) || num(dd.capital) || num(dd.resAcum) || num(dd.cxp);
    });
    const hasER = order.some((yr) => {
      const dd = byYear.get(yr).data;
      return num(dd.ventas) || num(dd.costo) || num(dd.gAdmin);
    });
    return { count: order.length, patInc, hasESF, hasER };
  };

  const esXlsx = (f) => /\.(xlsx|xls)$/i.test(f.name);

  // Selección de archivos: ACUMULA en vez de reemplazar. El usuario puede subir
  // el Balance (ESF) y el Estado de Resultados (ER) en clics separados —tal como
  // promete el texto de ayuda— sin que el segundo borre al primero. Se deduplica
  // por nombre+tamaño y se limpia el value del input para poder re-seleccionar el
  // mismo archivo y que onChange vuelva a dispararse.
  const onElegirArchivos = (e) => {
    const nuevos = [...(e.target.files || [])];
    e.target.value = "";
    if (!nuevos.length) return;
    setFiles((prev) => {
      const merged = [...prev];
      for (const f of nuevos) {
        if (!merged.some((g) => g.name === f.name && g.size === f.size)) merged.push(f);
      }
      return merged;
    });
    setIngMsg(null);
  };
  const quitarArchivo = (idx) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  const procesar = async () => {
    if (!files.length || !fuente) return;
    setIngBusy(true);
    setIngMsg(null);
    const warns = new Set();
    const noSoportados = [];
    let procesados = 0;
    let periodosCargados = 0;
    let patIncompleto = false;
    const num = (v) => (v == null ? 0 : (+v || 0));
    const mesesDefault = PERIODO_MESES[periodoTipo] || 12;
    try {
      if (fuente === "f101") {
        for (let i = 0; i < files.length; i++) {
          const res = await extractTaxPlan("f101", files[i]);
          cargarFijos3(res.data, res.params?.empresa);
          procesados++;
          (res.warnings || []).forEach((w) => warns.add(w));
        }
        setCuentas([]); // F-101 no trae detalle por cuenta
        setCmpResults([]); // F-101 no expone comparaciones período-a-período
      } else {
        // Internos / auditados: procesa TODOS los archivos y los fusiona por año
        // (Balance + Estado de Resultados separados → un período por año).
        const results = [];
        for (let i = 0; i < files.length; i++) {
          const f = files[i];
          if (!esXlsx(f)) { noSoportados.push(f.name); continue; }
          const res = await extractTaxPlan("interno", f);
          results.push({ res, name: f.name });
          (res.warnings || []).forEach((w) => warns.add(w));
        }
        if (results.length) {
          const r = cargarInternos(results, mesesDefault);
          setCmpResults(results.map((x) => x.res)); // crudo, para Comparaciones
          procesados = results.length;
          periodosCargados = r.count;
          patIncompleto = r.patInc;
          // Si al unir los archivos quedó el ESF y el ER completos, los avisos
          // "solo se cargó balance / solo resultados" ya no aplican.
          if (r.hasESF && r.hasER) {
            [...warns].forEach((w) => {
              if (/no se encontr/i.test(w)) warns.delete(w);
            });
          }
        }
      }
      if (noSoportados.length) {
        warns.add(
          "Extractor para PDF/Word de balances en construcción (próxima fase). " +
            "Por ahora súbelos en Excel. Sin procesar: " + noSoportados.join(", ")
        );
      }
      setIngMsg({
        ok: procesados > 0,
        prorrateoPreg: procesados > 0 && fuente !== "f101" && mesesDefault !== 12,
        patrimonioIncompleto: patIncompleto,
        text: procesados
          ? (fuente === "f101"
              ? `${procesados} Formulario(s) 101 cargado(s).`
              : `${procesados} archivo(s) fusionado(s) en ${periodosCargados} período(s) ${periodoTipo} (Balance + Estado de Resultados por año).`)
          : "Ningún archivo pudo procesarse con esta fuente.",
        warns: [...warns],
      });
      if (procesados) { setFiles([]); setSection("periodos"); }
    } catch (e) {
      setIngMsg({ warn: true, text: e.message });
    } finally {
      setIngBusy(false);
    }
  };

  const cargarEjemplo = () => {
    setPeriodos(initPeriodos());
    setD(clone(EX));
    setCuentas([]); // el ejemplo no trae detalle por cuenta
    setCmpResults([]);
    setHeader({ ...DEFAULT_HEADER, empresa: DEFAULT_PARAMS.empresa + " (ejemplo)" });
    setIngMsg({ ok: true, text: "Datos de ejemplo cargados (SIGMANSERVICES, 3 años)." });
  };

  const limpiar = () => {
    if (!window.confirm("¿Limpiar todos los datos y empezar de nuevo?")) return;
    setPeriodos([]);
    setD(emptyD(0));
    setCuentas([]);
    setCmpResults([]);
    setHeader({ ...DEFAULT_HEADER, empresa: "" });
    setDetalle(clone(EMPTY_DETALLE));
    setIngMsg(null);
  };

  /* ---------- gestor de períodos ---------- */
  const setPeriodo = (i, field, val) =>
    setPeriodos((prev) => prev.map((p, j) => (j === i ? { ...p, [field]: val } : p)));
  const delPeriodo = (i) => {
    setPeriodos((prev) => prev.filter((_, j) => j !== i));
    setD((prev) => {
      const next = {};
      Object.keys(prev).forEach((k) => (next[k] = prev[k].filter((_, j) => j !== i)));
      return next;
    });
    setDetalle((d) => ({ ...d, gastos: d.gastos.map((r) => ({ ...r, v: r.v.filter((_, j) => j !== i) })) }));
  };

  /* ---------- detalle CFO ---------- */
  const addRow = (k) => {
    const base = k === "gastos" ? { concepto: "", v: labels.map(() => 0) } : BLANK_ROW[k]();
    setDetalle((d) => ({ ...d, [k]: [...d[k], base] }));
  };
  const delRow = (k, idx) => setDetalle((d) => ({ ...d, [k]: d[k].filter((_, i) => i !== idx) }));
  const setRow = (k, idx, field, val) =>
    setDetalle((d) => ({ ...d, [k]: d[k].map((r, i) => (i === idx ? { ...r, [field]: val } : r)) }));
  const setRowYear = (k, idx, c, val) =>
    setDetalle((d) => ({
      ...d,
      [k]: d[k].map((r, i) =>
        i === idx ? { ...r, v: (r.v || []).map((x, j) => (j === c ? parseFloat(val) || 0 : x)) } : r
      ),
    }));

  /* ---------- export / derivados ---------- */
  const dashHTML = useMemo(
    () => buildStandaloneHTML({ D: Dnorm, header: { ...header, chart: chartStyle }, detalle, nivel, periodos, cuentas }),
    [Dnorm, header, detalle, nivel, periodos, chartStyle, cuentas]
  );
  const balCheck = useMemo(
    () => (periodos.length ? checkBalance(mapToDashboard(D, labels), labels) : []),
    [D, labels, periodos.length]
  );
  const proy = useMemo(
    () => (todosAnuales && periodos.length ? projectFinancials(D, DEFAULT_CTRL, params) : null),
    [D, params, todosAnuales, periodos.length]
  );

  const descargarHTML = () => downloadStandaloneHTML({ D: Dnorm, header: { ...header, chart: chartStyle }, detalle, nivel, periodos, cuentas });
  const [busyXl, setBusyXl] = useState(false);
  const [busyDoc, setBusyDoc] = useState(""); // "" | "pdf" | "word" | "ppt"
  const descargarExcelGrafico = async () => {
    if (!periodos.length) { alert("Carga al menos un período primero."); return; }
    setBusyXl(true);
    try {
      await exportDashboardExcel({ D: Dnorm, periodos, header, detalle, nivel, chartStyle });
    } catch (e) {
      alert("Error al exportar el Excel con gráfico: " + e.message);
    } finally { setBusyXl(false); }
  };
  const descargarDoc = async (tipo) => {
    if (!periodos.length) { alert("Carga al menos un período primero."); return; }
    setBusyDoc(tipo);
    const args = { D: Dnorm, periodos, header, detalle, nivel, chartStyle };
    try {
      if (tipo === "pdf") await exportDashboardPDF(args);
      else if (tipo === "word") await exportDashboardWord(args);
      else if (tipo === "ppt") await exportDashboardPPTX(args);
    } catch (e) {
      alert("Error al exportar " + tipo.toUpperCase() + ": " + e.message);
    } finally { setBusyDoc(""); }
  };
  const descargarExcel = async () => {
    setBusyX(true);
    try {
      await exportTaxPlan({ data: D, ctrl: DEFAULT_CTRL, params: { ...params, empresa: header.empresa } });
    } catch (e) { alert("Error al exportar a Excel: " + e.message); }
    finally { setBusyX(false); }
  };
  const descargarPptx = async () => {
    setBusyP(true);
    try {
      await generarPresentacionTax({ content: { empresa: header.empresa, ruc: params.ruc, fecha_analisis: header.subtitulo } });
    } catch (e) { alert("Error al generar el informe gerencial: " + e.message); }
    finally { setBusyP(false); }
  };

  /* ===================== RENDER ===================== */
  return (
    <div className="tax-root">
      {/* TOPBAR */}
      <div className="tx-tb no-print">
        <input className="tx-empresa" type="text" placeholder="Empresa" value={header.empresa}
          onChange={(e) => setHeader((h) => ({ ...h, empresa: e.target.value }))} />
        <div className="tx-scbtns">
          <ChartSelectorModal onChartSelected={aplicarChartSkill051} />
          <button className="tx-btn" onClick={descargarHTML}>⬇ Dashboard HTML</button>
          <button className="tx-btn" onClick={descargarExcelGrafico} disabled={busyXl}>{busyXl ? "Generando…" : "⬇ Excel + gráfico"}</button>
          <button className="tx-btn" onClick={() => descargarDoc("pdf")} disabled={!!busyDoc}>{busyDoc === "pdf" ? "Generando…" : "⬇ PDF"}</button>
          <button className="tx-btn" onClick={() => descargarDoc("word")} disabled={!!busyDoc}>{busyDoc === "word" ? "Generando…" : "⬇ Word"}</button>
          <button className="tx-btn" onClick={() => descargarDoc("ppt")} disabled={!!busyDoc}>{busyDoc === "ppt" ? "Generando…" : "⬇ PPT"}</button>
          <button className="tx-btn" onClick={descargarExcel} disabled={busyX}>{busyX ? "Generando…" : "⬇ Excel (fórmulas)"}</button>
          <button className="tx-btn gold" onClick={descargarPptx} disabled={busyP}>{busyP ? "Generando…" : "🎨 Informe gerencial"}</button>
          <button className="tx-btn light" onClick={cargarEjemplo}>↺ Ejemplo</button>
          <button className="tx-btn" onClick={limpiar}>🗑 Limpiar</button>
        </div>
      </div>

      {/* NAV PILLS */}
      <div className="tx-nav no-print">
        {SECTIONS.map(([id, n, label]) => (
          <button key={id} className={`tx-pill ${section === id ? "on" : ""}`} onClick={() => setSection(id)}>
            <span className="tx-pn">{n}</span>{label}
          </button>
        ))}
      </div>

      {/* ===== INGESTA ===== */}
      {section === "ingesta" && (
        <div className="tx-card">
          <h3>Fase 1 · Análisis de estados financieros</h3>
          <p className="tx-muted">
            Elige la <b>duración de cada período</b> y la <b>fuente de información</b>. El análisis es
            <b> multi-período</b>: comparas tantos años como traigan tus archivos (ej. 3 años = 3 columnas comparables).
          </p>

          {/* Duración de cada período (la cantidad de años se detecta de los archivos) */}
          <div style={{ marginTop: 6 }}>
            <div className="tx-muted" style={{ fontWeight: 600, marginBottom: 6 }}>
              🗓 Duración de cada período <span style={{ fontWeight: 400 }}>— comparas varios años automáticamente (1 por cada año/corte de tus archivos)</span>
            </div>
            <div className="tx-ingest-actions">
              {[["anual", "Anual · 1 año (12m)"], ["semestral", "Semestral (6m)"], ["trimestral", "Trimestral (3m)"], ["mensual", "Mensual (1m)"]].map(([id, lbl]) => (
                <button key={id} className={`tx-btn ${periodoTipo === id ? "" : "ghost"}`} onClick={() => setPeriodoTipo(id)}>
                  {periodoTipo === id ? "● " : ""}{lbl}
                </button>
              ))}
            </div>
            <div className="tx-muted small" style={{ marginTop: 6 }}>
              Ej.: 3 balances anuales (2023, 2024, 2025) → 3 períodos comparativos. No necesitas elegir "cuántos años": se detectan solos.
            </div>
          </div>

          {/* Fuente de información */}
          <div style={{ marginTop: 14 }}>
            <div className="tx-muted" style={{ fontWeight: 600, marginBottom: 6 }}>📥 Fuente de información</div>
            <div className="tx-ingest-actions">
              {[
                ["f101", "Formulario 101", "PDF · SRI (reemplaza por 3 años)"],
                ["internos", "Balances internos", "Excel (.xls/.xlsx) — se agregan como períodos"],
                ["auditados", "Balances auditados", "Excel (.xls/.xlsx) — se agregan como períodos"],
              ].map(([id, lbl, hint]) => (
                <button key={id} className={`tx-btn ${fuente === id ? "" : "ghost"}`}
                  onClick={() => { setFuente(id); setFiles([]); setIngMsg(null); }} title={hint}>
                  {fuente === id ? "● " : ""}{lbl}
                </button>
              ))}
            </div>
            {!fuente && (
              <div className="tx-muted small" style={{ marginTop: 8 }}>
                ① Elige una fuente para subir tus archivos y habilitar el botón <b>Procesar</b>.
              </div>
            )}
          </div>

          {fuente && (
            <div className="tx-ingest" style={{ marginTop: 12 }}>
              <p className="tx-muted">
                {fuente === "f101"
                  ? "Sube uno o varios PDF del Formulario 101 (reemplaza el análisis por 3 años anuales)."
                  : `Sube los ${fuente === "internos" ? "balances internos" : "balances auditados"} en Excel. Puedes seleccionar VARIOS archivos a la vez — por ejemplo el Balance (ESF) y el Estado de Resultados (ER) por separado: se fusionan por año en un período ${periodoTipo}.`}
              </p>
              {fuente !== "f101" && (
                <button className="tx-btn ghost" onClick={() => downloadTaxPlantilla().catch((e) => alert(e.message))}>⬇ Descargar plantilla Excel</button>
              )}
              <input type="file" multiple
                accept={fuente === "f101" ? "application/pdf" : ".xlsx,.xls,.pdf,.doc,.docx"}
                onChange={onElegirArchivos} />
              {files.length > 0 && (
                <div className="tx-muted small" style={{ marginTop: 6 }}>
                  <div style={{ marginBottom: 4 }}>
                    <b>Seleccionado(s) ({files.length})</b> — puedes seguir agregando más (se acumulan).
                    {" "}<a href="#" onClick={(e) => { e.preventDefault(); setFiles([]); }} style={{ color: "var(--tx-link, #b58900)" }}>Limpiar selección</a>
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {files.map((f, i) => (
                      <li key={`${f.name}-${i}`}>
                        {f.name}{" "}
                        <a href="#" onClick={(e) => { e.preventDefault(); quitarArchivo(i); }} title="Quitar este archivo" style={{ color: "#c0392b" }}>✕</a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="tx-ingest-actions" style={{ marginTop: 10, alignItems: "center" }}>
                <button className="tx-btn" onClick={procesar} disabled={!files.length || ingBusy}
                  style={{ fontWeight: 700, fontSize: 15, padding: "10px 20px" }}>
                  {ingBusy ? "Procesando…" : "▶ Procesar y generar dashboard"}
                </button>
                {!files.length && !ingBusy && (
                  <span className="tx-muted small">② Sube al menos un archivo para habilitar este botón.</span>
                )}
              </div>
            </div>
          )}

          {ingMsg && (
            <div className={`tx-note ${ingMsg.ok ? "n-ok" : "n-warn"}`}>
              <span className="ic">{ingMsg.ok ? "✓" : "⚠"}</span>
              <div>
                {ingMsg.text}
                {ingMsg.prorrateoPreg && (
                  <div style={{ marginTop: 4 }}>
                    ¿Tu Estado de Resultados ya está a <b>{periodoTipo}</b>, o lo proyectamos prorrateando
                    desde el anual? Ajústalo en la pestaña <b>Períodos</b> (columna "meses ER" y casilla "prorratear").
                  </div>
                )}
                {ingMsg.warns?.length > 0 && (
                  <ul className="tx-warnlist">{ingMsg.warns.map((w, i) => <li key={i}>{w}</li>)}</ul>
                )}
              </div>
            </div>
          )}

          <div className="tx-grid g3" style={{ marginTop: 16 }}>
            <label className="tx-fld"><span>Empresa</span>
              <input className="tx-cin" value={header.empresa} onChange={(e) => setHeader((h) => ({ ...h, empresa: e.target.value }))} /></label>
            <label className="tx-fld"><span>Subtítulo</span>
              <input className="tx-cin" value={header.subtitulo} onChange={(e) => setHeader((h) => ({ ...h, subtitulo: e.target.value }))} /></label>
            <label className="tx-fld"><span>Pie de página</span>
              <input className="tx-cin" value={header.pie} onChange={(e) => setHeader((h) => ({ ...h, pie: e.target.value }))} /></label>
          </div>
        </div>
      )}

      {/* ===== PERÍODOS ===== */}
      {section === "periodos" && (
        <div className="tx-card">
          <h3>Períodos a comparar</h3>
          <p className="tx-muted">
            Cada fila es un período. El <b>balance (ESF) se compara directo</b> (saldos acumulados) y
            puede tener <b>fechas distintas al Estado de Resultados</b> (ej. ESF 31-12-2024 vs 30-09-2025;
            ER 30-09-2024 vs 30-09-2025). El <b>ER se prorratea</b> a la base común ({baseMeses} meses) si "prorratear" está activo.
          </p>
          {periodos.length === 0 ? (
            <div className="tx-note n-warn"><span className="ic">⚠</span><div>No hay períodos. Carga información desde "Datos e ingesta" o pulsa "↺ Ejemplo".</div></div>
          ) : (
            <table className="tx-tbl">
              <thead><tr><th>Etiqueta ER</th><th>Etiqueta Balance (ESF)</th><th>Meses ER</th><th>Prorratear ER</th><th></th></tr></thead>
              <tbody>
                {periodos.map((p, i) => (
                  <tr key={p.id}>
                    <td style={{ textAlign: "left" }}>
                      <input className="tx-cin" value={p.label} onChange={(e) => setPeriodo(i, "label", e.target.value)} style={{ width: 140 }} /></td>
                    <td style={{ textAlign: "left" }}>
                      <input className="tx-cin" value={p.labelESF || ""} onChange={(e) => setPeriodo(i, "labelESF", e.target.value)} style={{ width: 140 }} /></td>
                    <td>
                      <input className="tx-cin" type="number" value={p.meses}
                        onChange={(e) => setPeriodo(i, "meses", parseInt(e.target.value, 10) || 0)} style={{ width: 70, textAlign: "center" }} /></td>
                    <td style={{ textAlign: "center" }}>
                      <input type="checkbox" checked={!!p.normalizar} onChange={(e) => setPeriodo(i, "normalizar", e.target.checked)} /></td>
                    <td><button className="tx-btn ghost" onClick={() => delPeriodo(i)}>✕</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {hayProrrateo && (
            <div className="tx-note n-info" style={{ marginTop: 10 }}>
              <span className="ic">ℹ</span>
              <div>El Estado de Resultados de los períodos más largos se prorratea a {baseMeses} meses
                (÷meses×{baseMeses}). <b>Prorrateo lineal, no ajustado por estacionalidad.</b></div>
            </div>
          )}
        </div>
      )}

      {/* ===== ESTADOS FINANCIEROS ===== */}
      {section === "eeff" && (
        <div className="tx-card">
          <h3>Estados financieros (editable)</h3>
          <p className="tx-muted">Ajusta las celdas. Los totales se recalculan solos. Columnas = períodos.</p>
          {periodos.length === 0 ? <div className="tx-muted">Sin períodos cargados.</div> : (
            <>
              <EeffEditor schema={ESF_SCHEMA} title="Estado de Situación Financiera" D={D} labels={labels} setCell={setCell} />
              <EeffEditor schema={ER_SCHEMA} title="Estado de Resultados (valores cargados)" D={D} labels={labels} setCell={setCell} />
            </>
          )}
        </div>
      )}

      {/* ===== COMPARACIONES ===== */}
      {section === "comparaciones" && (
        <div className="tx-card">
          <h3>Comparaciones período a período</h3>
          <p className="tx-muted">
            <b>Balance (ESF):</b> cada período vs. el inmediatamente anterior (may-26 vs 2025, 2025 vs 2024…).
            {" "}<b>Resultados (ERI):</b> parcial vs. parcial del mismo corte del año previo (may-26 vs may-25) y anual vs. anual.
            {" "}Nunca se cruza un corte parcial (p. ej. 5 meses) con uno anual (12 meses).
          </p>
          <ComparacionesPanel results={cmpResults} />
        </div>
      )}

      {/* ===== DETALLE CFO ===== */}
      {section === "detalle" && (
        <div>
          <DetalleGastos detalle={detalle} labels={labels} addRow={addRow} delRow={delRow} setRow={setRow} setRowYear={setRowYear} />
          <DetalleAtipicos detalle={detalle} addRow={addRow} delRow={delRow} setRow={setRow} />
          <DetalleActivos detalle={detalle} addRow={addRow} delRow={delRow} setRow={setRow} />
          <DetalleInversiones detalle={detalle} addRow={addRow} delRow={delRow} setRow={setRow} />
        </div>
      )}

      {/* ===== PROYECCIÓN 3 ESTADOS ===== */}
      {section === "proyeccion" && (
        <div className="tx-card">
          <h3>Proyección automática · 3 estados {PROJ[0]}–{PROJ[PROJ.length - 1]}</h3>
          {!proy ? (
            <div className="tx-note n-warn"><span className="ic">⚠</span>
              <div>La proyección a 3 estados solo aplica cuando todos los períodos son <b>años completos (12 meses)</b>.
                Para comparaciones de cortes parciales usa el análisis de variaciones del dashboard.</div></div>
          ) : (
            <>
              <p className="tx-muted">
                Supuestos derivados del histórico (crecimiento {proy.assumptions.growth}% · costo {proy.assumptions.costoR}% ·
                gastos {proy.assumptions.gastoR}% · cartera {proy.assumptions.diasCxC}d · inventario {proy.assumptions.diasInv}d).
              </p>
              <table className="tx-tbl">
                <thead><tr><th>Cuenta</th>{PROJ.map((y) => <th key={y}>{y}</th>)}</tr></thead>
                <tbody>
                  {[
                    ["Ventas", "ventas"], ["Costo", "costo"], ["Utilidad bruta", "ub"],
                    ["EBIT", "ebit"], ["EBITDA", "ebitda"], ["Utilidad neta", "neta"],
                    ["— Flujo operativo (FCO)", "fco"], ["— Flujo inversión (FCI)", "fci"],
                    ["— Flujo financiero (FCF)", "fcf"], ["Δ Caja", "deltaCaja"],
                    ["Total activo", "totalActivo"], ["Total pasivo", "totalPasivo"],
                    ["Patrimonio", "patrimonio"], ["Cuadre (A−P−Pat)", "cuadre"],
                  ].map(([lbl, k]) => (
                    <tr key={k} className={["ub", "ebit", "neta", "totalActivo", "patrimonio"].includes(k) ? "bold" : ""}>
                      <td style={{ textAlign: "left" }}>{lbl}</td>
                      {proy.rows.map((r, i) => <td key={i}>{m(r[k])}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {/* ===== DASHBOARD (vista previa) ===== */}
      {section === "preview" && (
        <div className="tx-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            <h3 style={{ margin: 0 }}>Dashboard ejecutivo · vista previa</h3>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <span className="tx-muted small">Nivel de detalle:</span>
              {[["resumido", "Resumido"], ["detallado", "Detallado"]].map(([id, lbl]) => (
                <button key={id} className={`tx-btn ${nivel === id ? "" : "ghost"}`} onClick={() => setNivel(id)}>{lbl}</button>
              ))}
              <button className="tx-btn" onClick={descargarHTML}>⬇ Descargar dashboard (HTML)</button>
            </div>
          </div>
          {periodos.length === 0 ? (
            <div className="tx-note n-warn"><span className="ic">⚠</span><div>Carga al menos un período para ver el dashboard.</div></div>
          ) : (
            <>
              <BalanceBanner balCheck={balCheck} />
              {hayProrrateo && (
                <div className="tx-note n-info" style={{ marginTop: 8 }}><span className="ic">ℹ</span>
                  <div>Estado de Resultados prorrateado a {baseMeses} meses (no ajustado por estacionalidad). Balance sin ajuste.</div></div>
              )}
              <iframe title="Dashboard ejecutivo" srcDoc={dashHTML}
                style={{ width: "100%", height: "78vh", border: "1px solid rgba(13,115,119,.3)", borderRadius: 8, marginTop: 10, background: "#071B2F" }} />
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* ===================== sub-componentes ===================== */

function EeffEditor({ schema, title, D, labels, setCell }) {
  return (
    <div style={{ marginTop: 14 }}>
      <div className="tx-muted" style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>
      <table className="tx-tbl">
        <thead><tr><th>Cuenta</th>{labels.map((y, i) => <th key={i}>{y}</th>)}</tr></thead>
        <tbody>
          {schema.map((sp, idx) => {
            if (sp[0] === "sec")
              return <tr key={idx} className="bold"><td colSpan={labels.length + 1} style={{ textAlign: "left" }}>{sp[1]}</td></tr>;
            if (sp[0] === "in")
              return (
                <tr key={idx}>
                  <td style={{ textAlign: "left", paddingLeft: 18 }}>{sp[2]}</td>
                  {labels.map((y, c) => (
                    <td key={c}>
                      <input className="tx-cin" type="number" value={D[sp[1]] ? D[sp[1]][c] : 0}
                        onChange={(e) => setCell(sp[1], c, e.target.value)} style={{ width: 110, textAlign: "right" }} /></td>
                  ))}
                </tr>
              );
            return (
              <tr key={idx} className="bold">
                <td style={{ textAlign: "left" }}>{sp[2]}</td>
                {labels.map((y, c) => <td key={c}>{f0(calcLine(D, sp, c))}</td>)}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SecTabla({ title, sub, children }) {
  return (
    <div className="tx-card">
      <h3 style={{ marginBottom: 2 }}>{title}</h3>
      <p className="tx-muted" style={{ marginTop: 0 }}>{sub}</p>
      {children}
    </div>
  );
}

function DetalleGastos({ detalle, labels, addRow, delRow, setRow, setRowYear }) {
  return (
    <SecTabla title="Principales gastos" sub="Concepto y evolución por período. Se grafica en el dashboard.">
      <table className="tx-tbl">
        <thead><tr><th>Concepto</th>{labels.map((y, i) => <th key={i}>{y}</th>)}<th></th></tr></thead>
        <tbody>
          {detalle.gastos.map((r, i) => (
            <tr key={i}>
              <td style={{ textAlign: "left" }}>
                <input className="tx-cin" value={r.concepto} placeholder="Ej. Nómina"
                  onChange={(e) => setRow("gastos", i, "concepto", e.target.value)} style={{ width: 220 }} /></td>
              {labels.map((y, c) => (
                <td key={c}>
                  <input className="tx-cin" type="number" value={(r.v && r.v[c]) || 0}
                    onChange={(e) => setRowYear("gastos", i, c, e.target.value)} style={{ width: 100, textAlign: "right" }} /></td>
              ))}
              <td><button className="tx-btn ghost" onClick={() => delRow("gastos", i)}>✕</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="tx-btn ghost" onClick={() => addRow("gastos")} style={{ marginTop: 8 }}>+ Agregar gasto</button>
    </SecTabla>
  );
}

function DetalleAtipicos({ detalle, addRow, delRow, setRow }) {
  return (
    <SecTabla title="Gastos atípicos" sub="Partidas no recurrentes / extraordinarias que distorsionan la tendencia.">
      <table className="tx-tbl">
        <thead><tr><th>Concepto</th><th>Año</th><th>Monto</th><th>Justificación</th><th></th></tr></thead>
        <tbody>
          {detalle.atipicos.map((r, i) => (
            <tr key={i}>
              <td style={{ textAlign: "left" }}><input className="tx-cin" value={r.concepto} onChange={(e) => setRow("atipicos", i, "concepto", e.target.value)} style={{ width: 200 }} /></td>
              <td><input className="tx-cin" type="number" value={r.anio} onChange={(e) => setRow("atipicos", i, "anio", e.target.value)} style={{ width: 80, textAlign: "center" }} /></td>
              <td><input className="tx-cin" type="number" value={r.monto} onChange={(e) => setRow("atipicos", i, "monto", e.target.value)} style={{ width: 110, textAlign: "right" }} /></td>
              <td style={{ textAlign: "left" }}><input className="tx-cin" value={r.just} onChange={(e) => setRow("atipicos", i, "just", e.target.value)} style={{ width: 240 }} /></td>
              <td><button className="tx-btn ghost" onClick={() => delRow("atipicos", i)}>✕</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="tx-btn ghost" onClick={() => addRow("atipicos")} style={{ marginTop: 8 }}>+ Agregar gasto atípico</button>
    </SecTabla>
  );
}

function DetalleActivos({ detalle, addRow, delRow, setRow }) {
  return (
    <SecTabla title="Activos fijos adquiridos (últimos 3 años)" sub="Altas de propiedad, planta y equipo. Base de CAPEX y depreciación.">
      <table className="tx-tbl">
        <thead><tr><th>Descripción</th><th>Categoría</th><th>Año</th><th>Monto</th><th></th></tr></thead>
        <tbody>
          {detalle.activos.map((r, i) => (
            <tr key={i}>
              <td style={{ textAlign: "left" }}><input className="tx-cin" value={r.desc} onChange={(e) => setRow("activos", i, "desc", e.target.value)} style={{ width: 200 }} /></td>
              <td style={{ textAlign: "left" }}><input className="tx-cin" value={r.categoria} placeholder="Ej. Maquinaria" onChange={(e) => setRow("activos", i, "categoria", e.target.value)} style={{ width: 150 }} /></td>
              <td><input className="tx-cin" type="number" value={r.anio} onChange={(e) => setRow("activos", i, "anio", e.target.value)} style={{ width: 80, textAlign: "center" }} /></td>
              <td><input className="tx-cin" type="number" value={r.monto} onChange={(e) => setRow("activos", i, "monto", e.target.value)} style={{ width: 110, textAlign: "right" }} /></td>
              <td><button className="tx-btn ghost" onClick={() => delRow("activos", i)}>✕</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="tx-btn ghost" onClick={() => addRow("activos")} style={{ marginTop: 8 }}>+ Agregar activo</button>
    </SecTabla>
  );
}

function DetalleInversiones({ detalle, addRow, delRow, setRow }) {
  return (
    <SecTabla title="Estado de inversiones" sub="Portafolio de instrumentos financieros y su rendimiento.">
      <table className="tx-tbl">
        <thead><tr><th>Instrumento</th><th>Año</th><th>Monto</th><th>Rendimiento %</th><th></th></tr></thead>
        <tbody>
          {detalle.inversiones.map((r, i) => (
            <tr key={i}>
              <td style={{ textAlign: "left" }}><input className="tx-cin" value={r.instrumento} onChange={(e) => setRow("inversiones", i, "instrumento", e.target.value)} style={{ width: 220 }} /></td>
              <td><input className="tx-cin" type="number" value={r.anio} onChange={(e) => setRow("inversiones", i, "anio", e.target.value)} style={{ width: 80, textAlign: "center" }} /></td>
              <td><input className="tx-cin" type="number" value={r.monto} onChange={(e) => setRow("inversiones", i, "monto", e.target.value)} style={{ width: 110, textAlign: "right" }} /></td>
              <td><input className="tx-cin" type="number" value={r.rendimiento} onChange={(e) => setRow("inversiones", i, "rendimiento", e.target.value)} style={{ width: 100, textAlign: "right" }} /></td>
              <td><button className="tx-btn ghost" onClick={() => delRow("inversiones", i)}>✕</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="tx-btn ghost" onClick={() => addRow("inversiones")} style={{ marginTop: 8 }}>+ Agregar inversión</button>
    </SecTabla>
  );
}

function BalanceBanner({ balCheck }) {
  const ok = balCheck.length > 0 && balCheck.every((b) => Math.abs(b.dif) < 2); // <2 absorbe redondeo por línea
  return (
    <div className={`tx-note ${ok ? "n-ok" : "n-warn"}`} style={{ marginTop: 10 }}>
      <span className="ic">{ok ? "✓" : "⚠"}</span>
      <div>
        {ok
          ? <>Ecuación contable <b>A = Pasivo + Patrimonio</b> cuadra en los {balCheck.length} período(s).</>
          : <>Hay descuadres: {balCheck.filter((b) => Math.abs(b.dif) >= 2).map((b) => `${b.anio}: ${fmt(b.dif)}`).join(" · ")}.</>}
      </div>
    </div>
  );
}

/* ---------- Comparaciones período a período (usa el crudo del backend) ---------- */
function ComparacionesPanel({ results }) {
  const tieneEsf = (r) => r && r.comparaciones && (r.comparaciones.esf || []).length && (r.labels_esf || []).length;
  const tieneEri = (r) => r && r.comparaciones && (r.comparaciones.eri || []).length && (r.labels_er || []).length;
  const esfRes = (results || []).find(tieneEsf);
  const eriRes = (results || []).find(tieneEri);
  if (!esfRes && !eriRes) {
    return (
      <div className="tx-note n-info">
        <span className="ic">ℹ</span>
        <div>
          Las comparaciones aparecen aquí al procesar un estado financiero <b>resumido por nombre</b>
          {" "}(ESF/ERI con columnas de período). Procesa un archivo en <b>Datos e ingesta</b>.
        </div>
      </div>
    );
  }
  return (
    <>
      {esfRes && (
        <CmpTabla titulo="Balance general (ESF · saldos por corte)"
          data={esfRes.data} labels={esfRes.labels_esf} pares={esfRes.comparaciones.esf}
          periodos={esfRes.periodos_esf} schema={ESF_SCHEMA} />
      )}
      {eriRes && (
        <CmpTabla titulo="Estado de resultados (ERI · flujo del período)"
          data={eriRes.data} labels={eriRes.labels_er}
          pares={construirParesEri(eriRes.periodos_eri)}
          periodos={eriRes.periodos_eri} schema={ER_SCHEMA} />
      )}
    </>
  );
}

function CmpTabla({ titulo, data, labels, pares, periodos, schema }) {
  const rubros = schema.filter((sp) => sp[0] === "in").map((sp) => [sp[1], sp[2]]);
  const filas = comparacionFilas(data || {}, labels || [], pares || [], rubros);
  const tipoDe = (lab) => {
    const p = (periodos || []).find((x) => x.label === lab);
    return p && p.tipo === "parcial" ? " · parcial" : "";
  };
  if (!filas.length) return null;
  return (
    <div style={{ marginTop: 16 }}>
      <div className="tx-muted" style={{ fontWeight: 600, marginBottom: 6 }}>
        {titulo}
        <span style={{ fontWeight: 400 }}>
          {" — "}{(labels || []).map((l) => `${l}${tipoDe(l)}`).join(" · ")}
        </span>
      </div>
      <table className="tx-tbl">
        <thead>
          <tr>
            <th>Concepto</th>
            {pares.map((par, i) => <th key={i}>{par[3] || `Δ ${par[0]} vs ${par[1]}`}</th>)}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila) => (
            <tr key={fila.key}>
              <td style={{ textAlign: "left" }}>{fila.etiqueta}</td>
              {fila.celdas.map((c, i) => {
                if (c.delta == null) return <td key={i} style={{ textAlign: "right" }}>—</td>;
                const col = c.delta > 0 ? "#1D9E75" : c.delta < 0 ? "#E24B4A" : "inherit";
                return (
                  <td key={i} style={{ textAlign: "right", color: col }}>
                    {m(c.delta)}
                    {c.pct == null ? "" : ` (${c.pct > 0 ? "+" : ""}${c.pct.toFixed(1)}%)`}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
