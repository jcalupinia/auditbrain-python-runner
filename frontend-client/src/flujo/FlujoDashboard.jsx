import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PortalShell from "../shell/PortalShell.jsx";
import { createJob, getJob, downloadJobArtifact, getJobArtifactJson } from "../api.js";
import HojaTrabajo from "./HojaTrabajo.jsx";
import "./flujo.css";

/* ============================================================
   Herramienta Flujo de Efectivo · Dashboard dedicado
   Mismo formato que el ICT: barra "Subir documentos" con 4 chips,
   acciones (Procesar / Descargar / ZIP / Nuevo), barra de progreso
   y grilla de 9 tarjetas numeradas (una por sección). Click en una
   tarjeta descarga su archivo. Usa el pipeline genérico de jobs.
   ============================================================ */

const TOOL_CODE = "FLUJO_EFECTIVO";

// Enlace al GPT del usuario (ChatGPT). Abre el asistente en la cuenta de cada
// usuario — no consume tokens de la plataforma. (Macro AbrirAuditIA del modelo.)
const ASISTENTE_IA_URL =
  "https://chatgpt.com/g/g-67c5274cf9fc8191aa0e732f2048bb4a-asistente-virtual-audit-ia";

const XLSX_MIMES = [
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel.sheet.macroEnabled.12",
  "application/vnd.ms-excel",
].join(",");

// Chips de subida (los 2 primeros son obligatorios; el plan de cuentas, opcional).
const UPLOADS = [
  { key: "balanza_anterior", icon: "📄", label: "Balanza anterior", req: true },
  { key: "balanza_actual", icon: "📊", label: "Balanza actual", req: true },
  { key: "plan_cuentas", icon: "🧾", label: "Plan de cuentas Super/SRI", req: false },
];

// Nombres de artefacto que produce el processor (backend).
const ART = {
  excel: "FlujoEfectivo.xlsx",
  esf: "EstadoDeSituacionFinanciera.txt",
  eri: "EstadoDeResultadoIntegral.txt",
  f101: "Formulario101.xml",
  zip: "FlujoEfectivo_completo.zip",
};

