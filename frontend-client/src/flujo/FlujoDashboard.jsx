import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PortalShell from "../shell/PortalShell.jsx";
import { createJob, getJob, downloadJobArtifact } from "../api.js";

/* ============================================================
   Herramienta Flujo de Efectivo · Dashboard dedicado
   Mismo formato que el ICT: barra de "Subir documentos" con
   chips, acciones (Procesar / Descargar), barra de progreso y
   grilla de tarjetas numeradas (una por sección del estado).
   Usa el pipeline genérico de jobs (createJob/getJob) y descarga
   cada artefacto por separado (downloadJobArtifact).
   ============================================================ */

const TOOL_CODE = "FLUJO_EFECTIVO";

const XLSX_MIMES = [
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel.sheet.macroEnabled.12",
  "application/vnd.ms-excel",
].join(",");

// Slots de subida (2 balanzas homologadas).
const UPLOADS = [
  { key: "balanza_anterior", icon: "📄", label: "Balanza año anterior" },
  { key: "balanza_actual", icon: "📊", label: "Balanza año actual" },
];

// Nombres de artefacto que produce el processor (backend).
const ART = {
  excel: "FlujoEfectivo.xlsx",
  esf: "EstadoDeSituacionFinanciera.txt",
  eri: "EstadoDeResultadoIntegral.txt",
  f101: "Formulario101.xml",
  zip: "FlujoEfectivo_completo.zip",
};

// Secciones en el ORDEN del índice del modelo (tarjetas numeradas).
const SECTIONS = [
  { n: "2", code: "ESF", name: "Estado de Situación Financiera", desc: "Balance por Código Super Cías · TXT de envío", dl: "txt", art: ART.esf },
  { n: "3", code: "ERI", name: "Estado de Resultados Integral", desc: "Cascada de resultados · TXT de envío", dl: "txt", art: ART.eri },
  { n: "4", code: "PAT", name: "Evolución del Patrimonio", desc: "Componentes del patrimonio · en el Excel", dl: "soon" },
  { n: "5", code: "FLU", name: "Estado de Flujo de Efectivo", desc: "Método indirecto (AF = 0) · en el Excel", dl: "soon" },
  { n: "6", code: "MNE", name: "Movimiento no Efectivo", desc: "Depreciación / amortización / deterioro", dl: "excel" },
  { n: "7·8", code: "MAP", name: "Homologación (Mapeo)", desc: "Cuentas · Super Cías · SRI · saldo", dl: "excel" },
  { n: "10", code: "101", name: "Formulario 101", desc: "Casilleros por Código SRI · XML", dl: "xml", art: ART.f101 },
  { n: "14", code: "IND", name: "Indicadores financieros", desc: "Razón corriente, endeudamiento, ROE…", dl: "excel" },
];

const MOTOR_STEPS = [
  "Homologando balanza por Código Super Cías",
  "Cuadrando Estado de Situación Financiera",
  "Cascada del Estado de Resultados",
  "Flujo de Efectivo (método indirecto)",
  "Patrimonio y movimiento no efectivo",
  "Formulario 101 e indicadores",
  "Ensamblando el Excel auditable",
];

function UploadChip({ upload, file, onPick, onClear, disabled }) {
  const ref = useRef(null);
  return (
    <>
      <input
        ref={ref}
        type="file"
        accept={XLSX_MIMES}
        style={{ display: "none" }}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onPick(f); e.target.value = ""; }}
      />
      <button
        className={file ? "pc-chip on" : "pc-chip"}
        disabled={disabled}
        onClick={() => { if (!file) ref.current?.click(); }}
        title={file ? file.name : `Subir ${upload.label}`}
      >
        <span>{upload.icon}</span>
        <span>{file ? `✓ ${upload.label}` : `↑ ${upload.label}`}</span>
        {file && (
          <span
            onClick={(e) => { e.stopPropagation(); onClear(); }}
            title="Quitar archivo"
            style={{ marginLeft: 4, cursor: "pointer", opacity: 0.8 }}
          >×</span>
        )}
      </button>
    </>
  );
}

