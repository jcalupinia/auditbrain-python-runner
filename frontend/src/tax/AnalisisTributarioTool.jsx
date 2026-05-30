import { useMemo, useState, useEffect } from "react";
import {
  extractTaxPlan,
  exportTaxPlan,
  downloadTaxPlantilla,
  generarPresentacionTax,
  consultarSriRuc,
} from "../api.js";
import TaxChart from "./TaxChart.jsx";
import { fmt, f0, fX, fP, fD, m } from "./format.js";
import {
  ESF_SCHEMA,
  ER_SCHEMA,
  ANIOS,
  PROJ,
  EX,
  DEFAULT_CTRL,
  DEFAULT_PARAMS,
  emptyData,
} from "./seed.js";

// Parámetros en blanco (sin datos de la empresa de ejemplo). Mantiene las
// tasas normativas por defecto; el resto vacío para una empresa nueva.
const BLANK_PARAMS = {
  empresa: "",
  ruc: "",
  repLegal: "",
  fechaCorte: "",
  fechaAnalisis: "",
  costoR: 0,
  gastoR: 0,
  irR: 25,
  retDiv: 12,
  divObjetivo: 0,
  // Supuestos de proyección (se re-derivan del histórico al cargar datos).
  growth: 0,
  growthRaw: 0,
  diasCxC: 0,
  diasInv: 0,
  diasCxP: 0,
  deprecPctPPE: 10,
  capexPctVentas: 1,
  sector: "",
  tasaSectorial: 0,
  actividadSRI: "",
};
import {
  tarifa,
  tAC,
  tActivo,
  tPC,
  tPasivo,
  tPat,
  ub,
  ebit,
  uai,
  neta,
  ind,
  cce,
  computeModel,
  scenarioCompare,
  applyScenario,
  SCENARIO_NAMES,
  deriveAssumptions,
  projectFinancials,
  SECTORES_CIIU,
  sugerirSeccion,
  sectorPorCod,
  METODOLOGIA_PROYECCION,
} from "./engine.js";
import "./tax.css";

const SECTIONS = [
  ["datos", "i", "Datos del cliente"],
  ["legal", "§", "Base legal y normativa"],
  ["eeff", "1", "Estados financieros"],
  ["indices", "2", "Índices financieros"],
  ["impuesto", "3", "Cálculo del impuesto"],
  ["retenciones", "4", "Retenciones dividendos"],
  ["credito", "5", "Crédito vs. Renta"],
  ["proyectado", "6", "Estados proyectados"],
  ["dashboard", "7", "Dashboards"],
  ["informe", "★", "Informe gerencial"],
];

// Línea calculada de la ingesta (espejo de calcLine del original).
function calcLine(D, sp, c) {
  switch (sp[1]) {
    case "totalAC":
      return tAC(D, c);
    case "totalANC":
      return D.ppe[c] + D.actImpDif[c];
    case "totalActivo":
      return tActivo(D, c);
    case "totalPC":
      return tPC(D, c);
    case "totalPNC":
      return D.benefPost[c] + D.cxpRel[c] + D.pasImpDif[c];
    case "totalPasivo":
      return tPasivo(D, c);
    case "totalPat":
      return tPat(D, c);
    case "ub":
      return ub(D, c);
    case "ebit":
      return ebit(D, c);
    case "uai":
      return uai(D, c);
    case "neta":
      return neta(D, c);
    default:
      return 0;
  }
}

const clone = (o) => JSON.parse(JSON.stringify(o));

