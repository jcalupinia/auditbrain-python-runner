import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PortalShell from "../shell/PortalShell.jsx";
import { createJob, getJob, downloadJob } from "../api.js";
import "./flujo.css";

/* ============================================================
   Herramienta Flujo de Efectivo · Dashboard dedicado
   Sube la balanza homologada (Código Super Cías/SRI) del año
   anterior y actual → corre los 8 motores → Excel auditable con
   los estados financieros y el Estado de Flujo (método indirecto).
   Usa el pipeline genérico de jobs (createJob/getJob/downloadJob).
   ============================================================ */

const TOOL_CODE = "FLUJO_EFECTIVO";

const SLOTS = [
  {
    key: "balanza_anterior",
    year: "Año anterior",
    title: "Balanza homologada · comparativo",
    desc: "Saldos del ejercicio anterior, con Código Super Cías y SRI.",
  },
  {
    key: "balanza_actual",
    year: "Año actual",
    title: "Balanza homologada · ejercicio",
    desc: "Saldos del ejercicio corriente, con Código Super Cías y SRI.",
  },
];

const DELIVERABLES = [
  { ico: "◆", t: "Estado de Situación Financiera" },
  { ico: "◆", t: "Estado de Resultados Integral" },
  { ico: "≈", t: "Flujo de Efectivo (indirecto)" },
  { ico: "◇", t: "Evolución del Patrimonio" },
  { ico: "⊘", t: "Movimiento no Efectivo" },
  { ico: "▤", t: "Formulario 101 (SRI)" },
  { ico: "▦", t: "Indicadores financieros" },
  { ico: "✓", t: "Homologación (rastro auditable)" },
];

const MOTOR_STEPS = [
  "Homologando balanza por Código Super Cías",
  "Cuadrando Estado de Situación Financiera",
  "Calculando cascada del Estado de Resultados",
  "Construyendo el Flujo de Efectivo (AF = 0)",
  "Evolución del patrimonio y movimiento no efectivo",
  "Formulario 101 e indicadores",
  "Ensamblando el Excel auditable",
];

const XLSX_MIMES = [
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel.sheet.macroEnabled.12",
  "application/vnd.ms-excel",
].join(",");

function DropZone({ slot, file, onPick, onClear, disabled }) {
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);

  function handleDrop(e) {
    e.preventDefault();
    setDrag(false);
    if (disabled) return;
    const f = e.dataTransfer.files?.[0];
    if (f) onPick(f);
  }

  return (
    <div
      className={`fx-drop${file ? " filled" : ""}${drag ? " drag" : ""}`}
      onClick={() => !file && !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); if (!file && !disabled) setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
      role="button"
      tabIndex={0}
    >
      <input
        ref={inputRef}
        type="file"
        accept={XLSX_MIMES}
        style={{ display: "none" }}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onPick(f); e.target.value = ""; }}
      />
      <span className="fx-drop-ico">
        {file ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
        ) : (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 21h14" /></svg>
        )}
      </span>
      <div className="fx-drop-txt">
        <div className="fx-drop-yr">{slot.year}</div>
        {file ? (
          <div className="fx-drop-file">
            <span>{file.name}</span>
          </div>
        ) : (
          <>
            <div className="fx-drop-t">{slot.title}</div>
            <div className="fx-drop-d">{slot.desc} · arrastra o haz clic</div>
          </>
        )}
      </div>
      {file && !disabled && (
        <button className="fx-drop-x" title="Quitar archivo" onClick={(e) => { e.stopPropagation(); onClear(); }}>×</button>
      )}
    </div>
  );
}