export default function FlujoDashboard() {
  const nav = useNavigate();
  const [files, setFiles] = useState({});
  const [phase, setPhase] = useState("idle");   // idle | running | done | error
  const [job, setJob] = useState(null);
  const [runStep, setRunStep] = useState(0);
  const [selected, setSelected] = useState(null);
  const [err, setErr] = useState(null);

  const uploadsDone = UPLOADS.filter((u) => files[u.key]).length;
  const bothReady = uploadsDone === UPLOADS.length;
  const isDone = phase === "done";
  const summary = job?.summary_json || {};
  const percent = isDone ? 100 : phase === "running" ? 60 : Math.round((uploadsDone / UPLOADS.length) * 40);

  useEffect(() => {
    if (phase !== "running") return;
    const id = setInterval(() => setRunStep((s) => Math.min(s + 1, MOTOR_STEPS.length - 1)), 650);
    return () => clearInterval(id);
  }, [phase]);

  useEffect(() => {
    if (phase !== "running" || !job?.id) return;
    let alive = true;
    const poll = setInterval(async () => {
      try {
        const j = await getJob(job.id);
        if (!alive) return;
        if (j.status === "done") { clearInterval(poll); setJob(j); setPhase("done"); }
        else if (j.status === "error" || j.status === "error_partial") {
          clearInterval(poll); setErr(j.error_message || "El procesamiento falló."); setPhase("error");
        }
      } catch (e) { /* reintenta */ }
    }, 2000);
    return () => { alive = false; clearInterval(poll); };
  }, [phase, job?.id]);

  async function handleProcess() {
    setErr(null); setRunStep(0); setPhase("running");
    try {
      const r = await createJob(TOOL_CODE, {
        balanza_anterior: files.balanza_anterior,
        balanza_actual: files.balanza_actual,
      });
      setJob(r);
    } catch (e) { setErr(e.message || "No se pudo iniciar."); setPhase("error"); }
  }

  function handleReset() {
    setFiles({}); setJob(null); setPhase("idle"); setRunStep(0); setSelected(null); setErr(null);
  }

  const dl = (name) => downloadJobArtifact(job.id, name).catch((e) => setErr(e.message));
  function tileDownload(s) {
    if (!isDone) return;
    if (s.dl === "txt" || s.dl === "xml") dl(s.art);
    else dl(ART.excel);
  }
  function statusLabel(s) {
    if (!isDone) return "Pendiente";
    if (s.dl === "txt") return "TXT ⤓";
    if (s.dl === "xml") return "XML ⤓";
    if (s.dl === "soon") return "Fase B";
    return "Excel ⤓";
  }

  const contextExtras = (
    <div className="pc-ctx-card">
      <div className="pc-ctx-h2">≈ Flujo de Efectivo</div>
      <div className="pc-ctx-k">Balanzas</div>
      <div className="pc-ctx-v">{uploadsDone}/2 subidas</div>
      <div className="pc-ctx-k">Estados</div>
      <div className="pc-ctx-v">{isDone ? "8 generados" : "—"}</div>
      <div className="pc-ctx-k">Cuadre ESF</div>
      <div className="pc-ctx-v">{isDone ? formatMoney(summary.cuadre_esf) : "—"}</div>
      <div className="pc-ctx-k">Flujo AF</div>
      <div className="pc-ctx-v">{isDone ? formatMoney(summary.cuadre_af) : "—"}</div>
    </div>
  );

  const sel = selected != null ? SECTIONS.find((s) => s.code === selected) : null;

  return (
    <PortalShell
      title="FLUJO DE EFECTIVO"
      subtitle="Estados financieros · método indirecto"
      activeCategory="SOCIETARIAS"
      activeNodeCode={TOOL_CODE}
      contextExtras={contextExtras}
    >
      <div className="pc-panel">
        <header className="pc-panel-h">
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <span className="pc-code">FLUJO</span>
            <span className="pc-panel-t">Estados financieros y Flujo de Efectivo</span>
          </div>
          <span className="pc-panel-m">
            {isDone ? "8/8 SECCIONES" : `${uploadsDone}/2 BALANZAS`}
          </span>
        </header>

        <div className="pc-panel-b">
          <button className="pc-btn secondary" onClick={() => nav("/catalog")} style={{ marginBottom: 14 }}>
            ← Volver al catálogo
          </button>

          {/* BARRA 1: acciones */}
          <div className="pc-scenarios">
            <span className="pc-scenarios-l">Doble codificación</span>
            <span className="pc-chip on" style={{ cursor: "default" }}>Super Cías · SRI</span>
            <div style={{ flex: 1 }} />
            <button
              className="pc-chip accent"
              onClick={handleProcess}
              disabled={!bothReady || phase === "running"}
              title={bothReady ? "Corre los 8 motores y genera los estados" : "Sube las 2 balanzas"}
              style={{ fontWeight: 700 }}
            >
              {phase === "running" ? "⏳ Procesando…" : "▶ Procesar"}
            </button>
            <button
              className="pc-chip accent"
              onClick={() => dl(ART.excel)}
              disabled={!isDone}
              title={isDone ? "Excel auditable de 9 hojas" : "Procesa primero"}
              style={{ fontWeight: 700 }}
            >
              📤 Descargar Excel
            </button>
            <button
              className="pc-chip"
              onClick={() => dl(ART.zip)}
              disabled={!isDone}
              title={isDone ? "TXT + XML + Excel en un ZIP" : "Procesa primero"}
            >
              🗂 Descargar todo (ZIP)
            </button>
            <button className="pc-chip danger" onClick={handleReset} title="Empezar de nuevo">
              🔄 Nuevo
            </button>
          </div>

          {/* BARRA 2: subir documentos */}
          <div className="pc-scenarios" style={{
            padding: "12px 14px", background: "var(--panel-2)",
            border: "1px solid var(--line)", borderRadius: 10, marginTop: 6,
          }}>
            <span className="pc-scenarios-l" style={{ color: "var(--accent)" }}>📂 Subir documentos</span>
            {UPLOADS.map((u) => (
              <UploadChip
                key={u.key}
                upload={u}
                file={files[u.key] || null}
                disabled={phase === "running" || isDone}
                onPick={(f) => setFiles((p) => ({ ...p, [u.key]: f }))}
                onClear={() => setFiles((p) => { const n = { ...p }; delete n[u.key]; return n; })}
              />
            ))}
          </div>

          {/* Barra de progreso */}
          <div style={{ marginTop: 16, background: "var(--panel-2)", border: "1px solid var(--line)", borderRadius: 8, height: 8, overflow: "hidden" }}>
            <div style={{ width: `${percent}%`, height: "100%", background: "var(--accent)", transition: "width 0.3s" }} />
          </div>
          <div style={{ fontSize: 11, color: "var(--text-soft)", marginTop: 6 }}>
            <b style={{ color: "var(--accent)" }}>{isDone ? 8 : 0}</b> de 8 secciones generadas ·
            <b style={{ color: "var(--accent)", marginLeft: 6 }}>{uploadsDone}</b> de 2 balanzas subidas
          </div>

          {err && (
            <div style={{ marginTop: 14, padding: "12px 14px", background: "rgba(255,93,93,0.08)", border: "1px solid rgba(255,93,93,0.4)", borderRadius: 10, color: "var(--danger)", fontSize: 13 }}>
              {err}
            </div>
          )}

          {phase === "running" && (
            <div style={{ marginTop: 14, padding: "12px 14px", background: "var(--accent-dim)", border: "1px solid rgba(52,211,106,0.45)", borderRadius: 10, fontSize: 13, color: "var(--text-soft)" }}>
              <span style={{ color: "var(--accent)", fontWeight: 700 }}>▶ {MOTOR_STEPS[runStep]}…</span>
            </div>
          )}

          {bothReady && phase === "idle" && (
            <div style={{ marginTop: 14, padding: "12px 14px", background: "var(--accent-dim)", border: "1px solid rgba(52,211,106,0.45)", borderRadius: 10, fontSize: 13, display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ fontSize: 22 }}>✨</span>
              <div>
                <div style={{ color: "var(--accent)", fontWeight: 700 }}>Listo para procesar</div>
                <div style={{ color: "var(--text-soft)", fontSize: 12, marginTop: 2 }}>
                  Las 2 balanzas están cargadas. Pulsa <b style={{ color: "var(--accent)" }}>▶ Procesar</b> para
                  generar los estados y habilitar las descargas por sección.
                </div>
              </div>
            </div>
          )}

          {/* GRID DE SECCIONES */}
          <div style={{ marginTop: 18, marginBottom: 8, fontSize: 11, color: "var(--text-soft)", letterSpacing: 0.06 }}>
            {isDone ? "Click en una sección para descargar su archivo:" : "Secciones que se generarán (orden del modelo):"}
          </div>
          <div className="pc-tiles">
            {SECTIONS.map((s) => {
              const ready = isDone && s.dl !== "soon";
              return (
                <button
                  key={s.code}
                  className={`pc-tile${ready ? " done" : ""}${selected === s.code ? " on" : ""}`}
                  onClick={() => { setSelected(s.code); tileDownload(s); }}
                  disabled={phase === "running"}
                >
                  <span className={`pc-tile-n${isDone ? " done" : " dim"}`}>{s.n}</span>
                  <div className="pc-tile-txt">
                    <span className="pc-tile-t">{s.name}</span>
                    <span className="pc-tile-d">{s.desc}</span>
                  </div>
                  <span className="pc-tile-st" style={ready ? { color: "var(--accent)" } : {}}>{statusLabel(s)}</span>
                </button>
              );
            })}
          </div>

          {sel && (
            <div style={{ marginTop: 14, padding: "12px 14px", background: "var(--panel-2)", border: "1px solid var(--line)", borderRadius: 10, fontSize: 12.5, color: "var(--text-soft)" }}>
              <b style={{ color: "var(--text)" }}>Sección {sel.n} · {sel.name}.</b>{" "}
              {sel.dl === "soon"
                ? "El TXT oficial (códigos 95xx / 99xx) llega en la Fase B; sus valores ya están en el Excel."
                : isDone
                  ? "Descarga iniciada. Volvé a hacer clic para bajarla de nuevo."
                  : "Se habilitará al procesar."}
            </div>
          )}
        </div>
      </div>
    </PortalShell>
  );
}

function formatMoney(n) {
  if (n == null) return "—";
  return (Number(n) || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