// 9 secciones (grilla 3×3), descripciones cortas al estilo ICT.
const SECTIONS = [
  { n: "1", code: "ESF", name: "Situación Financiera", desc: "Balance por Código Super Cías", dl: "txt", art: ART.esf },
  { n: "2", code: "ERI", name: "Resultados Integral", desc: "Cascada de resultados", dl: "txt", art: ART.eri },
  { n: "3", code: "PAT", name: "Evolución Patrimonio", desc: "Componentes del patrimonio", dl: "soon" },
  { n: "4", code: "FLU", name: "Flujo de Efectivo", desc: "Método indirecto · AF = 0", dl: "soon" },
  { n: "5", code: "MNE", name: "Movimiento no Efectivo", desc: "Depreciación y deterioros", dl: "excel" },
  { n: "6", code: "MAP", name: "Homologación", desc: "Cuentas · Super Cías · SRI", dl: "excel" },
  { n: "7", code: "101", name: "Formulario 101", desc: "Casilleros por Código SRI", dl: "xml", art: ART.f101 },
  { n: "8", code: "NOT", name: "Notas a los Estados", desc: "Desglose por rubro", dl: "soon" },
  { n: "9", code: "IND", name: "Indicadores", desc: "Razón corriente, ROE…", dl: "excel" },
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
        {!upload.req && !file && <span style={{ fontSize: 9, opacity: 0.7 }}>opcional</span>}
        {file && (
          <span onClick={(e) => { e.stopPropagation(); onClear(); }} title="Quitar" style={{ marginLeft: 4, cursor: "pointer", opacity: 0.8 }}>×</span>
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
  const [previews, setPreviews] = useState(null);
  const [err, setErr] = useState(null);

  const reqDone = UPLOADS.filter((u) => u.req).every((u) => files[u.key]);
  const docsUp = UPLOADS.filter((u) => files[u.key]).length;
  const isDone = phase === "done";
  const summary = job?.summary_json || {};
  const percent = isDone ? 100 : phase === "running" ? 60 : (reqDone ? 40 : docsUp * 15);

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

  // al terminar, trae las tablas de vista previa (una sola vez)
  useEffect(() => {
    if (phase !== "done" || !job?.id) return;
    let alive = true;
    getJobArtifactJson(job.id, "previews.json")
      .then((p) => { if (alive) { setPreviews(p); setSelected("ESF"); } })
      .catch(() => { /* la preview es opcional */ });
    return () => { alive = false; };
  }, [phase, job?.id]);

  async function handleProcess() {
    setErr(null); setRunStep(0); setPhase("running");
    try {
      const fileMap = {};
      UPLOADS.forEach((u) => { if (files[u.key]) fileMap[u.key] = files[u.key]; });
      const r = await createJob(TOOL_CODE, fileMap);
      setJob(r);
    } catch (e) { setErr(e.message || "No se pudo iniciar."); setPhase("error"); }
  }

  function handleReset() {
    setFiles({}); setJob(null); setPhase("idle"); setRunStep(0); setSelected(null); setErr(null);
  }

  const dl = (name) => downloadJobArtifact(job.id, name).catch((e) => setErr(e.message));
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
      <div className="pc-ctx-k">Documentos</div>
      <div className="pc-ctx-v">{docsUp} subidos</div>
      <div className="pc-ctx-k">Secciones</div>
      <div className="pc-ctx-v">{isDone ? "9 generadas" : "—"}</div>
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
      <div className="pc-panel fx3d">
        <header className="pc-panel-h">
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <span className="pc-code">FLUJO</span>
            <span className="pc-panel-t">Estados financieros y Flujo de Efectivo</span>
          </div>
          <span className="pc-panel-m">{isDone ? "9/9 SECCIONES" : `${docsUp}/3 DOCUMENTOS`}</span>
        </header>

        <div className="pc-panel-b">
          <button className="pc-btn secondary" onClick={() => nav("/catalog")} style={{ marginBottom: 14 }}>
            ← Volver al catálogo
          </button>

          {/* BARRA 1: contexto + Procesar (como el ICT) */}
          <div className="pc-scenarios">
            <span className="pc-scenarios-l">Doble codificación</span>
            <span className="pc-chip on" style={{ cursor: "default" }}>Super Cías · SRI</span>
            <div style={{ flex: 1 }} />
            <button className="pc-chip accent" onClick={handleProcess} disabled={!reqDone || phase === "running"} title={reqDone ? "Corre los 8 motores" : "Sube las 2 balanzas"} style={{ fontWeight: 700 }}>
              {phase === "running" ? "⏳ Procesando…" : "▶ Procesar"}
            </button>
          </div>

          {/* BARRA 2: descargas + nuevo (como el ICT) */}
          <div className="pc-scenarios">
            <button className="pc-chip accent" onClick={() => dl(ART.excel)} disabled={!isDone} title="Excel auditable de 9 hojas" style={{ fontWeight: 700 }}>
              📤 Descargar Excel
            </button>
            <button className="pc-chip" onClick={() => dl(ART.zip)} disabled={!isDone} title="TXT + XML + Excel en un ZIP">
              🗂 Descargar todo (ZIP)
            </button>
            <button className="pc-chip danger" onClick={handleReset} title="Empezar de nuevo">
              🔄 Encerar / Nuevo
            </button>
          </div>

          {/* BARRA 2: subir documentos (4 chips) */}
          <div className="pc-scenarios" style={{ padding: "12px 14px", background: "var(--panel-2)", border: "1px solid var(--line)", borderRadius: 10, marginTop: 6 }}>
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
            <a
              className="pc-chip"
              href={ASISTENTE_IA_URL}
              target="_blank"
              rel="noopener noreferrer"
              title="Abre el Asistente Virtual Audit IA en tu ChatGPT (no consume tokens de la plataforma)"
              style={{ textDecoration: "none" }}
            >
              <span>🤖</span><span>Asistente Virtual IA</span><span style={{ fontSize: 11, opacity: 0.7 }}>↗</span>
            </a>
          </div>

          {/* Barra de progreso */}
          <div style={{ marginTop: 16, background: "var(--panel-2)", border: "1px solid var(--line)", borderRadius: 8, height: 8, overflow: "hidden" }}>
            <div style={{ width: `${percent}%`, height: "100%", background: "var(--accent)", transition: "width 0.3s" }} />
          </div>
          <div style={{ fontSize: 11, color: "var(--text-soft)", marginTop: 6 }}>
            <b style={{ color: "var(--accent)" }}>{isDone ? 9 : 0}</b> de 9 secciones generadas ·
            <b style={{ color: "var(--accent)", marginLeft: 6 }}>{docsUp}</b> de 3 documentos subidos
          </div>

          {err && (
            <div style={{ marginTop: 14, padding: "12px 14px", background: "rgba(255,93,93,0.08)", border: "1px solid rgba(255,93,93,0.4)", borderRadius: 10, color: "var(--danger)", fontSize: 13 }}>{err}</div>
          )}

          {phase === "running" && (
            <div style={{ marginTop: 14, padding: "12px 14px", background: "var(--accent-dim)", border: "1px solid rgba(52,211,106,0.45)", borderRadius: 10, fontSize: 13, color: "var(--text-soft)" }}>
              <span style={{ color: "var(--accent)", fontWeight: 700 }}>▶ {MOTOR_STEPS[runStep]}…</span>
            </div>
          )}

          {reqDone && phase === "idle" && (
            <div style={{ marginTop: 14, padding: "12px 14px", background: "var(--accent-dim)", border: "1px solid rgba(52,211,106,0.45)", borderRadius: 10, fontSize: 13, display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ fontSize: 22 }}>✨</span>
              <div>
                <div style={{ color: "var(--accent)", fontWeight: 700 }}>Listo para procesar</div>
                <div style={{ color: "var(--text-soft)", fontSize: 12, marginTop: 2 }}>
                  Las balanzas están cargadas. Pulsa <b style={{ color: "var(--accent)" }}>▶ Procesar</b> para generar las 9 secciones.
                </div>
              </div>
            </div>
          )}

          {/* GRID DE SECCIONES */}
          <div style={{ marginTop: 18, marginBottom: 8, fontSize: 11, color: "var(--text-soft)", letterSpacing: 0.06 }}>
            {isDone ? "Click en una sección para descargar su archivo:" : "Secciones que se generarán:"}
          </div>
          <div className="pc-tiles">
            {SECTIONS.map((s) => {
              const ready = isDone && s.dl !== "soon";
              return (
                <button
                  key={s.code}
                  className={`pc-tile${ready ? " done" : ""}${selected === s.code ? " on" : ""}`}
                  onClick={() => setSelected(s.code)}
                  disabled={phase === "running"}
                  style={ready ? { background: "linear-gradient(180deg, var(--panel-2), var(--accent-dim))" } : undefined}
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
            <div className="fx-prev">
              <div className="fx-prev-h">
                <div>
                  <div className="fx-prev-t">{sel.name}</div>
                  <div className="fx-prev-m">Vista previa · {(previews?.[sel.code]?.rows?.length ?? 0)} filas</div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {(sel.dl === "txt" || sel.dl === "xml") && isDone && (
                    <button className="pc-chip accent" onClick={() => dl(sel.art)} style={{ fontWeight: 700 }}>
                      ⤓ Descargar {sel.dl.toUpperCase()}
                    </button>
                  )}
                  {isDone && (
                    <button className="pc-chip" onClick={() => dl(ART.excel)}>📊 Excel</button>
                  )}
                </div>
              </div>
              {!isDone ? (
                <div className="fx-prev-empty">Procesá primero para ver la tabla de esta sección.</div>
              ) : sel.code === "ESF" && previews?.WP_ESF ? (
                <HojaTrabajo data={previews.WP_ESF} />
              ) : previews?.[sel.code] ? (
                <div className="fx-prev-scroll">
                  <table className="fx-prev-tbl">
                    <thead>
                      <tr>{previews[sel.code].cols.map((c, i) => (
                        <th key={i} className={i === 0 ? "" : "num"}>{c}</th>
                      ))}</tr>
                    </thead>
                    <tbody>
                      {previews[sel.code].rows.map((r, ri) => (
                        <tr key={ri}>{r.map((v, ci) => (
                          <td key={ci} className={ci === 0 ? "cod" : "num"}>
                            {ci === 0 ? v : (typeof v === "number" ? formatMoney(v) : v)}
                          </td>
                        ))}</tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="fx-prev-empty">
                  {sel.dl === "soon"
                    ? "La presentación oficial (códigos 95xx / 99xx) llega en la Fase B; sus valores ya están en el Excel."
                    : "Cargando vista previa…"}
                </div>
              )}
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