export default function AnalisisTributarioTool({ projectId }) {
  // Arranque en blanco (sin datos de la empresa de ejemplo). El botón
  // "Ejemplo" carga la empresa ficticia (EMPRESA IA S.A.) bajo demanda.
  const [D, setD] = useState(() => emptyData());
  const [CTRL, setCTRL] = useState(() => clone(DEFAULT_CTRL));
  const [scn, setScn] = useState("sin");
  const [params, setParams] = useState(() => ({ ...BLANK_PARAMS }));
  const [section, setSection] = useState("datos");
  const [ingest, setIngest] = useState(null); // null | "f101" | "resumido"

  // Supuestos de proyección AUTO-derivados del histórico (crecimiento, márgenes,
  // días de capital de trabajo, depreciación, CAPEX). Se recalculan al cambiar
  // los estados financieros; el usuario no los llena (editables como override).
  useEffect(() => {
    const A = deriveAssumptions(D);
    setParams((prev) => {
      // Crecimiento: histórico si crece; si no crece (≤0), tasa sectorial.
      const sect = Number(prev.tasaSectorial) || 0;
      const growth = A.growthRaw > 0 ? A.growth : sect > 0 ? sect : 0;
      return {
        ...prev,
        growth,
        growthRaw: A.growthRaw,
        costoR: A.costoR,
        gastoR: A.gastoR,
        diasCxC: A.diasCxC,
        diasInv: A.diasInv,
        diasCxP: A.diasCxP,
        deprecPctPPE: A.deprecPctPPE,
        capexPctVentas: A.capexPctVentas,
      };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [D, params.tasaSectorial]);

  // Derivados (recálculo en vivo).
  const R = useMemo(() => computeModel(D, CTRL, params), [D, CTRL, params]);
  const scComp = useMemo(
    () => scenarioCompare(D, CTRL, params),
    [D, CTRL, params],
  );
  const i0 = useMemo(() => ind(D, 0), [D]);
  const i1 = useMemo(() => ind(D, 1), [D]);
  const i2 = useMemo(() => ind(D, 2), [D]);

  const sumK = (k) => R.reduce((s, r) => s + r[k], 0);
  const P = (k) => R.map((r) => r[k]);

  // Mutadores inmutables.
  const setCell = (key, c, val) =>
    setD((prev) => ({
      ...prev,
      [key]: prev[key].map((v, i) => (i === c ? parseFloat(val) || 0 : v)),
    }));
  const setCtrlCell = (i, k, val) =>
    setCTRL((prev) =>
      prev.map((row, idx) =>
        idx === i ? { ...row, [k]: parseFloat(val) || 0 } : row,
      ),
    );
  const setParam = (k, val) =>
    setParams((prev) => ({ ...prev, [k]: parseFloat(val) || 0 }));
  const setText = (k, val) => setParams((prev) => ({ ...prev, [k]: val }));

  const applyScn = (s) => {
    setScn(s);
    setCTRL(applyScenario(s, D, CTRL, params));
  };

  const loadExample = () => {
    setD(clone(EX));
    setParams({ ...DEFAULT_PARAMS });
    setScn("mix");
    setCTRL(applyScenario("mix", EX, DEFAULT_CTRL, DEFAULT_PARAMS));
  };

  // Limpia TODO (cero datos de la empresa de ejemplo) para empezar con otra
  // empresa: estados financieros en 0, cabecera vacía, palancas por defecto.
  const limpiarTodo = () => {
    if (!window.confirm("¿Limpiar todos los datos y empezar una empresa nueva?"))
      return;
    setD(emptyData());
    setParams({ ...BLANK_PARAMS });
    setScn("sin");
    setCTRL(clone(DEFAULT_CTRL));
    setIngest(null);
    setSection("datos");
  };

  // Fusiona el resultado de la ingesta: solo valores no nulos sobre el estado.
  const mergeExtract = (res) => {
    if (res?.data) {
      setD((prev) => {
        const next = { ...prev };
        Object.entries(res.data).forEach(([k, arr]) => {
          if (!next[k] || !Array.isArray(arr)) return;
          next[k] = next[k].map((v, i) =>
            arr[i] !== null && arr[i] !== undefined ? arr[i] : v,
          );
        });
        return next;
      });
    }
    if (res?.params && Object.keys(res.params).length) {
      setParams((prev) => ({ ...prev, ...res.params }));
    }
  };

  const [busy, setBusy] = useState(false);
  const exportExcel = async () => {
    setBusy(true);
    try {
      await exportTaxPlan({ data: D, ctrl: CTRL, params });
    } catch (e) {
      alert("Error al exportar a Excel: " + e.message);
    } finally {
      setBusy(false);
    }
  };

  // ---- Presentación ejecutiva (.pptx) ----
  const [presBusy, setPresBusy] = useState(false);

  // Arma el contenido ejecutivo del deck con cifras en vivo.
  const buildDeckContent = () => {
    const pagoAct = R.reduce((a, r) => a + r.pago, 0);
    const credIR = R.reduce((a, r) => a + r.cIR, 0);
    const devol = R.reduce((a, r) => a + r.dev, 0);
    const recuperable = credIR + devol;
    const riesgo = R[R.length - 1].riesgo;
    const totalPat = D.capital[2] + D.reservas[2] + D.ori[2] + D.resAcum[2];
    const primero = computeModel(
      D,
      applyScenario("sin", D, CTRL, params),
      params,
    )[0];
    const esc = buildEscenarios(D, CTRL, params);
    const matriz = esc.map((m) => ({
      escenario: m.nombre,
      recomendado: m.key === "e3",
      pago_2026: Math.round(m.pago2026),
      pago_2026_2028: Math.round(m.pago),
      retencion_credito: Math.round(m.retencion),
      costo_muerto: Math.round(m.muerto),
      patrimonio_2028: Math.round(m.patrimonio),
    }));
    const hist = pagoHistorico(D, params).map((h) => ({
      anio: h.anio,
      base: Math.round(h.base),
      pago: Math.round(h.pago),
      estado: "Realizado",
    }));
    return {
      empresa: params.empresa || "la Compañía",
      ruc: params.ruc || "",
      representante: params.repLegal || "",
      fecha_analisis: fmtFecha(params.fechaAnalisis) || "",
      fecha_corte: fmtFecha(params.fechaCorte) || "",
      escenario_recomendado: SCENARIO_NAMES[scn],
      moneda: "USD",
      kpis: [
        { label: "Utilidades no distribuidas", valor: fmt(D.resAcum[2]) },
        { label: "Pago sin acción 2026–28", valor: fmt(scComp.sin) },
        { label: `Pago — ${SCENARIO_NAMES[scn]}`, valor: fmt(pagoAct) },
        { label: "Ahorro / diferimiento", valor: fmt(scComp.sin - pagoAct) },
        { label: "Crédito recuperable", valor: fmt(recuperable) },
        { label: "En riesgo (costo muerto)", valor: fmt(riesgo) },
      ],
      diagnostico_financiero: {
        liquidez: fX(i2.liq),
        endeudamiento: fP(i2.end),
        roe: fP(i2.roe),
        margen_neto: fP(i2.mn),
        dias_inventario: fD(i2.dInv),
        ciclo_efectivo: fD(cce(D, 2)),
      },
      diagnostico_tributario: {
        base_anio1: fmt(primero.base),
        tarifa: fP(primero.tar),
        pago_anio1: fmt(primero.pago),
        pago_horizonte: fmt(scComp.sin),
      },
      diagnostico_societario: {
        capital: fmt(D.capital[2]),
        reservas: fmt(D.reservas[2]),
        resultados_acumulados: fmt(D.resAcum[2]),
        patrimonio_total: fmt(totalPat),
      },
      alternativas: [
        "No hacer nada (se paga el anticipo cada año)",
        `Distribuir dividendos (retención ${params.retDiv}% recuperable)`,
        "Capitalizar con sustancia antes del 31 de julio",
        "Híbrido: distribución + capitalización",
      ],
      pago_historico: hist,
      matriz_escenarios: matriz,
      grafico_pago_por_escenario: {
        labels: matriz.map((m) => m.escenario),
        valores: matriz.map((m) => m.pago_2026_2028),
      },
      modelacion_2026_2028: {
        anios: PROJ,
        pago_a_cuenta: R.map((r) => Math.round(r.pago)),
        credito_vs_ir: R.map((r) => Math.round(r.cIR)),
        en_riesgo: R.map((r) => Math.round(r.enR)),
        patrimonio: R.map((r) => Math.round(r.patrimonio)),
      },
      metodologia_proyeccion: {
        intro:
          "Modelo de tres estados (2026–2028) construido automáticamente a " +
          "partir del histórico 2023–2025.",
        fuente_crecimiento:
          deriveAssumptions(D).growthRaw > 0
            ? `Histórico real (${deriveAssumptions(D).growthRaw}% promedio anual).`
            : `El histórico no crece; tasa sectorial referencial ${
                Number(params.tasaSectorial) || 0
              }%${params.sector ? ` (CIIU ${params.sector})` : ""}.`,
        pasos: METODOLOGIA_PROYECCION.map((m) => ({
          titulo: m.titulo,
          detalle: m.detalle,
        })),
      },
      plan_accion: [
        { accion: "Convocar Junta y aprobar la estrategia", responsable: "Representante legal", plazo: "Antes del 31 de julio" },
        { accion: "Formalizar aumento de capital (acta, escritura, Registro Mercantil)", responsable: "Asesor legal", plazo: "Antes del 31 de julio" },
        { accion: "Sustentar capitalización en activos productivos/empleo (no inventarios)", responsable: "Gerencia financiera", plazo: "Antes del corte" },
        { accion: "Aplicar el crédito en retención de dividendos e IR", responsable: "Tributario", plazo: "En la declaración" },
      ],
      recomendacion:
        `Bajo el escenario ${SCENARIO_NAMES[scn]}, el pago a cuenta 2026–2028 ` +
        `baja a ${fmt(pagoAct)} frente a ${fmt(scComp.sin)} sin actuar, con ` +
        `${fmt(recuperable)} recuperables. Perfeccionar la decisión antes del ` +
        `31 de julio con sustancia económica. Para ${params.empresa || "la Compañía"} ` +
        `evitar capitalizar vía inventarios.`,
      nota: "Parámetros normativos editables, sujetos a validación humana y a criterios del SRI.",
    };
  };

  const generarPresentacion = async () => {
    setPresBusy(true);
    try {
      await generarPresentacionTax({ content: buildDeckContent() });
    } catch (e) {
      alert("Error al generar la presentación: " + e.message);
    } finally {
      setPresBusy(false);
    }
  };

  if (!projectId) {
    return (
      <div className="notice warn">
        Selecciona un proyecto del módulo TAX primero (botón Workspace en la
        cabecera).
      </div>
    );
  }

  return (
    <div className="tax-root">
      {/* TOPBAR */}
      <div className="tx-tb no-print">
        <input
          className="tx-empresa"
          type="text"
          placeholder="Empresa"
          value={params.empresa}
          onChange={(e) =>
            setParams((prev) => ({ ...prev, empresa: e.target.value }))
          }
        />
        <div className="tx-scbtns">
          <span className="tx-sclab">Escenario</span>
          {Object.entries(SCENARIO_NAMES).map(([k, lbl]) => (
            <button
              key={k}
              className={`tx-sbtn ${scn === k ? "on" : ""}`}
              onClick={() => applyScn(k)}
            >
              {lbl}
            </button>
          ))}
          <span className="tx-sep" />
          <button className="tx-btn ghost" onClick={() => setIngest("f101")}>
            ⬆ Formulario 101
          </button>
          <button
            className="tx-btn ghost"
            onClick={() => setIngest("resumido")}
          >
            ⬆ Balance resumido
          </button>
          <button className="tx-btn" onClick={exportExcel} disabled={busy}>
            {busy ? "Generando…" : "⬇ Excel"}
          </button>
          <button
            className="tx-btn gold"
            onClick={generarPresentacion}
            disabled={presBusy}
          >
            {presBusy ? "Generando…" : "🎨 Presentación"}
          </button>
          <button className="tx-btn" onClick={() => window.print()}>
            🖨 PDF
          </button>
          <button className="tx-btn" onClick={limpiarTodo}>
            🗑 Limpiar
          </button>
          <button className="tx-btn light" onClick={loadExample}>
            ↺ Ejemplo
          </button>
        </div>
      </div>

      {/* NAV PILLS */}
      <div className="tx-nav no-print">
        {SECTIONS.map(([id, n, label]) => (
          <button
            key={id}
            className={`tx-pill ${section === id ? "on" : ""}`}
            onClick={() => setSection(id)}
          >
            <span className="tx-pn">{n}</span>
            {label}
          </button>
        ))}
      </div>

      {ingest && (
        <IngestPanel
          kind={ingest}
          onClose={() => setIngest(null)}
          onExtracted={mergeExtract}
        />
      )}


      <div className="tx-content">
        {section === "datos" && (
          <SecDatos params={params} setText={setText} setParam={setParam} />
        )}
        {section === "legal" && <SecLegal />}
        {section === "eeff" && (
          <SecEeff D={D} setCell={setCell} />
        )}
        {section === "indices" && (
          <SecIndices D={D} i0={i0} i1={i1} i2={i2} />
        )}
        {section === "impuesto" && (
          <SecImpuesto
            D={D}
            R={R}
            CTRL={CTRL}
            params={params}
            setParam={setParam}
            setCtrlCell={setCtrlCell}
            sumK={sumK}
          />
        )}
        {section === "retenciones" && <SecRetenciones R={R} />}
        {section === "credito" && <SecCredito R={R} sumK={sumK} />}
        {section === "proyectado" && (
          <SecProyectado D={D} CTRL={CTRL} params={params} R={R} scn={scn} />
        )}
        {section === "dashboard" && (
          <SecDashboard
            D={D}
            R={R}
            scComp={scComp}
            scn={scn}
            sumK={sumK}
            i0={i0}
            i1={i1}
            i2={i2}
          />
        )}
        {section === "informe" && (
          <SecInforme
            D={D}
            R={R}
            CTRL={CTRL}
            i0={i0}
            i1={i1}
            i2={i2}
            scComp={scComp}
            scn={scn}
            params={params}
            sumK={sumK}
          />
        )}
      </div>
    </div>
  );
}

/* ============ panel de ingesta (carga 101 / balance resumido) ============ */
function IngestPanel({ kind, onClose, onExtracted }) {
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [progreso, setProgreso] = useState("");
  const f101 = kind === "f101";

  const process = async () => {
    if (!files.length) return;
    setBusy(true);
    setError("");
    setResult(null);
    const anios = [];
    const warnings = new Set();
    try {
      for (let i = 0; i < files.length; i++) {
        setProgreso(`Procesando ${i + 1}/${files.length}: ${files[i].name}`);
        const res = await extractTaxPlan(kind, files[i]);
        onExtracted?.(res);
        if (res.anio_detectado) anios.push(res.anio_detectado);
        (res.warnings || []).forEach((w) => warnings.add(w));
      }
      setResult({ count: files.length, anios, warnings: [...warnings] });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      setProgreso("");
    }
  };

  const getPlantilla = async () => {
    try {
      await downloadTaxPlantilla();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="tx-ingest no-print">
      <div className="tx-ingest-h">
        <h3>
          {f101
            ? "Cargar Formulario(s) 101 (SRI)"
            : "Cargar balance resumido (informe auditoría externa)"}
        </h3>
        <button className="tx-x" onClick={onClose}>
          ✕
        </button>
      </div>
      <p className="tx-muted">
        {f101
          ? "Sube uno o varios PDF del Formulario 101 (ej. 2023, 2024 y 2025). El sistema detecta el año de cada uno y puebla su columna en los estados financieros."
          : "Sube el balance resumido en la plantilla definida (.xlsx). Se mapeará a los mismos esquemas ESF / ER."}
      </p>
      {!f101 && (
        <button className="tx-btn ghost" onClick={getPlantilla}>
          ⬇ Descargar plantilla en blanco
        </button>
      )}
      <input
        type="file"
        multiple={f101}
        accept={f101 ? "application/pdf" : ".xlsx,.xls"}
        onChange={(e) => {
          setFiles([...(e.target.files || [])]);
          setResult(null);
          setError("");
        }}
      />
      {files.length > 0 && (
        <div className="tx-muted small">
          Seleccionado{files.length > 1 ? "s" : ""} ({files.length}):{" "}
          {files.map((f) => f.name).join(", ")}
        </div>
      )}
      <div className="tx-ingest-actions">
        <button className="tx-btn" onClick={process} disabled={!files.length || busy}>
          {busy ? "Procesando…" : `Procesar y cargar${files.length > 1 ? ` (${files.length})` : ""}`}
        </button>
      </div>
      {busy && progreso && (
        <div className="tx-note n-info">
          <span className="ic">⏳</span>
          <div>{progreso}</div>
        </div>
      )}
      {error && (
        <div className="tx-note n-warn">
          <span className="ic">⚠</span>
          <div>{error}</div>
        </div>
      )}
      {result && (
        <div className="tx-note n-ok">
          <span className="ic">✓</span>
          <div>
            <b>{result.count}</b> archivo{result.count > 1 ? "s" : ""} cargado
            {result.count > 1 ? "s" : ""} en <b>Estados financieros</b>.
            {result.anios.length > 0 && (
              <> Años detectados: <b>{result.anios.join(", ")}</b>.</>
            )}
            {result.warnings?.length > 0 && (
              <ul className="tx-warnlist">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
            <div className="tx-muted small">
              Verifica que los años sean correctos y ajusta las celdas azules.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Formatea una fecha ISO (yyyy-mm-dd) a texto es-EC; "" si vacía.
function fmtFecha(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("es-EC", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/* ===================== 0 · DATOS DEL CLIENTE ===================== */
function SecDatos({ params, setText, setParam }) {
  const [sri, setSri] = useState({ loading: false, msg: "", err: "" });
  const F = [
    ["empresa", "Nombre / razón social", "text", "Nombre de la compañía"],
    ["ruc", "RUC", "text", "13 dígitos"],
    ["repLegal", "Representante legal", "text", "Para dirigir el informe"],
    ["fechaCorte", "Fecha de corte", "date", "ej. 31 de julio"],
    ["fechaAnalisis", "Fecha del análisis", "date", "fecha del cálculo"],
  ];

  async function consultarSri() {
    const ruc = String(params.ruc || "").replace(/\D/g, "");
    if (ruc.length !== 13) {
      setSri({ loading: false, msg: "", err: "El RUC debe tener 13 dígitos." });
      return;
    }
    setSri({ loading: true, msg: "", err: "" });
    try {
      const r = await consultarSriRuc(ruc);
      if (r.razon_social) setText("empresa", r.razon_social);
      const actividad = r.actividad || "";
      setText("actividadSRI", actividad);
      // Sugerir sección CIIU a partir de la actividad y fijar su tasa.
      const cod = actividad ? sugerirSeccion(actividad) : "";
      if (cod) {
        setText("sector", cod);
        const s = sectorPorCod(cod);
        if (s) setParam("tasaSectorial", s.tasa);
      }
      setSri({
        loading: false,
        err: "",
        msg: `SRI: ${r.razon_social || "(sin razón social)"}${
          r.estado ? " · " + r.estado : ""
        }`,
      });
    } catch (e) {
      setSri({ loading: false, msg: "", err: e.message || "Error consultando el SRI." });
    }
  }

  function onSectorChange(cod) {
    setText("sector", cod);
    const s = sectorPorCod(cod);
    if (s) setParam("tasaSectorial", s.tasa);
  }

  return (
    <section>
      <div className="tx-h1">Datos del cliente</div>
      <p className="tx-lead">
        Identificación del contribuyente y fechas del análisis. Estos datos
        encabezan el informe gerencial. Si deja la fecha del análisis vacía, se
        usa la fecha de hoy.
      </p>
      <div className="tx-card">
        <h3>Encabezado del informe</h3>
        <div className="tx-grid g3">
          {F.map(([k, l, type, hint]) => (
            <div className="tx-field tx-field-l" key={k}>
              <label>
                {l} {hint && <span className="hint">{hint}</span>}
              </label>
              <input
                type={type}
                value={params[k] || ""}
                onChange={(e) => setText(k, e.target.value)}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="tx-card">
        <h3>Sector económico (CIIU) y crecimiento sectorial</h3>
        <p className="tx-lead" style={{ marginTop: 0 }}>
          Se usa <b>únicamente como respaldo</b>: si el histórico de ventas{" "}
          <b>no crece</b> (variación ≤ 0), la proyección toma la tasa de
          crecimiento del sector en lugar de un crecimiento nulo. Si el histórico
          sí crece, prevalece el dato real de la empresa. Consulte el SRI por RUC
          para autocompletar la razón social y sugerir la sección CIIU.
        </p>
        <div className="tx-actions">
          <button
            type="button"
            className="tx-btn"
            onClick={consultarSri}
            disabled={sri.loading}
          >
            {sri.loading ? "Consultando…" : "Consultar SRI por RUC"}
          </button>
          {sri.msg && <span className="tx-ok-line">{sri.msg}</span>}
          {sri.err && <span className="tx-warn-line">{sri.err}</span>}
        </div>
        <div className="tx-grid g3" style={{ marginTop: 12 }}>
          <div className="tx-field tx-field-l">
            <label>
              Sección CIIU del sector{" "}
              <span className="hint">determina la tasa referencial</span>
            </label>
            <select
              value={params.sector || ""}
              onChange={(e) => onSectorChange(e.target.value)}
            >
              <option value="">— Seleccione un sector —</option>
              {SECTORES_CIIU.map((s) => (
                <option key={s.cod} value={s.cod}>
                  {s.cod} · {s.nombre}
                </option>
              ))}
            </select>
          </div>
          <div className="tx-field tx-field-l">
            <label>
              Crecimiento sectorial (%){" "}
              <span className="hint">referencial, editable</span>
            </label>
            <input
              type="number"
              step="0.1"
              value={params.tasaSectorial ?? 0}
              onChange={(e) => setParam("tasaSectorial", e.target.value)}
            />
          </div>
          <div className="tx-field tx-field-l">
            <label>
              Actividad económica (SRI){" "}
              <span className="hint">solo informativa</span>
            </label>
            <input
              type="text"
              value={params.actividadSRI || ""}
              onChange={(e) => setText("actividadSRI", e.target.value)}
              placeholder="Se completa al consultar el SRI"
            />
          </div>
        </div>
      </div>
    </section>
  );
}

/* ===================== 1 · LEGAL ===================== */
function SecLegal() {
  return (
    <section>
      <div className="tx-h1">Base legal y normativa</div>
      <p className="tx-lead">
        Régimen ecuatoriano de <b>pago a cuenta sobre utilidades no
        distribuidas</b> (vigente desde septiembre de 2025). Marco de
        referencia para el análisis. Sujeto a criterios administrativos del SRI.
      </p>
      <div className="tx-legalgrid">
        <div className="tx-lcard">
          <h5>1 · Naturaleza</h5>
          <p>
            No es un impuesto definitivo, sino un <b>anticipo recuperable</b>{" "}
            que paga la sociedad al mantener utilidades acumuladas sin distribuir
            ni capitalizar. Puede compensarse contra retención de dividendos e
            Impuesto a la Renta, o solicitarse en devolución.
          </p>
        </div>
        <div className="tx-lcard">
          <h5>2 · Fecha de corte: 31 de julio</h5>
          <p>
            Si hasta el 31 de julio no se ha distribuido dividendos ni
            capitalizado, nace la obligación.{" "}
            <b>Toda planificación debe perfeccionarse antes de esa fecha.</b>{" "}
            Declaración en agosto; pago según 9º dígito del RUC, con opción de 3
            cuotas (ago/sep/oct).
          </p>
        </div>
        <div className="tx-lcard">
          <h5>3 · Base de cálculo</h5>
          <p>
            Utilidad contable del ejercicio anterior − 15% trabajadores −
            Impuesto a la Renta − reserva legal; (+) utilidades acumuladas
            anteriores; (−) dividendos y (−) capitalizaciones de enero a julio;
            (±) ajuste por método de participación.
          </p>
        </div>
        <div className="tx-lcard">
          <h5>4 · Tarifa única (sobre el total)</h5>
          <table className="tx-brk">
            <tbody>
              <tr>
                <td>Hasta 100.000</td>
                <td className="r">0%</td>
              </tr>
              <tr>
                <td>100.000 – 1M</td>
                <td className="r">0,75%</td>
              </tr>
              <tr>
                <td>1M – 10M</td>
                <td className="r">1,25%</td>
              </tr>
              <tr>
                <td>10M – 100M</td>
                <td className="r">1,75%</td>
              </tr>
              <tr>
                <td>100M – 500M</td>
                <td className="r">2,25%</td>
              </tr>
              <tr>
                <td>Más de 500M</td>
                <td className="r">2,50%</td>
              </tr>
            </tbody>
          </table>
          <p className="mt">
            No es progresiva: la tarifa del tramo se aplica a toda la base.
          </p>
        </div>
        <div className="tx-lcard">
          <h5>5 · Recuperación del crédito</h5>
          <ul>
            <li>
              <b>Dividendos:</b> crédito contra retención de dividendos e IR;
              excedente en devolución.
            </li>
            <li>
              <b>Capitalización:</b> compensación contra IR; excedente en
              devolución.
            </li>
            <li>
              <b>Devolución</b> del saldo dentro de los plazos legales.
            </li>
          </ul>
        </div>
        <div className="tx-lcard danger">
          <h5 className="rd">6 · Riesgo mortal</h5>
          <p>
            Si se paga el anticipo y no se distribuye ni capitaliza durante los{" "}
            <b>dos ejercicios siguientes</b>, el crédito se pierde y se registra
            como <b>gasto no deducible</b> (costo muerto).
          </p>
        </div>
        <div className="tx-lcard">
          <h5>7 · Capitalización válida (con sustancia)</h5>
          <ul>
            <li>Activos productivos nuevos.</li>
            <li>Inventarios nuevos.</li>
            <li>Generación de empleo ≥ 5%.</li>
          </ul>
          <p className="mt">
            Requisitos: Junta General, reforma estatutaria, escritura, Registro
            Mercantil; kardex, avalúo, certificación; facturas y soporte de
            propiedad.
          </p>
        </div>
        <div className="tx-lcard danger">
          <h5 className="rd">8 · Foco de fiscalización SRI</h5>
          <ul>
            <li>Capitalizaciones sin sustancia económica.</li>
            <li>Inventarios sobrevalorados.</li>
            <li>Activos usados como nuevos.</li>
            <li>Simulaciones societarias.</li>
          </ul>
        </div>
      </div>
    </section>
  );
}

/* ===================== 1 · EEFF (ingesta) ===================== */
function Ingesta({ schema, title, D, setCell }) {
  return (
    <table className="tx-tbl">
      <thead>
        <tr>
          <th>{title}</th>
          {ANIOS.map((y) => (
            <th key={y}>{y}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {schema.map((sp, idx) => {
          if (sp[0] === "sec")
            return (
              <tr className="secrow" key={idx}>
                <td colSpan={4}>{sp[1]}</td>
              </tr>
            );
          const key = sp[1];
          if (sp[0] === "in")
            return (
              <tr key={idx}>
                <td>{sp[2]}</td>
                {[0, 1, 2].map((c) => (
                  <td key={c}>
                    <input
                      className="tx-cin"
                      type="number"
                      value={D[key][c]}
                      onChange={(e) => setCell(key, c, e.target.value)}
                    />
                  </td>
                ))}
              </tr>
            );
          return (
            <tr className={sp[0] === "tot" ? "tot" : "sub"} key={idx}>
              <td>{sp[2]}</td>
              {[0, 1, 2].map((c) => (
                <td key={c}>{fmt(calcLine(D, sp, c))}</td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function SecEeff({ D, setCell }) {
  return (
    <section>
      <div className="tx-h1">Estados financieros de la empresa</div>
      <p className="tx-lead">
        Capa de ingesta — fuente única de datos. Edite las celdas{" "}
        <b className="blue">azules</b> y todos los cálculos, índices, impuestos y
        proyecciones se recalculan. Para otra empresa, sobrescriba estos valores
        o use los botones de carga (Formulario 101 / Balance resumido).
      </p>
      <div className="tx-split">
        <div className="tx-card">
          <h3>Estado de Situación Financiera</h3>
          <div className="tx-scroll">
            <Ingesta
              schema={ESF_SCHEMA}
              title="ESF (USD)"
              D={D}
              setCell={setCell}
            />
          </div>
        </div>
        <div className="tx-card">
          <h3>Estado de Resultados Integrales</h3>
          <div className="tx-scroll">
            <Ingesta
              schema={ER_SCHEMA}
              title="ER (USD)"
              D={D}
              setCell={setCell}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

/* ===================== 2 · INDICES ===================== */
function Kpi({ l, c, v, d }) {
  return (
    <div className={`tx-kpi ${c || ""}`}>
      <div className="kl">{l}</div>
      <div className="kv">{v}</div>
      <div className="kd">{d}</div>
    </div>
  );
}

function SecIndices({ D, i0, i1, i2 }) {
  const IND = [
    ["Liquidez corriente", (i) => fX(i.liq)],
    ["Prueba ácida", (i) => fX(i.acid)],
    ["Capital de trabajo", (i) => fmt(i.ct)],
    ["Endeudamiento", (i) => fP(i.end)],
    ["Apalancamiento", (i) => fX(i.apal)],
    ["Margen bruto", (i) => fP(i.mb)],
    ["Margen operativo", (i) => fP(i.mo)],
    ["Margen neto", (i) => fP(i.mn)],
    ["ROE", (i) => fP(i.roe)],
    ["ROA", (i) => fP(i.roa)],
    ["Rotación activos", (i) => fX(i.rot)],
    ["Días cartera", (i) => fD(i.dCart)],
    ["Días inventario", (i) => fD(i.dInv)],
    ["Días proveedores", (i) => fD(i.dProv)],
  ];
  const inds = [i0, i1, i2];
  const balData = {
    labels: ANIOS,
    datasets: [
      { label: "Activo", data: [0, 1, 2].map((c) => tActivo(D, c)), backgroundColor: "#1E5AA8", borderRadius: 4 },
      { label: "Pasivo", data: [0, 1, 2].map((c) => tPasivo(D, c)), backgroundColor: "#C0392B", borderRadius: 4 },
      { label: "Patrimonio", data: [0, 1, 2].map((c) => tPat(D, c)), backgroundColor: "#C7A83C", borderRadius: 4 },
    ],
  };
  const retData = {
    labels: ANIOS,
    datasets: [
      { label: "ROE", data: inds.map((i) => i.roe * 100), borderColor: "#C0392B", tension: 0.3, borderWidth: 2.5, pointRadius: 4 },
      { label: "ROA", data: inds.map((i) => i.roa * 100), borderColor: "#1E5AA8", tension: 0.3, borderWidth: 2.5, pointRadius: 4 },
      { label: "Margen neto", data: inds.map((i) => i.mn * 100), borderColor: "#C7A83C", tension: 0.3, borderWidth: 2.5, pointRadius: 4 },
    ],
  };
  return (
    <section>
      <div className="tx-h1">Índices financieros</div>
      <p className="tx-lead">
        Diagnóstico de liquidez, rentabilidad y eficiencia operativa con
        tendencia.
      </p>
      <div className="tx-kpis mb">
        <Kpi l="Liquidez" c={i2.liq >= 1.5 ? "g" : "a"} v={fX(i2.liq)} d={`Antes ${fX(i1.liq)}`} />
        <Kpi l="ROE" c={i2.roe >= 0.12 ? "g" : i2.roe >= 0.06 ? "a" : "r"} v={fP(i2.roe)} d={`Antes ${fP(i1.roe)}`} />
        <Kpi l="Margen neto" c={i2.mn >= i1.mn ? "g" : "r"} v={fP(i2.mn)} d={`Antes ${fP(i1.mn)}`} />
        <Kpi l="Días inventario" c={i2.dInv <= 120 ? "g" : i2.dInv <= 180 ? "a" : "r"} v={fD(i2.dInv)} d={`Antes ${fD(i1.dInv)}`} />
        <Kpi l="Ciclo efectivo" c={cce(D, 2) <= 120 ? "g" : "r"} v={fD(cce(D, 2))} d={`Antes ${fD(cce(D, 1))}`} />
      </div>
      <div className="tx-split">
        <div className="tx-card">
          <h3>Indicadores</h3>
          <div className="tx-scroll">
            <table className="tx-tbl">
              <thead>
                <tr>
                  <th>Indicador</th>
                  {ANIOS.map((y) => (
                    <th key={y}>{y}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {IND.map(([l, fn]) => (
                  <tr key={l}>
                    <td>{l}</td>
                    {inds.map((i, c) => (
                      <td key={c}>{fn(i)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <div className="tx-card">
            <h3>Activo · Pasivo · Patrimonio</h3>
            <TaxChart
              type="bar"
              data={balData}
              options={{ ...BASE_OPT, scales: { y: Y_MONEY, x: { grid: { display: false } } } }}
            />
          </div>
          <div className="tx-card">
            <h3>ROE · ROA · Margen neto</h3>
            <TaxChart
              type="line"
              data={retData}
              options={{ ...BASE_OPT, scales: { y: Y_PCT, x: { grid: { display: false } } } }}
            />
          </div>
        </div>
      </div>
      <div className="tx-card">
        <h3>Descomposición DuPont del ROE {ANIOS[2]}</h3>
        <div className="tx-dupont">
          <Dp l="Margen neto" v={fP(i2.mn, 2)} />
          <Op s="×" />
          <Dp l="Rotación" v={fX(i2.rot, 3)} />
          <Op s="×" />
          <Dp l="Apalancamiento" v={fX(i2.apal, 3)} />
          <Op s="=" />
          <Dp l="ROE" v={fP(i2.roe, 2)} gold />
        </div>
      </div>
    </section>
  );
}

function Dp({ l, v, gold }) {
  return (
    <div className={`tx-dp ${gold ? "gold" : ""}`}>
      <div className="dpl">{l}</div>
      <div className="dpv">{v}</div>
    </div>
  );
}
function Op({ s }) {
  return <span className="tx-op">{s}</span>;
}

/* ===================== 3 · IMPUESTO ===================== */
function SecImpuesto({ D, R, CTRL, params, setParam, setCtrlCell, sumK }) {
  const noDist = D.resAcum[2];
  const wf = [
    ["Utilidad depurada del ejercicio (≈ neta)", neta(D, 2), ""],
    ["(+) Utilidades acumuladas (saldo cierre anterior)", D.resAcum[1], "plus"],
    ["= Utilidades no distribuidas", noDist, "sub"],
    ["(−) Dividendos (año 1)", -CTRL[0].div, "minus"],
    ["(−) Capitalización (año 1)", -CTRL[0].cap, "minus"],
    ["= Base gravable (año 1)", R[0].base, "base"],
  ];
  const brows = [
    ["Hasta 100.000", "0%", 100000],
    ["100.000 – 1M", "0,75%", 1000000],
    ["1 – 10M", "1,25%", 10000000],
    ["10 – 100M", "1,75%", 100000000],
    ["100 – 500M", "2,25%", 500000000],
    ["+500M", "2,50%", Infinity],
  ];
  let prev = 0;
  const PARAM_F = [
    ["costoR", "Costo / ventas (%)", null],
    ["gastoR", "Gastos op. / ventas (%)", null],
    ["irR", "Tasa Impuesto Renta (%)", null],
    ["retDiv", "Retención div. único (%)", "verificar"],
  ];
  const CTRL_ROWS = [
    ["Dividendos (ene–jul)", "div", false],
    ["Capitalización (ene–jul)", "cap", false],
  ];
  return (
    <section>
      <div className="tx-h1">Cálculo del impuesto — pago a cuenta</div>
      <p className="tx-lead">
        Depuración de la base y aplicación de la tarifa única. El crecimiento de
        ventas y los márgenes se derivan <b>automáticamente</b> del histórico
        (crecimiento {params.growth || 0}%); tú solo decides los{" "}
        <b>dividendos y la capitalización</b> por año (antes del 31 de julio).
      </p>
      <div className="tx-card">
        <h3>Palancas de planificación por año</h3>
        <div className="tx-grid g4 mb">
          {PARAM_F.map(([k, l, hint]) => (
            <div className="tx-field" key={k}>
              <label>
                {l} {hint && <span className="hint">{hint}</span>}
              </label>
              <input
                type="number"
                step="0.1"
                value={params[k]}
                onChange={(e) => setParam(k, e.target.value)}
              />
            </div>
          ))}
        </div>
        <div className="tx-scroll">
          <table className="tx-tbl">
            <thead>
              <tr>
                <th>Decisión / año</th>
                {PROJ.map((y) => (
                  <th className="proj" key={y}>
                    {y}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {CTRL_ROWS.map(([l, k, isPct]) => (
                <tr key={k}>
                  <td>{l}</td>
                  {CTRL.map((c, i) => (
                    <td className="proj" key={i}>
                      <input
                        className="tx-cin"
                        type="number"
                        value={isPct ? c[k] : Math.round(c[k])}
                        onChange={(e) => setCtrlCell(i, k, e.target.value)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="tx-legend">
          Base de cada año = resultados acumulados del cierre anterior −
          dividendos − capitalización (enero–julio).
        </p>
      </div>
      <div className="tx-split">
        <div className="tx-card">
          <h3>Determinación de la base (año 1)</h3>
          <div className="tx-wf">
            {wf.map(([l, v, c], idx) => (
              <div className={`tx-wf-row ${c}`} key={idx}>
                <span className="wl">{l}</span>
                <span className="wv">{fmt(v)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="tx-card">
          <h3>Tarifa aplicable</h3>
          <table className="tx-brk">
            <tbody>
              {brows.map(([l, t, lim]) => {
                const act = R[0].base > prev && R[0].base <= lim;
                prev = lim;
                return (
                  <tr className={act ? "act" : ""} key={l}>
                    <td>{l}</td>
                    <td className="r">{t}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="tx-note n-info mt">
            <span className="ic">💡</span>
            <div>
              <b>Nivel 1:</b> capitalizar antes del 31 de julio hasta que la
              base caiga al tramo 0% — la obligación no nace.
            </div>
          </div>
        </div>
      </div>
      <div className="tx-card">
        <h3>Pago a cuenta 2026–2028</h3>
        <div className="tx-scroll">
          <table className="tx-tbl">
            <thead>
              <tr>
                <th>Concepto</th>
                {PROJ.map((y) => (
                  <th className="proj" key={y}>
                    {y}
                  </th>
                ))}
                <th className="proj">Total</th>
              </tr>
            </thead>
            <tbody>
              <TxRow label="Base gravable" R={R} k="base" total={sumK("base")} />
              <TxRow label="Tarifa única" R={R} fn={(r) => (r.tar * 100).toFixed(2) + "%"} />
              <TxRow label="Pago a cuenta" R={R} k="pago" cls="sub" total={sumK("pago")} />
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

// Fila de tabla proyectada (espejo de txRow). Con fn no se muestra total.
function TxRow({ label, R, k, cls, fn, total }) {
  return (
    <tr className={cls || ""}>
      <td>{label}</td>
      {R.map((r, i) => (
        <td className="proj" key={i}>
          {fn ? fn(r) : fmt(r[k])}
        </td>
      ))}
      <td className="proj">{fn ? "" : fmt(total)}</td>
    </tr>
  );
}

/* ===================== 4 · RETENCIONES ===================== */
function SecRetenciones({ R }) {
  const sum = (k) => R.reduce((s, r) => s + r[k], 0);
  return (
    <section>
      <div className="tx-h1">Cálculo de retenciones de dividendos</div>
      <p className="tx-lead">
        Al distribuir, el accionista soporta la retención del impuesto único; el
        pago a cuenta se acredita contra ella.
      </p>
      <div className="tx-card">
        <h3>Retención y crédito por dividendos</h3>
        <div className="tx-scroll">
          <table className="tx-tbl">
            <thead>
              <tr>
                <th>Concepto</th>
                {PROJ.map((y) => (
                  <th className="proj" key={y}>
                    {y}
                  </th>
                ))}
                <th className="proj">Total</th>
              </tr>
            </thead>
            <tbody>
              <TxRow label="Dividendos distribuidos" R={R} k="div" total={sum("div")} />
              <TxRow label="Retención impuesto único" R={R} k="ret" cls="sub" total={sum("ret")} />
              <TxRow label="Crédito usado vs. retención" R={R} k="cRet" cls="hl" total={sum("cRet")} />
              <TxRow label="Retención neta a enterar" R={R} fn={(r) => fmt(Math.max(0, r.ret - r.cRet))} />
            </tbody>
          </table>
        </div>
      </div>
      <div className="tx-note n-info">
        <span className="ic">ℹ️</span>
        <div>
          La tasa de retención del impuesto único a dividendos depende de la
          residencia y la fracción del accionista; el valor es parametrizable y
          debe validarse con la tabla vigente.
        </div>
      </div>
    </section>
  );
}

/* ===================== 5 · CREDITO ===================== */
function SecCredito({ R, sumK }) {
  return (
    <section>
      <div className="tx-h1">
        Crédito tributario aplicado al Impuesto a la Renta
      </div>
      <p className="tx-lead">
        El pago a cuenta no absorbido en la retención de dividendos se usa para{" "}
        <b>disminuir el Impuesto a la Renta</b> del ejercicio; el excedente se
        solicita en devolución.
      </p>
      <div className="tx-kpis mb">
        <Kpi l="Pago a cuenta 2026–28" c="b" v={fmt(sumK("pago"))} d="Anticipo total" />
        <Kpi l="Crédito que baja el IR" c="g" v={fmt(sumK("cIR"))} d="Reduce Impuesto a la Renta" />
        <Kpi l="Crédito vía dividendos" c="g" v={fmt(sumK("cRet"))} d="Contra retención" />
        <Kpi l="A devolución" c="b" v={fmt(sumK("dev"))} d="Excedente" />
        <Kpi l="En riesgo" c="r" v={fmt(R[R.length - 1].riesgo)} d="Costo muerto potencial" />
      </div>
      <div className="tx-card">
        <h3>Ciclo del crédito por año</h3>
        <div className="tx-scroll">
          <table className="tx-tbl">
            <thead>
              <tr>
                <th>Concepto</th>
                {PROJ.map((y) => (
                  <th className="proj" key={y}>
                    {y}
                  </th>
                ))}
                <th className="proj">Total</th>
              </tr>
            </thead>
            <tbody>
              <TxRow label="Crédito generado (pago)" R={R} k="pago" total={sumK("pago")} />
              <TxRow label="Usado vs. retención dividendos" R={R} k="cRet" total={sumK("cRet")} />
              <TxRow label="Usado vs. Impuesto a la Renta" R={R} k="cIR" cls="hl" total={sumK("cIR")} />
              <TxRow label="Excedente a devolución" R={R} k="dev" total={sumK("dev")} />
              <TxRow label="En riesgo (costo muerto)" R={R} k="enR" total={sumK("enR")} />
            </tbody>
          </table>
        </div>
      </div>
      <div className="tx-note n-dang">
        <span className="ic">⛔</span>
        <div>
          <b>Riesgo de costo muerto:</b> el crédito no recuperado mediante
          distribución o capitalización en los dos ejercicios siguientes se
          pierde y se registra como gasto no deducible.
        </div>
      </div>
    </section>
  );
}

/* ===================== 6 · PROYECTADO ===================== */
function YHead({ title }) {
  return (
    <thead>
      <tr>
        <th>{title}</th>
        {ANIOS.map((y) => (
          <th key={y}>{y}</th>
        ))}
        {PROJ.map((y) => (
          <th className="proj" key={y}>
            {y}P
          </th>
        ))}
      </tr>
    </thead>
  );
}

function RowHP({ label, hist, proj, cls, neg }) {
  return (
    <tr className={cls || ""}>
      <td>{label}</td>
      {hist.map((v, i) => (
        <td key={`h${i}`}>{m(v, neg)}</td>
      ))}
      {proj.map((v, i) => (
        <td className="proj" key={`p${i}`}>
          {m(v, neg)}
        </td>
      ))}
    </tr>
  );
}

function SecProyectado({ D, CTRL, params }) {
  const { assumptions: A, rows } = projectFinancials(D, CTRL, params);
  const cuadra = rows.every((r) => Math.abs(r.cuadre) < 1.5);
  const sup = [
    ["Crecimiento ventas", A.growth + "%"],
    ["Costo / ventas", A.costoR + "%"],
    ["Gastos op. / ventas", A.gastoR + "%"],
    ["Días de cartera", A.diasCxC + " d"],
    ["Días de inventario", A.diasInv + " d"],
    ["Días de proveedores", A.diasCxP + " d"],
    ["Depreciación (% PP&E)", A.deprecPctPPE + "%"],
    ["CAPEX (% ventas)", A.capexPctVentas + "%"],
  ];
  const Col = ({ children }) => <th>{children}</th>;
  const Row = ({ l, k, cls, fn }) => (
    <tr className={cls || ""}>
      <td>{l}</td>
      {rows.map((r, i) => (
        <td key={i}>{(fn || fmt)(r[k])}</td>
      ))}
    </tr>
  );
  return (
    <section>
      <div className="tx-h1">Estados financieros proyectados 2026–2028</div>
      <p className="tx-lead">
        Proyección <b>automática</b>: las ventas crecen según el histórico, se
        aplican los márgenes y días de capital de trabajo observados, y se
        modelan CAPEX, depreciación y flujo de caja. Tú no llenas supuestos; solo
        decides dividendos/capitalización en los escenarios.
      </p>

      {/* ---- Supuestos auto ---- */}
      <div className="tx-card">
        <h3>Supuestos — derivados automáticamente del histórico</h3>
        <div className="tx-supgrid">
          {sup.map(([l, v]) => (
            <div className="tx-sup" key={l}>
              <div className="tx-sup-v">{v}</div>
              <div className="tx-sup-l">{l}</div>
            </div>
          ))}
        </div>
        <p className="tx-muted small">
          Se recalculan solos al editar los estados financieros (celdas azules).
          Crecimiento con piso 0% (no se proyectan caídas indefinidas).
        </p>
        <p className="tx-muted small">
          <b>Fuente del crecimiento:</b>{" "}
          {A.growthRaw > 0 ? (
            <>histórico real de la empresa ({A.growthRaw}% promedio anual).</>
          ) : (
            <>
              el histórico no crece ({A.growthRaw}%); se usa la tasa sectorial
              referencial ({Number(params.tasaSectorial) || 0}%
              {params.sector ? `, sección CIIU ${params.sector}` : ""}).
            </>
          )}
        </p>
      </div>

      {/* ---- Metodología de proyección ---- */}
      <div className="tx-card">
        <h3>Metodología de la proyección</h3>
        <div className="tx-legalgrid">
          {METODOLOGIA_PROYECCION.map((m) => (
            <div className="tx-lcard" key={m.titulo}>
              <h5>{m.titulo}</h5>
              <p>{m.detalle}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ---- Estado de Resultados ---- */}
      <div className="tx-card">
        <h3>Estado de Resultados proyectado</h3>
        <div className="tx-scroll">
          <table className="tx-ptbl">
            <thead><tr><Col>Concepto (USD)</Col>{PROJ.map((y) => <Col key={y}>{y}</Col>)}</tr></thead>
            <tbody>
              <Row l="Ventas" k="ventas" />
              <Row l="(−) Costo de ventas" k="costo" />
              <Row l="Utilidad bruta" k="ub" cls="sub" />
              <Row l="(−) Gastos operativos" k="gAdmin" />
              <Row l="EBITDA" k="ebitda" cls="sub" />
              <Row l="(−) Depreciación" k="deprec" />
              <Row l="EBIT (utilidad operativa)" k="ebit" cls="sub" />
              <Row l="(−) Participación 15%" k="part" />
              <Row l="(−) Impuesto a la renta" k="irCausado" />
              <Row l="Utilidad neta" k="neta" cls="tot" />
            </tbody>
          </table>
        </div>
      </div>

      {/* ---- Estado de Situación Financiera ---- */}
      <div className="tx-card">
        <h3>Estado de Situación Financiera proyectado</h3>
        <div className="tx-scroll">
          <table className="tx-ptbl">
            <thead><tr><Col>Concepto (USD)</Col>{PROJ.map((y) => <Col key={y}>{y}</Col>)}</tr></thead>
            <tbody>
              <Row l="Efectivo" k="efectivo" />
              <Row l="Cuentas por cobrar" k="cxc" />
              <Row l="Inventario" k="inv" />
              <Row l="Total activo corriente" k="activoCte" cls="sub" />
              <Row l="Propiedad, planta y equipo" k="ppe" />
              <Row l="TOTAL ACTIVO" k="totalActivo" cls="tot" />
              <Row l="Cuentas por pagar" k="cxp" />
              <Row l="TOTAL PASIVO" k="totalPasivo" cls="sub" />
              <Row l="Capital" k="capital" />
              <Row l="Resultados acumulados" k="resAcum" />
              <Row l="TOTAL PATRIMONIO" k="patrimonio" cls="tot" />
            </tbody>
          </table>
        </div>
        <p className={cuadra ? "tx-ok-line" : "tx-warn-line"}>
          {cuadra
            ? "✓ El balance cuadra: Activo = Pasivo + Patrimonio en los tres años."
            : "⚠ Revisar: el balance no cuadra perfectamente (faltan datos en el histórico)."}
        </p>
      </div>

      {/* ---- Flujo de caja ---- */}
      <div className="tx-card">
        <h3>Flujo de caja proyectado</h3>
        <div className="tx-scroll">
          <table className="tx-ptbl">
            <thead><tr><Col>Concepto (USD)</Col>{PROJ.map((y) => <Col key={y}>{y}</Col>)}</tr></thead>
            <tbody>
              <Row l="Flujo operativo (FCO)" k="fco" cls="sub" />
              <Row l="(−) CAPEX (inversión)" k="fci" />
              <Row l="(−) Dividendos pagados" k="fcf" />
              <Row l="= Variación de caja" k="deltaCaja" cls="sub" />
              <Row l="Efectivo final" k="efectivo" cls="tot" />
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

/* ===================== 7 · DASHBOARD ===================== */
function SecDashboard({ D, R, scComp, scn, sumK, i0, i1, i2 }) {
  const inds = [i0, i1, i2];
  const cIR = {
    labels: PROJ,
    datasets: [
      { label: "IR causado", data: R.map((r) => Math.round(r.irCausado)), backgroundColor: "#C0392B", borderRadius: 4 },
      { label: "IR a pagar (con crédito)", data: R.map((r) => Math.round(r.irAP)), backgroundColor: "#1E8449", borderRadius: 4 },
    ],
  };
  const cTax = {
    labels: PROJ,
    datasets: [
      { label: "Pago a cuenta", data: R.map((r) => Math.round(r.pago)), backgroundColor: "#1E5AA8", borderRadius: 4 },
      { label: "En riesgo", data: R.map((r) => Math.round(r.enR)), backgroundColor: "#C0392B", borderRadius: 4 },
    ],
  };
  const cNeta = {
    labels: PROJ,
    datasets: [{ label: "Utilidad neta", data: R.map((r) => Math.round(r.neta)), backgroundColor: "#C7A83C", borderRadius: 4 }],
  };
  const cPat = {
    labels: PROJ,
    datasets: [
      { label: "Patrimonio", data: R.map((r) => Math.round(r.patrimonio)), borderColor: "#0A2342", backgroundColor: "rgba(10,35,66,.08)", fill: true, tension: 0.3, borderWidth: 2.5, pointRadius: 4 },
      { label: "Resultados acum.", data: R.map((r) => Math.round(r.resAcum)), borderColor: "#A6C63F", tension: 0.3, borderWidth: 2.5, pointRadius: 4 },
    ],
  };
  const cCycle = {
    labels: ANIOS,
    datasets: [
      { label: "Cartera", data: inds.map((i) => i.dCart), backgroundColor: "#1E5AA8" },
      { label: "Inventario", data: inds.map((i) => i.dInv), backgroundColor: "#C0392B" },
      { label: "Proveedores (−)", data: inds.map((i) => -i.dProv), backgroundColor: "#A6C63F" },
    ],
  };
  const cScn = {
    labels: ["Sin acción", "Escenario actual"],
    datasets: [
      {
        data: [Math.round(scComp.sin), Math.round(sumK("pago"))],
        backgroundColor: ["#C0392B", "#1E8449"],
        borderRadius: 6,
        maxBarThickness: 70,
      },
    ],
  };
  const moneyOpt = { ...BASE_OPT, scales: { y: Y_MONEY, x: { grid: { display: false } } } };
  return (
    <section>
      <div className="tx-h1">Dashboards ejecutivos</div>
      <p className="tx-lead">Síntesis integral financiera y tributaria.</p>
      <div className="tx-kpis mb">
        <Kpi l="Pago sin acción 2026–28" c="r" v={fmt(scComp.sin)} d="Se repite cada año" />
        <Kpi l="Pago escenario actual" c="b" v={fmt(sumK("pago"))} d={SCENARIO_NAMES[scn]} />
        <Kpi l="Crédito baja el IR" c="g" v={fmt(sumK("cIR"))} d="Ahorro en renta" />
        <Kpi l="Crédito en riesgo" c="r" v={fmt(R[R.length - 1].riesgo)} d="Costo muerto" />
        <Kpi l="Patrimonio 2028" c="b" v={fmt(R[R.length - 1].patrimonio)} d="Proyectado" />
      </div>
      <div className="tx-split">
        <div className="tx-card">
          <h3>IR causado vs. a pagar (con crédito)</h3>
          <TaxChart type="bar" data={cIR} options={moneyOpt} />
        </div>
        <div className="tx-card">
          <h3>Pago a cuenta y crédito en riesgo</h3>
          <TaxChart type="bar" data={cTax} options={moneyOpt} />
        </div>
        <div className="tx-card">
          <h3>Utilidad neta proyectada</h3>
          <TaxChart type="bar" data={cNeta} options={{ ...moneyOpt, plugins: { legend: { display: false } } }} />
        </div>
        <div className="tx-card">
          <h3>Patrimonio y resultados acumulados</h3>
          <TaxChart type="line" data={cPat} options={moneyOpt} />
        </div>
        <div className="tx-card">
          <h3>Ciclo de conversión de efectivo (días)</h3>
          <TaxChart
            type="bar"
            data={cCycle}
            options={{ ...BASE_OPT, scales: { y: { stacked: true, grid: { color: "#eef1f4" } }, x: { stacked: true, grid: { display: false } } } }}
          />
        </div>
        <div className="tx-card">
          <h3>Pago a cuenta — comparación de escenarios</h3>
          <TaxChart type="bar" data={cScn} options={{ ...moneyOpt, plugins: { legend: { display: false } } }} />
        </div>
      </div>
    </section>
  );
}

/* ===================== ★ INFORME ===================== */
const INFORME_INDICE = [
  "Resumen Ejecutivo",
  "Antecedentes",
  "Objetivo del Proyecto",
  "Alcance",
  "Marco Normativo",
  "Diagnóstico Financiero",
  "Diagnóstico Tributario",
  "Diagnóstico Societario",
  "Análisis del Pago Históricamente Realizado",
  "Identificación de Alternativas Previas al 31 de Julio",
  "Matriz de Decisión Estratégica",
  "Modelación Financiera y Tributaria",
  "Dashboard Ejecutivo",
  "Plan de Acción",
  "Conclusiones",
  "Anexos",
];

// Pago a cuenta histórico: base = utilidades retenidas del cierre del año
// anterior. El régimen rige desde 2025 (primer pago: base = acumuladas 2024).
function pagoHistorico(D, params) {
  const baseProp = (anioIdx) => D.resAcum[anioIdx]; // acum. cierre anterior
  const calc = (base) => ({ base, tar: tarifa(base), pago: base * tarifa(base) });
  return [
    { anio: ANIOS[2], ...calc(baseProp(1)) }, // pago 2025 ← acumuladas 2024
  ];
}

// Cuatro escenarios comparativos con montos definidos. La decisión (dividendos /
// capitalización) se aplica solo en el primer año proyectado (2026); el resto
// del horizonte queda sin nuevas decisiones.
function buildEscenarios(D, CTRL, params) {
  const acum = D.resAcum[2]; // utilidades acumuladas al cierre 2025
  const divObj = params.divObjetivo || 0;
  const mk = (div, cap) =>
    CTRL.map((c, i) => (i === 0 ? { g: c.g, div, cap } : { g: c.g, div: 0, cap: 0 }));
  const defs = [
    { key: "e1", nombre: "1 · Sin acción", div: 0, cap: 0 },
    { key: "e2", nombre: `2 · Dividendos ${fmt(divObj)}`, div: divObj, cap: 0 },
    {
      key: "e3",
      nombre: `3 · Dividendos ${fmt(divObj)} + capitaliza la diferencia`,
      div: divObj,
      cap: Math.max(0, acum - divObj),
    },
    { key: "e4", nombre: "4 · Capitaliza todo", div: 0, cap: acum },
  ];
  return defs.map((d) => {
    const rows = computeModel(D, mk(d.div, d.cap), params);
    const last = rows[rows.length - 1];
    return {
      ...d,
      pago: rows.reduce((a, r) => a + r.pago, 0),
      recuperable: rows.reduce((a, r) => a + r.cIR + r.dev, 0),
      muerto: last.riesgo,
      patrimonio: last.patrimonio,
      retencion: d.div * ((params.retDiv || 0) / 100),
      pago2026: rows[0].pago,
    };
  });
}

function SecInforme({ D, R, CTRL, i0, i1, i2, scComp, scn, params, sumK }) {
  const emp = (params.empresa || "").trim() || "la Compañía";
  const rep = (params.repLegal || "").trim();
  const ruc = (params.ruc || "").trim();
  const fAnalisis =
    fmtFecha(params.fechaAnalisis) ||
    new Date().toLocaleDateString("es-EC", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  const fCorte = fmtFecha(params.fechaCorte);

  // Escenario actual
  const pagoSin = scComp.sin;
  const pagoAct = R.reduce((a, r) => a + r.pago, 0);
  const credIR = R.reduce((a, r) => a + r.cIR, 0);
  const devol = R.reduce((a, r) => a + r.dev, 0);
  const recuperable = credIR + devol;
  const ahorro = pagoSin - pagoAct;
  const riesgo = R[R.length - 1].riesgo;
  const dVtas = (i2.V - i1.V) / i1.V;

  // Cuatro escenarios comparativos definidos + pago histórico (desde 2025).
  const matriz = buildEscenarios(D, CTRL, params);
  const historico = pagoHistorico(D, params);

  // Charts embebidos (dashboard ejecutivo).
  const moneyOpt = { ...BASE_OPT, scales: { y: Y_MONEY, x: { grid: { display: false } } } };
  const cScn = {
    labels: matriz.map((m) => m.nombre),
    datasets: [
      {
        label: "Pago a cuenta 2026–2028",
        data: matriz.map((m) => Math.round(m.pago)),
        backgroundColor: ["#C0392B", "#1E5AA8", "#1E8449", "#C7A83C"],
        borderRadius: 6,
        maxBarThickness: 60,
      },
    ],
  };
  const cFlujo = {
    labels: PROJ,
    datasets: [
      { label: "Pago a cuenta", data: R.map((r) => Math.round(r.pago)), backgroundColor: "#1E5AA8", borderRadius: 4 },
      { label: "Crédito vs. IR", data: R.map((r) => Math.round(r.cIR)), backgroundColor: "#1E8449", borderRadius: 4 },
      { label: "En riesgo", data: R.map((r) => Math.round(r.enR)), backgroundColor: "#C0392B", borderRadius: 4 },
    ],
  };

  const totalPat = D.capital[2] + D.reservas[2] + D.ori[2] + D.resAcum[2];
  const reservaMin = D.capital[2] * 0.5; // reserva legal hasta 50% del capital
  const primerPagoSin = computeModel(
    D,
    applyScenario("sin", D, CTRL, params),
    params,
  )[0];

  return (
    <section>
      <div className="tx-report">
        {/* ===== PORTADA ===== */}
        <div className="rcover">
          <div className="rk">AuditBrain · Executive Advisory · Tax Advisory</div>
          <h2>Planificación tributaria sobre utilidades no distribuidas</h2>
          <div className="rsub">Informe ejecutivo para el accionista</div>
          <div className="remp">{emp}</div>
          {ruc && <div className="rdate">RUC: {ruc}</div>}
          {rep && <div className="rdate">{rep} · Representante legal</div>}
          <div className="rdate">
            Horizonte 2026–2028 · {fAnalisis}
            {fCorte && ` · Corte: ${fCorte}`}
          </div>
          <div className="mt">
            <span className="conf">
              Confidencial · Documento preliminar sujeto a revisión y aprobación
            </span>
          </div>
        </div>

        {/* ===== ÍNDICE GENERAL ===== */}
        <h4>Índice general</h4>
        <ol className="idx">
          {INFORME_INDICE.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ol>

        {/* ===== 1. RESUMEN EJECUTIVO ===== */}
        <h4>1. Resumen Ejecutivo</h4>
        {rep && (
          <p>
            Estimado(a) señor(a) <b>{rep}</b>, en su calidad de representante
            legal de {emp}, ponemos a su consideración el presente análisis.
          </p>
        )}
        <p>
          {emp} mantiene utilidades acumuladas por <b>{fmt(D.resAcum[2])}</b>,
          lo que la expone al pago a cuenta sobre utilidades no distribuidas. Sin
          planificación, el desembolso acumulado 2026–2028 ascendería a{" "}
          <b>{fmt(pagoSin)}</b>. Bajo el escenario <b>{SCENARIO_NAMES[scn]}</b>,
          el pago se reduce a <b>{fmt(pagoAct)}</b>, con un ahorro/diferimiento
          de <b>{fmt(ahorro)}</b> y <b>{fmt(recuperable)}</b> recuperables vía
          crédito y devolución.
        </p>
        <div className="tx-kpis mb">
          <Kpi l="Utilidades no distribuidas" c="b" v={fmt(D.resAcum[2])} d="Saldo 2025" />
          <Kpi l="Pago sin acción 2026–28" c="r" v={fmt(pagoSin)} d="Si no se actúa" />
          <Kpi l={`Pago — ${SCENARIO_NAMES[scn]}`} c="g" v={fmt(pagoAct)} d="Escenario actual" />
          <Kpi l="Ahorro / diferimiento" c="g" v={fmt(ahorro)} d="vs. no actuar" />
          <Kpi l="Crédito recuperable" c="b" v={fmt(recuperable)} d="IR + devolución" />
          <Kpi l="En riesgo (costo muerto)" c="r" v={fmt(riesgo)} d="Por inacción" />
        </div>

        {/* ===== 2. ANTECEDENTES ===== */}
        <h4>2. Antecedentes</h4>
        <p>
          Desde septiembre de 2025 rige en Ecuador el{" "}
          <b>pago a cuenta sobre las utilidades no distribuidas</b>, un anticipo
          anual que grava a las sociedades que mantienen utilidades acumuladas
          sin distribuir ni capitalizar al 31 de julio de cada año. Las
          utilidades acumuladas de {emp} han evolucionado de{" "}
          <b>{fmt(D.resAcum[0])}</b> (2023) a <b>{fmt(D.resAcum[1])}</b> (2024) y{" "}
          <b>{fmt(D.resAcum[2])}</b> (2025), tendencia creciente que incrementa la
          exposición a la obligación de forma recurrente.
        </p>

        {/* ===== 3. OBJETIVO ===== */}
        <h4>3. Objetivo del Proyecto</h4>
        <p>
          Estructurar, con evidencia financiera y tributaria, cómo (i){" "}
          <b>evitar legítimamente que la obligación nazca</b> y (ii){" "}
          <b>convertir cada dólar pagado en crédito plenamente recuperable</b>,
          cuantificando los escenarios de decisión disponibles antes del 31 de
          julio y su impacto en caja, patrimonio y riesgo de costo muerto.
        </p>

        {/* ===== 4. ALCANCE ===== */}
        <h4>4. Alcance</h4>
        <p>
          Comprende: diagnóstico financiero 2023–2025, determinación de la base y
          del pago a cuenta bajo la tarifa única vigente, cálculo de la retención
          del impuesto único a los dividendos, modelación del crédito tributario
          aplicable a la reducción del Impuesto a la Renta, proyección de estados
          financieros 2026–2028, matriz de decisión y plan de acción. La
          herramienta es reutilizable para cualquier empresa mediante la carga de
          sus estados financieros (Formulario 101 o balance resumido).
        </p>

        {/* ===== 5. MARCO NORMATIVO ===== */}
        <h4>5. Marco Normativo</h4>
        <ul>
          <li>
            <b>Naturaleza:</b> anticipo recuperable, no impuesto definitivo.
          </li>
          <li>
            <b>Base:</b> utilidades acumuladas − dividendos − capitalización, con
            corte al <b>31 de julio</b>.
          </li>
          <li>
            <b>Tarifa:</b> única por tramo (no progresiva); se aplica a toda la
            base según su magnitud (ver Anexo B).
          </li>
          <li>
            <b>Crédito en cascada:</b> el pago se compensa contra la retención de
            dividendos, luego contra el Impuesto a la Renta y el excedente se
            solicita en devolución.
          </li>
          <li className="rwarn">
            Parámetros normativos (tarifa, retención de dividendos {params.retDiv}
            %, tasa IR {params.irR}%, reserva legal) <b>editables y sujetos a
            validación humana</b> y a criterios administrativos del SRI.
          </li>
        </ul>

        {/* ===== 6. DIAGNÓSTICO FINANCIERO ===== */}
        <h4>6. Diagnóstico Financiero</h4>
        <p>
          En 2025 las ventas {dVtas < 0 ? "se contrajeron" : "crecieron"}{" "}
          <b>{fP(Math.abs(dVtas))}</b> y el ROE{" "}
          {i2.roe < i1.roe ? "descendió" : "avanzó"} a <b>{fP(i2.roe)}</b> (desde{" "}
          {fP(i1.roe)}). La compañía conserva liquidez sólida ({fX(i2.liq)}) y
          bajo endeudamiento ({fP(i2.end)}), pero presenta capital de trabajo
          inmovilizado: los días de inventario alcanzan <b>{fD(i2.dInv)}</b> y el
          ciclo de conversión de efectivo <b>{fD(cce(D, 2))}</b>.
        </p>
        <table className="rtbl">
          <thead>
            <tr><th>Indicador</th><th>2023</th><th>2024</th><th>2025</th></tr>
          </thead>
          <tbody>
            <tr><td>Liquidez corriente</td><td>{fX(i0.liq)}</td><td>{fX(i1.liq)}</td><td>{fX(i2.liq)}</td></tr>
            <tr><td>Endeudamiento</td><td>{fP(i0.end)}</td><td>{fP(i1.end)}</td><td>{fP(i2.end)}</td></tr>
            <tr><td>Margen neto</td><td>{fP(i0.mn)}</td><td>{fP(i1.mn)}</td><td>{fP(i2.mn)}</td></tr>
            <tr><td>ROE</td><td>{fP(i0.roe)}</td><td>{fP(i1.roe)}</td><td>{fP(i2.roe)}</td></tr>
            <tr><td>Días de inventario</td><td>{fD(i0.dInv)}</td><td>{fD(i1.dInv)}</td><td>{fD(i2.dInv)}</td></tr>
          </tbody>
        </table>

        {/* ===== 7. DIAGNÓSTICO TRIBUTARIO ===== */}
        <h4>7. Diagnóstico Tributario</h4>
        <p>
          La base gravable del primer año (sin acción) es{" "}
          <b>{fmt(primerPagoSin.base)}</b>, sujeta a una tarifa de{" "}
          <b>{fP(primerPagoSin.tar)}</b>, generando un pago a cuenta de{" "}
          <b>{fmt(primerPagoSin.pago)}</b>. De no mediar planificación, esta
          obligación se repite cada ejercicio, totalizando <b>{fmt(pagoSin)}</b>{" "}
          en el horizonte 2026–2028 y convirtiéndose en costo muerto si no se
          recupera vía crédito.
        </p>

        {/* ===== 8. DIAGNÓSTICO SOCIETARIO ===== */}
        <h4>8. Diagnóstico Societario</h4>
        <p>
          Estructura patrimonial al cierre 2025: capital{" "}
          <b>{fmt(D.capital[2])}</b>, reservas <b>{fmt(D.reservas[2])}</b>, otros
          resultados integrales <b>{fmt(D.ori[2])}</b> y resultados acumulados{" "}
          <b>{fmt(D.resAcum[2])}</b>, para un patrimonio total de{" "}
          <b>{fmt(totalPat)}</b>. El elevado peso de los resultados acumulados
          frente al capital ofrece margen amplio para capitalizar o distribuir.
          La reserva legal debe constituirse hasta el <b>50% del capital</b>{" "}
          (referencia {fmt(reservaMin)}); el aumento de capital requiere
          formalización societaria (Junta, escritura y Registro Mercantil).
        </p>

        {/* ===== 9. PAGO HISTÓRICO ===== */}
        <h4>9. Análisis del Pago Históricamente Realizado</h4>
        <p>
          El pago a cuenta de cada año se determina sobre las{" "}
          <b>utilidades retenidas del cierre del ejercicio anterior</b>. El primer
          pago bajo el régimen corresponde a <b>2025</b> (calculado sobre las
          utilidades acumuladas al cierre de 2024). A partir de ahí la obligación
          es recurrente mientras se mantengan utilidades sin distribuir ni
          capitalizar.
        </p>
        <table className="rtbl">
          <thead>
            <tr><th>Año</th><th>Base (acum. cierre anterior)</th><th>Tarifa</th><th>Pago a cuenta</th><th>Estado</th></tr>
          </thead>
          <tbody>
            {historico.map((h) => (
              <tr key={h.anio}>
                <td>{h.anio}</td>
                <td>{fmt(h.base)}</td>
                <td>{fP(h.tar)}</td>
                <td>{fmt(h.pago)}</td>
                <td>Realizado</td>
              </tr>
            ))}
            {R.map((r, i) => (
              <tr key={PROJ[i]}>
                <td>{PROJ[i]}</td>
                <td>{fmt(r.base)}</td>
                <td>{fP(r.tar)}</td>
                <td>{fmt(r.pago)}</td>
                <td>Proyectado ({SCENARIO_NAMES[scn]})</td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* ===== 10. ALTERNATIVAS ===== */}
        <h4>10. Identificación de Alternativas Previas al 31 de Julio</h4>
        <ul>
          <li>
            <b>No hacer nada:</b> se causa y paga el anticipo cada año; máximo
            riesgo de costo muerto.
          </li>
          <li>
            <b>Distribuir dividendos:</b> reduce la base; genera retención del
            impuesto único ({params.retDiv}%) que constituye crédito recuperable.
          </li>
          <li>
            <b>Capitalizar con sustancia:</b> reduce la base hasta el tramo 0%;
            la obligación no nace. Debe respaldarse en activos productivos o
            empleo, no en inventarios.
          </li>
          <li>
            <b>Híbrido (distribución + capitalización):</b> equilibra liquidez del
            accionista y fortalecimiento patrimonial.
          </li>
        </ul>

        {/* ===== 11. MATRIZ DE DECISIÓN ===== */}
        <h4>11. Matriz de Decisión Estratégica</h4>
        <p>
          Comparación de las cuatro decisiones (aplicadas en 2026, sobre la base
          de las utilidades acumuladas al cierre 2025, {fmt(D.resAcum[2])}).
        </p>
        <table className="rtbl">
          <thead>
            <tr>
              <th>Escenario</th>
              <th>Pago a cuenta 2026</th>
              <th>Pago 2026–28</th>
              <th>Retención div. (crédito)</th>
              <th>Costo muerto</th>
              <th>Patrimonio 2028</th>
            </tr>
          </thead>
          <tbody>
            {matriz.map((m) => (
              <tr key={m.key} className={m.key === "e3" ? "ron" : ""}>
                <td>{m.nombre}{m.key === "e3" ? " ◄ sugerido" : ""}</td>
                <td>{fmt(m.pago2026)}</td>
                <td>{fmt(m.pago)}</td>
                <td>{fmt(m.retencion)}</td>
                <td>{fmt(m.muerto)}</td>
                <td>{fmt(m.patrimonio)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="rnote">
          ◄ El escenario 3 (dividendos + capitalización de la diferencia) anula el
          pago de 2026 y a la vez genera retención recuperable y liquidez para el
          accionista. La capitalización debe respaldarse con sustancia económica
          (activos productivos/empleo), no con inventarios.
        </p>

        {/* ===== 12. MODELACIÓN ===== */}
        <h4>12. Modelación Financiera y Tributaria</h4>
        <p>
          <b>Metodología de proyección de los tres estados financieros.</b> El
          modelo 2026–2028 se construye de forma automática a partir del histórico
          (2023–2025), aplicando la siguiente secuencia:
        </p>
        <ol className="rmet">
          {METODOLOGIA_PROYECCION.map((m) => (
            <li key={m.titulo}>
              <b>{m.titulo.replace(/^\d+\s·\s/, "")}.</b> {m.detalle}
            </li>
          ))}
        </ol>
        <p>
          El crecimiento de ventas se toma del histórico real de {emp} cuando es
          positivo; si el histórico no crece, se emplea como respaldo la tasa de
          crecimiento del sector (CIIU{params.sector ? ` ${params.sector}` : ""},{" "}
          {Number(params.tasaSectorial) || 0}% referencial). La depreciación se
          refleja únicamente en EBITDA, PP&E y flujo de caja, por lo que{" "}
          <b>no altera la base del pago a cuenta</b>.
        </p>
        <table className="rtbl">
          <thead>
            <tr><th>Concepto</th>{PROJ.map((y) => <th key={y}>{y}</th>)}</tr>
          </thead>
          <tbody>
            <tr><td>Ventas</td>{R.map((r, i) => <td key={i}>{fmt(r.ventas)}</td>)}</tr>
            <tr><td>Utilidad neta</td>{R.map((r, i) => <td key={i}>{fmt(r.neta)}</td>)}</tr>
            <tr><td>Base gravable</td>{R.map((r, i) => <td key={i}>{fmt(r.base)}</td>)}</tr>
            <tr><td>Tarifa</td>{R.map((r, i) => <td key={i}>{fP(r.tar)}</td>)}</tr>
            <tr><td>Pago a cuenta</td>{R.map((r, i) => <td key={i}>{fmt(r.pago)}</td>)}</tr>
            <tr><td>Crédito vs. IR</td>{R.map((r, i) => <td key={i}>{fmt(r.cIR)}</td>)}</tr>
            <tr><td>Patrimonio</td>{R.map((r, i) => <td key={i}>{fmt(r.patrimonio)}</td>)}</tr>
          </tbody>
        </table>

        {/* ===== 13. DASHBOARD ===== */}
        <h4>13. Dashboard Ejecutivo</h4>
        <div className="tx-split">
          <div className="tx-card">
            <h3>Pago a cuenta por escenario</h3>
            <TaxChart type="bar" data={cScn} options={{ ...moneyOpt, plugins: { legend: { display: false } } }} />
          </div>
          <div className="tx-card">
            <h3>Pago, crédito y riesgo por año</h3>
            <TaxChart type="bar" data={cFlujo} options={moneyOpt} />
          </div>
        </div>

        {/* ===== 14. PLAN DE ACCIÓN ===== */}
        <h4>14. Plan de Acción</h4>
        <table className="rtbl">
          <thead>
            <tr><th>Acción</th><th>Responsable</th><th>Plazo</th></tr>
          </thead>
          <tbody>
            <tr><td>Convocar Junta y aprobar la estrategia (distribución / capitalización)</td><td>Representante legal</td><td>Antes del 31 de julio</td></tr>
            <tr><td>Formalizar aumento de capital (acta, escritura, Registro Mercantil)</td><td>Asesor legal / societario</td><td>Antes del 31 de julio</td></tr>
            <tr><td>Sustentar la capitalización en activos productivos o empleo (no inventarios)</td><td>Gerencia financiera</td><td>Antes del corte</td></tr>
            <tr><td>Documentar respaldo (facturas, avalúo, kardex, nómina)</td><td>Contabilidad</td><td>Permanente</td></tr>
            <tr><td>Aplicar el crédito en retención de dividendos e Impuesto a la Renta</td><td>Tributario</td><td>En la declaración</td></tr>
            <tr><td>Validar parámetros normativos con profesional tributario/legal</td><td>Asesor tributario</td><td>Previo a ejecutar</td></tr>
          </tbody>
        </table>

        {/* ===== 15. CONCLUSIONES ===== */}
        <h4>15. Conclusiones</h4>
        <ul>
          <li>
            La inacción implica un pago recurrente de <b>{fmt(pagoSin)}</b> con
            alto riesgo de costo muerto ({fmt(riesgo)}).
          </li>
          <li>
            El escenario <b>{SCENARIO_NAMES[scn]}</b> reduce el pago a{" "}
            <b>{fmt(pagoAct)}</b> y hace recuperable <b>{fmt(recuperable)}</b>,
            fortaleciendo el patrimonio a <b>{fmt(R[R.length - 1].patrimonio)}</b>.
          </li>
          <li>
            La decisión debe perfeccionarse <b>antes del 31 de julio</b> y
            respaldarse con sustancia económica para resistir fiscalización.
          </li>
          <li className="rwarn">
            Para {emp}: evitar la capitalización vía inventarios
            ({fD(i2.dInv)} de inventario); preferir activos productivos/empleo.
          </li>
        </ul>

        {/* ===== 16. ANEXOS ===== */}
        <h4>16. Anexos</h4>
        <p><b>Anexo A — Parámetros y supuestos</b></p>
        <table className="rtbl">
          <tbody>
            <tr><td>Costo / ventas</td><td>{params.costoR}%</td></tr>
            <tr><td>Gastos operativos / ventas</td><td>{params.gastoR}%</td></tr>
            <tr><td>Tasa Impuesto a la Renta</td><td>{params.irR}%</td></tr>
            <tr><td>Retención impuesto único dividendos</td><td>{params.retDiv}%</td></tr>
          </tbody>
        </table>
        <p><b>Anexo B — Tramos de la tarifa única</b></p>
        <table className="rtbl">
          <thead><tr><th>Base hasta</th><th>Tarifa</th></tr></thead>
          <tbody>
            <tr><td>100.000</td><td>0,00%</td></tr>
            <tr><td>1.000.000</td><td>0,75%</td></tr>
            <tr><td>10.000.000</td><td>1,25%</td></tr>
            <tr><td>100.000.000</td><td>1,75%</td></tr>
            <tr><td>500.000.000</td><td>2,25%</td></tr>
            <tr><td>+500.000.000</td><td>2,50%</td></tr>
          </tbody>
        </table>
        <p className="rnote">
          <b>Anexo C — Glosario:</b> Pago a cuenta = anticipo recuperable;
          Base = utilidades acumuladas − dividendos − capitalización; Costo muerto
          = pago no recuperado por inacción.
        </p>

        <p className="rfoot">
          Documento generado por AuditBrain® Tax › Análisis. Proyección de
          planificación, no auditada. Régimen sujeto a criterios administrativos
          del SRI. Las cifras normativas requieren validación profesional.
        </p>
      </div>
    </section>
  );
}

/* ===================== opciones de charts ===================== */
const BASE_OPT = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: "bottom",
      labels: { font: { family: "Montserrat", size: 10 }, usePointStyle: true, boxWidth: 8 },
    },
  },
};
const Y_MONEY = {
  ticks: { callback: (v) => "$" + f0(v), font: { family: "Roboto", size: 10 } },
  grid: { color: "#eef1f4" },
};
const Y_PCT = {
  ticks: { callback: (v) => v + "%", font: { size: 10 } },
  grid: { color: "#eef1f4" },
};