export default function FlujoDashboard() {
  const nav = useNavigate();
  const [files, setFiles] = useState({});          // {slot: File}
  const [phase, setPhase] = useState("idle");       // idle | running | done | error
  const [job, setJob] = useState(null);
  const [runStep, setRunStep] = useState(0);
  const [err, setErr] = useState(null);

  const bothReady = SLOTS.every((s) => files[s.key]);
  const stepUpload = !bothReady;
  const stepRun = bothReady && phase === "idle";

  // animación de motores mientras corre el backend
  useEffect(() => {
    if (phase !== "running") return;
    const id = setInterval(() => setRunStep((s) => Math.min(s + 1, MOTOR_STEPS.length - 1)), 700);
    return () => clearInterval(id);
  }, [phase]);

  // polling del job
  useEffect(() => {
    if (phase !== "running" || !job?.id) return;
    let alive = true;
    const poll = setInterval(async () => {
      try {
        const j = await getJob(job.id);
        if (!alive) return;
        if (j.status === "done") {
          clearInterval(poll);
          setJob(j);
          setRunStep(MOTOR_STEPS.length - 1);
          setPhase("done");
        } else if (j.status === "error" || j.status === "error_partial") {
          clearInterval(poll);
          setErr(j.error_message || "El procesamiento falló.");
          setPhase("error");
        }
      } catch (e) { /* reintenta en el próximo tick */ }
    }, 2000);
    return () => { alive = false; clearInterval(poll); };
  }, [phase, job?.id]);

  async function generar() {
    setErr(null);
    setPhase("running");
    setRunStep(0);
    try {
      const r = await createJob(TOOL_CODE, {
        balanza_anterior: files.balanza_anterior,
        balanza_actual: files.balanza_actual,
      });
      setJob(r);
    } catch (e) {
      setErr(e.message || "No se pudo iniciar el procesamiento.");
      setPhase("error");
    }
  }

  function reset() {
    setPhase("idle"); setJob(null); setErr(null); setRunStep(0);
  }

  const summary = job?.summary_json || {};
  const cuadreEsf = summary.cuadre_esf;
  const cuadreAf = summary.cuadre_af;

  const contextExtras = (
    <div className="pc-ctx-card">
      <div className="pc-ctx-h2">≈ Flujo de Efectivo</div>
      <div className="fx-ctx-prog" style={{ gridColumn: "1/-1" }}>
        <div className="fx-ctx-line"><span className={`pc-dot ${files.balanza_anterior ? "ok" : ""}`} /> Balanza <b>año anterior</b></div>
        <div className="fx-ctx-line"><span className={`pc-dot ${files.balanza_actual ? "ok" : ""}`} /> Balanza <b>año actual</b></div>
        <div className="fx-ctx-line"><span className={`pc-dot ${phase === "done" ? "ok" : ""}`} /> Estados <b>generados</b></div>
      </div>
    </div>
  );

  return (
    <PortalShell
      title="FLUJO DE EFECTIVO"
      subtitle="Estados financieros · método indirecto"
      activeCategory="SOCIETARIAS"
      activeNodeCode={TOOL_CODE}
      contextExtras={contextExtras}
    >
      <div className="fx">
        <button className="fx-linkback" onClick={() => nav("/catalog")}>← Volver al catálogo</button>

        {/* HERO */}
        <section className="fx-hero">
          <div className="fx-hero-eyebrow">Herramientas Societarias</div>
          <h1>Estado de <em>Flujo de Efectivo</em><br />y estados financieros auditables</h1>
          <p>
            Sube la balanza homologada del año anterior y del año actual. El sistema aplica la
            doble codificación <b>Super Cías → estados financieros</b> y <b>SRI → Formulario 101</b>,
            corre los ocho motores de cálculo y entrega un Excel auditable con el Estado de Flujo por
            método indirecto — cuadrado al centavo.
          </p>
          <div className="fx-hero-codes">
            <span className="fx-codepill"><span className="fx-swatch" style={{ background: "var(--accent)" }} /> <b>Super Cías</b> · ESF · ERI · Patrimonio</span>
            <span className="fx-codepill"><span className="fx-swatch" style={{ background: "var(--fx-gold)" }} /> <b>SRI</b> · Formulario 101</span>
          </div>
        </section>

        {/* STEPPER */}
        <div className="fx-steps">
          <div className={`fx-step${stepUpload ? " on" : " done"}`}>
            <span className="fx-step-n">1</span>
            <div><div className="fx-step-t">Sube las balanzas</div><div className="fx-step-d">Año anterior y actual</div></div>
          </div>
          <div className={`fx-step${stepRun ? " on" : phase === "done" ? " done" : ""}`}>
            <span className="fx-step-n">2</span>
            <div><div className="fx-step-t">Genera los estados</div><div className="fx-step-d">Ocho motores + cuadraturas</div></div>
          </div>
          <div className={`fx-step${phase === "done" ? " on" : ""}`}>
            <span className="fx-step-n">3</span>
            <div><div className="fx-step-t">Descarga el Excel</div><div className="fx-step-d">Auditable, listo para revisión</div></div>
          </div>
        </div>

        {/* RESULTADO */}
        {phase === "done" ? (
          <section className="fx-result">
            <div className="fx-badges">
              <div className={`fx-badge ${summary.cuadre_esf_cuadra === false ? "bad" : "ok"}`}>
                <div className="fx-badge-l">Cuadre ESF (A = P + Pat)</div>
                <div className="fx-badge-v">{cuadreEsf != null ? formatMoney(cuadreEsf) : "—"}</div>
                <div className="fx-badge-sub"><span className={`pc-dot ${summary.cuadre_esf_cuadra === false ? "bad" : "ok"}`} /> {summary.cuadre_esf_cuadra === false ? "Revisar" : "Cuadrado"}</div>
              </div>
              <div className={`fx-badge ${summary.cuadre_af_cuadra === false ? "bad" : "ok"}`}>
                <div className="fx-badge-l">Cuadre Flujo (AF)</div>
                <div className="fx-badge-v">{cuadreAf != null ? formatMoney(cuadreAf) : "—"}</div>
                <div className="fx-badge-sub"><span className={`pc-dot ${summary.cuadre_af_cuadra === false ? "bad" : "ok"}`} /> {summary.cuadre_af_cuadra === false ? "Revisar" : "Cuadrado"}</div>
              </div>
              <div className="fx-badge">
                <div className="fx-badge-l">Cuentas procesadas</div>
                <div className="fx-badge-v">{(summary.filas_actual ?? "—")}</div>
                <div className="fx-badge-sub">año actual · {summary.filas_anterior ?? "—"} anterior</div>
              </div>
            </div>

            <div className="fx-dl">
              <div>
                <div className="fx-dl-t">Excel auditable listo</div>
                <div className="fx-dl-d">9 hojas · RESUMEN, ESF, ERI, Flujo, Patrimonio, No Efectivo, F-101, Indicadores + Homologación.</div>
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <button className="pc-btn secondary" onClick={reset}>Generar otro</button>
                <button className="fx-cta" onClick={() => downloadJob(job.id).catch((e) => setErr(e.message))}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></svg>
                  Descargar Excel
                </button>
              </div>
            </div>
          </section>
        ) : (
          <div className="fx-cols">
            {/* IZQUIERDA: uploads / procesamiento */}
            <div className="fx-card">
              <div className="fx-card-h">
                <b>{phase === "running" ? "Procesando" : "Cargar balanzas"}</b>
                <span className="fx-tag">{phase === "running" ? "MOTORES" : "2 archivos · .xlsx / .xlsm"}</span>
              </div>
              <div className="fx-card-b">
                {phase === "running" ? (
                  <div className="fx-run">
                    {MOTOR_STEPS.map((s, i) => (
                      <div key={i} className={`fx-run-row${i < runStep ? " ok" : i === runStep ? " act" : ""}`}>
                        <span className="fx-run-dot">{i < runStep ? "✓" : ""}</span>
                        {s}
                      </div>
                    ))}
                  </div>
                ) : (
                  <>
                    <div className="fx-drops">
                      {SLOTS.map((s) => (
                        <DropZone
                          key={s.key}
                          slot={s}
                          file={files[s.key] || null}
                          onPick={(f) => setFiles((p) => ({ ...p, [s.key]: f }))}
                          onClear={() => setFiles((p) => { const n = { ...p }; delete n[s.key]; return n; })}
                        />
                      ))}
                    </div>
                    {err && <div className="fx-error" style={{ marginTop: 14 }}>{err}</div>}
                    <div className="fx-actions">
                      <button className="fx-cta" disabled={!bothReady} onClick={generar}>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 5 5L20 7" /></svg>
                        Generar estados financieros
                      </button>
                      <span className="fx-hint">{bothReady ? "Ambas balanzas cargadas" : "Sube las dos balanzas para continuar"}</span>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* DERECHA: qué recibes */}
            <div className="fx-card">
              <div className="fx-card-h">
                <b>Qué vas a recibir</b>
                <span className="fx-tag">9 HOJAS</span>
              </div>
              <div className="fx-card-b">
                <div className="fx-deliv">
                  {DELIVERABLES.map((d) => (
                    <div key={d.t} className="fx-deliv-item">
                      <span className="fx-di-ico">{d.ico}</span>
                      <b>{d.t}</b>
                    </div>
                  ))}
                </div>
                <div className="fx-deliv-note">
                  Cada valor es <b>trazable</b>: la hoja de Homologación muestra de qué cuentas sale cada
                  saldo, y las cuadraturas (A = P + Pat y AF = 0) se presentan con semáforo. Firmado por
                  <b> AuditConsulting Auditores</b> · AUDIT-IA.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </PortalShell>
  );
}

function formatMoney(n) {
  const v = Number(n) || 0;
  return v.toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
