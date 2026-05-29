import { useMemo, useState } from "react";
import { extractTaxPlan, exportTaxPlan, downloadTaxPlantilla } from "../api.js";
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
} from "./seed.js";
import {
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
  const [D, setD] = useState(() => clone(EX));
  const [CTRL, setCTRL] = useState(() => clone(DEFAULT_CTRL));
  const [scn, setScn] = useState("mix");
  const [params, setParams] = useState(() => ({ ...DEFAULT_PARAMS }));
  const [section, setSection] = useState("datos");
  const [ingest, setIngest] = useState(null); // null | "f101" | "resumido"

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
          <button className="tx-btn" onClick={() => window.print()}>
            🖨 PDF
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
        {section === "datos" && <SecDatos params={params} setText={setText} />}
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
        {section === "proyectado" && <SecProyectado D={D} R={R} P={P} />}
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
          <SecInforme D={D} R={R} i1={i1} i2={i2} scComp={scComp} scn={scn} params={params} />
        )}
      </div>
    </div>
  );
}

/* ============ panel de ingesta (carga 101 / balance resumido) ============ */
function IngestPanel({ kind, onClose, onExtracted }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const f101 = kind === "f101";

  const process = async () => {
    if (!file) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const res = await extractTaxPlan(kind, file);
      onExtracted?.(res);
      setResult(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
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
            ? "Cargar Formulario 101 (SRI)"
            : "Cargar balance resumido (informe auditoría externa)"}
        </h3>
        <button className="tx-x" onClick={onClose}>
          ✕
        </button>
      </div>
      <p className="tx-muted">
        {f101
          ? "Sube el PDF del Formulario 101. El sistema extraerá los casilleros y poblará el Estado de Situación Financiera y el Estado de Resultados."
          : "Sube el balance resumido en la plantilla definida (.xlsx). Se mapeará a los mismos esquemas ESF / ER."}
      </p>
      {!f101 && (
        <button className="tx-btn ghost" onClick={getPlantilla}>
          ⬇ Descargar plantilla en blanco
        </button>
      )}
      <input
        type="file"
        accept={f101 ? "application/pdf" : ".xlsx,.xls"}
        onChange={(e) => {
          setFile(e.target.files?.[0] || null);
          setResult(null);
          setError("");
        }}
      />
      {file && <div className="tx-muted small">Seleccionado: {file.name}</div>}
      <div className="tx-ingest-actions">
        <button className="tx-btn" onClick={process} disabled={!file || busy}>
          {busy ? "Procesando…" : "Procesar y cargar"}
        </button>
      </div>
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
            Datos cargados en <b>Estados financieros</b>.
            {result.anio_detectado ? ` Año detectado: ${result.anio_detectado}.` : ""}
            {result.warnings?.length > 0 && (
              <ul className="tx-warnlist">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
            <div className="tx-muted small">
              Revisa y ajusta las celdas azules antes de usar las cifras.
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
function SecDatos({ params, setText }) {
  const F = [
    ["empresa", "Nombre / razón social", "text", "Nombre de la compañía"],
    ["ruc", "RUC", "text", "13 dígitos"],
    ["repLegal", "Representante legal", "text", "Para dirigir el informe"],
    ["fechaCorte", "Fecha de corte", "date", "ej. 31 de julio"],
    ["fechaAnalisis", "Fecha del análisis", "date", "fecha del cálculo"],
  ];
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
    ["Crecimiento ventas (%)", "g", true],
    ["Dividendos (ene–jul)", "div", false],
    ["Capitalización (ene–jul)", "cap", false],
  ];
  return (
    <section>
      <div className="tx-h1">Cálculo del impuesto — pago a cuenta</div>
      <p className="tx-lead">
        Depuración de la base y aplicación de la tarifa única. Las palancas por
        año (dividendos / capitalización antes del 31 de julio) gobiernan toda
        la planificación.
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

function SecProyectado({ D, R, P }) {
  return (
    <section>
      <div className="tx-h1">Estados financieros proyectados 2026–2028</div>
      <p className="tx-lead">
        Histórico 2023–2025 y proyección 2026–2028 (columnas{" "}
        <span className="proj-txt">P</span>) bajo el escenario seleccionado. El
        patrimonio rueda con las decisiones; la capitalización reclasifica
        resultados acumulados a capital.
      </p>
      <div className="tx-card">
        <h3>Estado de Resultados</h3>
        <div className="tx-scroll">
          <table className="tx-tbl">
            <YHead title="Estado de Resultados (USD)" />
            <tbody>
              <RowHP label="Ventas" hist={D.ventas} proj={P("ventas")} />
              <RowHP label="(−) Costo" hist={D.costo} proj={P("costo")} neg />
              <RowHP label="Utilidad bruta" hist={[0, 1, 2].map((c) => ub(D, c))} proj={P("ub")} cls="sub" />
              <RowHP label="(−) Gastos operativos" hist={D.gAdmin} proj={P("gAdmin")} neg />
              <RowHP label="Utilidad operativa" hist={[0, 1, 2].map((c) => ebit(D, c))} proj={P("ebit")} cls="sub" />
              <RowHP label="Impuesto renta causado" hist={D.irCausado} proj={P("irCausado")} neg />
              <RowHP label="(−) Crédito tributario aplicado" hist={[0, 0, 0]} proj={P("cIR")} cls="hl" neg />
              <RowHP label="= Impuesto renta a pagar" hist={D.irCausado} proj={P("irAP")} cls="sub" neg />
              <RowHP label="Utilidad neta" hist={[0, 1, 2].map((c) => neta(D, c))} proj={P("neta")} cls="tot" />
            </tbody>
          </table>
        </div>
        <p className="tx-legend">
          Note la línea{" "}
          <b className="amber">“(−) Crédito tributario aplicado”</b>: el anticipo
          que reduce el IR a pagar.
        </p>
      </div>
      <div className="tx-card">
        <h3>Estado de Situación Financiera</h3>
        <div className="tx-scroll">
          <table className="tx-tbl">
            <YHead title="Estado de Situación (USD)" />
            <tbody>
              <RowHP label="Total activo" hist={[0, 1, 2].map((c) => tActivo(D, c))} proj={P("activo")} cls="sub" />
              <RowHP label="Total pasivo" hist={[0, 1, 2].map((c) => tPasivo(D, c))} proj={P("pasivo")} cls="sub" />
              <RowHP label="Capital social" hist={D.capital} proj={P("capital")} />
              <RowHP label="Resultados acumulados" hist={D.resAcum} proj={P("resAcum")} />
              <RowHP label="Total patrimonio" hist={[0, 1, 2].map((c) => tPat(D, c))} proj={P("patrimonio")} cls="tot" />
              <RowHP label="Memo: crédito en riesgo acum." hist={[0, 0, 0]} proj={P("riesgo")} cls="hl" />
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
function SecInforme({ D, R, i1, i2, scComp, scn, params }) {
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
  const pagoSin = scComp.sin;
  const pagoAct = R.reduce((a, r) => a + r.pago, 0);
  const credIR = R.reduce((a, r) => a + r.cIR, 0);
  const ahorro = pagoSin - pagoAct;
  const riesgo = R[R.length - 1].riesgo;
  const dVtas = (i2.V - i1.V) / i1.V;
  return (
    <section>
      <div className="tx-report">
        <div className="rcover">
          <div className="rk">
            AuditBrain · Executive Advisory · Tax Advisory
          </div>
          <h2>Planificación tributaria sobre utilidades no distribuidas</h2>
          <div className="remp">{emp}</div>
          {ruc && <div className="rdate">RUC: {ruc}</div>}
          {rep && (
            <div className="rdate">{rep} · Representante legal</div>
          )}
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

        <h4>Índice</h4>
        <ol className="idx">
          <li>Introducción</li>
          <li>Alcance del servicio</li>
          <li>Diagnóstico financiero</li>
          <li>Estrategia tributaria</li>
          <li>Soluciones y escenarios</li>
          <li>Ahorro y recomendaciones</li>
        </ol>

        <h4>1. Introducción</h4>
        {rep && (
          <p>
            Estimado(a) señor(a) <b>{rep}</b>, en su calidad de representante
            legal de {emp}, ponemos a su consideración el presente análisis.
          </p>
        )}
        <p>
          Desde septiembre de 2025 rige en Ecuador el{" "}
          <b>pago a cuenta sobre las utilidades no distribuidas</b>, un anticipo
          anual que grava a las sociedades que mantienen utilidades acumuladas
          sin distribuir ni capitalizar al 31 de julio de cada año. {emp}{" "}
          mantiene utilidades acumuladas por <b>{fmt(D.resAcum[2])}</b>, lo que
          la expone a una obligación recurrente. El accionista busca no soportar
          este desembolso de forma permanente; el presente análisis estructura,
          con evidencia financiera y tributaria, cómo evitar legítimamente que
          la obligación nazca o cómo convertir cada dólar pagado en crédito
          plenamente recuperable.
        </p>

        <h4>2. Alcance del servicio</h4>
        <p>
          El componente comprende: diagnóstico financiero 2023–2025,
          determinación de la base y del pago a cuenta bajo la tarifa única
          vigente, cálculo de la retención del impuesto único a los dividendos,
          modelación del crédito tributario aplicable a la reducción del
          Impuesto a la Renta, proyección de estados financieros 2026–2028 y
          recomendaciones ejecutivas. La herramienta es reutilizable para
          cualquier empresa del portafolio mediante la carga de sus estados
          financieros.
        </p>

        <h4>3. Diagnóstico financiero</h4>
        <p>
          En 2025 las ventas {dVtas < 0 ? "se contrajeron" : "crecieron"}{" "}
          <b>{fP(Math.abs(dVtas))}</b> y el ROE{" "}
          {i2.roe < i1.roe ? "descendió" : "avanzó"} a <b>{fP(i2.roe)}</b>{" "}
          (desde {fP(i1.roe)}). La compañía conserva liquidez sólida (
          {fX(i2.liq)}) y bajo endeudamiento ({fP(i2.end)}), pero presenta
          capital de trabajo inmovilizado: los días de inventario alcanzan{" "}
          <b>{fD(i2.dInv)}</b> y el ciclo de conversión de efectivo{" "}
          <b>{fD(cce(D, 2))}</b>. El balance es fuerte; el desafío es operativo y
          de eficiencia.
        </p>

        <h4>4. Estrategia tributaria</h4>
        <p>
          La planificación no se orienta a “no pagar”, sino a (i){" "}
          <b>evitar que la obligación nazca</b> mediante capitalización con
          sustancia antes del 31 de julio, y (ii){" "}
          <b>convertir el pago en crédito recuperable</b> contra la retención de
          dividendos y el Impuesto a la Renta, evitando que se transforme en
          costo muerto por inacción durante dos ejercicios. La combinación
          recomendada equilibra liquidez del accionista (distribución parcial) y
          fortalecimiento patrimonial (capitalización).
        </p>

        <h4>5. Soluciones y escenarios</h4>
        <p>
          Bajo el escenario <b>{SCENARIO_NAMES[scn]}</b>, el pago a cuenta
          acumulado 2026–2028 es <b>{fmt(pagoAct)}</b>, frente a{" "}
          <b>{fmt(pagoSin)}</b> sin planificación. Del anticipo,{" "}
          <b>{fmt(credIR)}</b> se aplican como crédito que reduce directamente el
          Impuesto a la Renta, y el resto se recupera por retención de
          dividendos y devolución. El patrimonio proyectado al 2028 asciende a{" "}
          <b>{fmt(R[R.length - 1].patrimonio)}</b>.
        </p>

        <h4>6. Ahorro y recomendaciones</h4>
        <ul>
          <li>
            <b>Ahorro / diferimiento estimado:</b> {fmt(ahorro)} frente a no
            actuar; crédito en riesgo bajo el escenario óptimo: {fmt(riesgo)}.
          </li>
          <li>
            Perfeccionar la operación societaria (Junta, acta, aumento de
            capital, Registro Mercantil) <b>antes del 31 de julio</b>.
          </li>
          <li>
            Respaldar la capitalización con{" "}
            <b>activos productivos nuevos o empleo ≥5%</b>. Para {emp}, evitar la
            vía inventarios: con {fD(i2.dInv)} de inventario y ventas a la baja,
            agravaría la operación y es foco probable de fiscalización del SRI.
          </li>
          <li>
            Documentar el sustento (facturas, avalúo, kardex) y aplicar el
            crédito en la retención de dividendos y el Impuesto a la Renta dentro
            de los plazos.
          </li>
          <li>
            <b>Revisión humana requerida:</b> tarifa, retención de dividendos,
            reserva legal y tasa de IR deben validarse con un profesional
            tributario y legal antes de ejecutar.
          </li>
        </ul>
        <p className="rfoot">
          Documento generado por AuditBrain® Tax › Análisis. Proyección de
          planificación, no auditada. Régimen sujeto a criterios administrativos
          del SRI.
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
