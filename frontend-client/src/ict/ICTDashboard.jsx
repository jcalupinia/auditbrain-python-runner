import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { getActiveSession, deleteSession, downloadExcel, createSession, uploadAnexoSlot, resetSlot } from "./ictApi.js";
import ICTEditContribuyenteModal from "./ICTEditContribuyenteModal.jsx";
import PortalShell from "../shell/PortalShell.jsx";

/* ============================================================
   Portal Cliente · Dashboard ICT 2025
   Patrón visual idéntico a la herramienta TAX del Command Center:
   - Barra superior con los uploads GLOBALES de la sesión
     (F-101, Balance Mapeado, F-104, ATS, etc.) SIEMPRE visibles
   - Barra de acciones generales (descargar, editar, cerrar)
   - Grid numerado [0]-[9] de los 10 anexos como NAVEGACIÓN/ESTADO
   - Panel inferior con el estado del anexo seleccionado
     (warnings, advertencias, qué uploads usa)
   ============================================================ */

/* --------------------------------------------------------------
   Uploads globales: catálogo único de tipos de documento del ICT.
   Cada upload se sube a su "anexo principal" en el backend (el
   primero que lo requiere), y el shared_context del orquestador
   ya lo reutiliza en todos los demás anexos que lo necesitan.
   -------------------------------------------------------------- */
// Cuatro documentos mínimos que cubren el 95-100% de los 10 anexos del ICT.
// Análisis cruzado con declaraciones reales del SRI 2025 (PROPHAR).
// Los detalles secundarios (Mayor Exentos/No Deducibles/Kardex/ATS/Facturación SRI)
// se omiten para simplificar UX — el cliente sube 4 documentos en vez de 8.
const GLOBAL_UPLOADS = [
  { key: "balance_mapeado",     label: "Balance Mapeado",  icon: "📊", anexo: "A1", multi: false,
    usedIn: ["A1","A2","A3","A4","A5","A6","A7","A9"],
    desc: "Excel con cuenta contable → casillero SRI → saldo 31 dic" },
  { key: "f101",                label: "Formulario 101",   icon: "📄", anexo: "A1", multi: false,
    usedIn: ["A1","A2","A3","A4","A5","A6","A7","A9"],
    desc: "Declaración anual IR sociedades (PDF SRI)" },
  { key: "f104",                label: "Formularios 104",  icon: "📑", anexo: "A2", multi: true,
    usedIn: ["A2","A8"],
    desc: "12 declaraciones mensuales IVA (PDF SRI)" },
  { key: "f103",                label: "Formularios 103",  icon: "📋", anexo: "A8", multi: true,
    usedIn: ["A3","A5","A7","A8"],
    desc: "12 declaraciones mensuales Retenciones IR (PDF SRI)" },
];

const ANEXOS_INFO = [
  { code: "INDICE", n: "0", name: "Índice",        desc: "Identificación + Aplica SI/NO por anexo", uploads: [] },
  { code: "A1",     n: "1", name: "A1 Mapeo",      desc: "Cruce casilleros F-101 con balance",       uploads: ["f101","balance_mapeado"] },
  { code: "A2",     n: "2", name: "A2 Ingresos",   desc: "Ordinarios + conciliación IVA mensual",     uploads: ["f101","f104","balance_mapeado"] },
  { code: "A3",     n: "3", name: "A3 Costos",     desc: "9 bloques de deducibilidad",                uploads: ["f101","balance_mapeado"] },
  { code: "A4",     n: "4", name: "A4 Concil.Ing", desc: "Exentos / no objeto / RIMPE",               uploads: ["f101","balance_mapeado"] },
  { code: "A5",     n: "5", name: "A5 Concil.C/G", desc: "5 cuadros + prorrateo + retenciones",       uploads: ["f101","f103","balance_mapeado"] },
  { code: "A6",     n: "6", name: "A6 Beneficios", desc: "Deducciones + contratos + exoneraciones",   uploads: ["f101","balance_mapeado"] },
  { code: "A7",     n: "7", name: "A7 Crédito",    desc: "IR multi-año + retenciones efectuadas",     uploads: ["f101","f103"] },
  { code: "A8",     n: "8", name: "A8 Com.Ext.",   desc: "Pagos al exterior con/sin CDI + paraísos",  uploads: ["f103","f104"] },
  { code: "A9",     n: "9", name: "A9 Inventarios",desc: "9 casilleros + saldos por cuenta",          uploads: ["f101","balance_mapeado"] },
];

const STATUS_DISPLAY = {
  empty:   { tile: "dim",  label: "Pendiente"  },
  partial: { tile: "",     label: "Parcial"    },
  ready:   { tile: "done", label: "Completado" },
  error:   { tile: "",     label: "Error"      },
};

function bytes(n) {
  if (!n && n !== 0) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/* ============================================================
   Sub-componente: chip de upload global (botón en barra superior)
   ============================================================ */
function GlobalUploadChip({ upload, session, onChanged }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);

  // Estado del archivo: lo buscamos en el anexo principal del upload.
  const anexo = (session.anexos || []).find((a) => a.anexo_code === upload.anexo);
  const uploaded = anexo?.uploaded_files?.[upload.key];

  async function handleFile(e) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setBusy(true);
    try {
      await uploadAnexoSlot(session.id, upload.anexo, upload.key, Array.from(files));
      onChanged();
    } catch (err) {
      alert(`Error subiendo ${upload.label}: ${err.message}`);
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function handleReset(e) {
    e.stopPropagation();
    if (!confirm(`¿Eliminar ${upload.label}? Se recalcularán los anexos que lo usan.`)) return;
    setBusy(true);
    try {
      await resetSlot(session.id, upload.anexo, upload.key);
      onChanged();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  const cls = uploaded ? "pc-chip on" : "pc-chip";
  const labelText = busy
    ? "Subiendo..."
    : uploaded
      ? `✓ ${upload.label}`
      : `↑ ${upload.label}`;

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple={upload.multi}
        style={{ display: "none" }}
        onChange={handleFile}
      />
      <button
        className={cls}
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        title={uploaded
          ? `${uploaded.filename} · ${bytes(uploaded.size)} — clic para reemplazar`
          : `Sube el ${upload.label} (usado en ${upload.usedIn.join(", ")})`
        }
      >
        <span>{upload.icon}</span>
        <span>{labelText}</span>
        {upload.multi && <span style={{ fontSize: 9, opacity: 0.7 }}>multi</span>}
        {uploaded && (
          <span
            onClick={handleReset}
            style={{
              marginLeft: 4, padding: "0 4px",
              borderLeft: "1px solid rgba(0,0,0,0.2)",
              fontSize: 11, fontWeight: 700,
            }}
            title="Eliminar archivo"
          >×</span>
        )}
      </button>
    </>
  );
}

/* ============================================================
   Dashboard principal
   ============================================================ */
export default function ICTDashboard() {
  const nav = useNavigate();
  const [session, setSession] = useState(undefined);
  const [editOpen, setEditOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [selected, setSelected] = useState("INDICE");

  const refresh = useCallback(async () => {
    try {
      const s = await getActiveSession();
      setSession(s);
    } catch {
      setSession(null);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  if (session === undefined) {
    return (
      <PortalShell title="ICT 2025" subtitle="Cargando proyecto..." activeCategory="TRIBUTARIAS">
        <div className="pc-panel"><div className="pc-panel-b" style={{ color: "var(--text-soft)" }}>
          Cargando proyecto ICT 2025...
        </div></div>
      </PortalShell>
    );
  }
  if (session === null) {
    return (
      <PortalShell title="ICT 2025" subtitle="Crear nuevo proyecto" activeCategory="TRIBUTARIAS">
        <ICTLandingPanel />
      </PortalShell>
    );
  }

  const readyCount = (session.anexos || []).filter((a) => a.status === "ready").length;
  const totalAnexos = ANEXOS_INFO.length;
  const percent = Math.round((readyCount / totalAnexos) * 100);

  // Cuántos uploads globales ya subieron
  const uploadedKeys = new Set();
  (session.anexos || []).forEach((a) => {
    Object.keys(a.uploaded_files || {}).forEach((k) => uploadedKeys.add(k));
  });
  const uploadsDone = GLOBAL_UPLOADS.filter((u) => uploadedKeys.has(u.key)).length;

  async function handleDownload() {
    setDownloading(true);
    try {
      await downloadExcel(session.id);
    } catch (e) {
      alert(`Error descargando: ${e.message}`);
    } finally {
      setDownloading(false);
    }
  }
  async function handleClose() {
    if (!confirm("¿Cerrar este proyecto ICT? Podrás crear uno nuevo, pero no recuperar este.")) return;
    await deleteSession(session.id);
    setSession(null);
  }

  const selInfo = ANEXOS_INFO.find((i) => i.code === selected);
  const selAnexo = (session.anexos || []).find((a) => a.anexo_code === selected)
    || { anexo_code: selected, status: "empty", warnings: [], uploaded_files: {} };

  const contextExtras = (
    <div className="pc-ctx-card">
      <div className="pc-ctx-h2">📋 Proyecto ICT activo</div>
      <div className="pc-ctx-k">Razón social</div>
      <div className="pc-ctx-v">{session.razon_social}</div>
      <div className="pc-ctx-k">RUC</div>
      <div className="pc-ctx-v" style={{ fontFamily: "var(--mono)" }}>{session.ruc}</div>
      <div className="pc-ctx-k">Ejercicio</div>
      <div className="pc-ctx-v">AF {session.ejercicio_fiscal}</div>
      {session.numero_adhesivo && <>
        <div className="pc-ctx-k">Adhesivo</div>
        <div className="pc-ctx-v">{session.numero_adhesivo}</div>
      </>}
      <div className="pc-ctx-k">Anexos</div>
      <div className="pc-ctx-v">
        <b>{readyCount}/{totalAnexos}</b> · {percent}%
      </div>
      <div className="pc-ctx-k">Documentos</div>
      <div className="pc-ctx-v">
        <b>{uploadsDone}/{GLOBAL_UPLOADS.length}</b> subidos
      </div>
    </div>
  );

  return (
    <PortalShell
      title="ICT 2025"
      subtitle={`${session.razon_social} · RUC ${session.ruc}`}
      activeCategory="TRIBUTARIAS"
      activeNodeCode="ICT_2025"
      contextExtras={contextExtras}
    >
      {/* ----- Panel maestro de la herramienta ICT ----- */}
      <section className="pc-panel">
        <header className="pc-panel-h">
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <span className="pc-code">ICT</span>
            <span className="pc-panel-t">Workspace de Cumplimiento Tributario</span>
          </div>
          <span className="pc-panel-m">
            AF {session.ejercicio_fiscal} · {readyCount}/{totalAnexos} ANEXOS
          </span>
        </header>
        <div className="pc-panel-b">
          {/* Volver al catálogo */}
          <button
            className="pc-btn secondary"
            onClick={() => nav("/catalog")}
            style={{ marginBottom: 14 }}
          >
            ← Volver al catálogo
          </button>

          {/* ===== BARRA 1: Datos del contribuyente ===== */}
          <div className="pc-scenarios">
            <span className="pc-scenarios-l">Contribuyente</span>
            <span className="pc-chip on" style={{ cursor: "default" }}>
              {session.razon_social}
            </span>
            <button className="pc-chip" onClick={() => setEditOpen(true)}>
              ✏ Editar datos
            </button>
            <div style={{ flex: 1 }} />
            <button className="pc-chip accent" onClick={handleDownload} disabled={downloading}>
              {downloading ? "⏳ Generando..." : "↓ Descargar Excel ICT"}
            </button>
            <button className="pc-chip danger" onClick={handleClose}>
              ✕ Cerrar proyecto
            </button>
          </div>

          {/* ===== BARRA 2: SUBIR DOCUMENTOS (siempre visible) ===== */}
          <div className="pc-scenarios" style={{
            padding: "12px 14px",
            background: "var(--panel-2)",
            border: "1px solid var(--line)",
            borderRadius: 10,
            marginTop: 6,
          }}>
            <span className="pc-scenarios-l" style={{ color: "var(--accent)" }}>
              📂 Subir documentos
            </span>
            {GLOBAL_UPLOADS.map((u) => (
              <GlobalUploadChip
                key={u.key}
                upload={u}
                session={session}
                onChanged={refresh}
              />
            ))}
          </div>

          {/* Barra de progreso */}
          <div style={{
            marginTop: 16,
            background: "var(--panel-2)",
            border: "1px solid var(--line)",
            borderRadius: 8,
            height: 8,
            overflow: "hidden",
          }}>
            <div style={{
              width: `${percent}%`,
              height: "100%",
              background: "var(--accent)",
              transition: "width 0.3s",
            }} />
          </div>
          <div style={{ fontSize: 11, color: "var(--text-soft)", marginTop: 6 }}>
            <b style={{ color: "var(--accent)" }}>{readyCount}</b> de {totalAnexos} anexos completados ·
            <b style={{ color: "var(--accent)", marginLeft: 6 }}>{uploadsDone}</b> de {GLOBAL_UPLOADS.length} documentos subidos
          </div>

          {/* ===== GRID DE ANEXOS (navegación / estado) ===== */}
          <div style={{
            marginTop: 18, marginBottom: 8,
            fontSize: 11, color: "var(--text-soft)", letterSpacing: 0.06,
          }}>
            Click en un anexo para ver su estado y advertencias:
          </div>
          <div className="pc-tiles">
            {ANEXOS_INFO.map((info) => {
              const anexo = (session.anexos || []).find((a) => a.anexo_code === info.code);
              const st = STATUS_DISPLAY[anexo?.status || "empty"];
              const isSelected = selected === info.code;
              return (
                <button
                  key={info.code}
                  className={`pc-tile ${st.tile}${isSelected ? " on" : ""}`}
                  onClick={() => setSelected(info.code)}
                >
                  <span className={`pc-tile-n ${st.tile}`}>{info.n}</span>
                  <div className="pc-tile-txt">
                    <span className="pc-tile-t">{info.name}</span>
                    <span className="pc-tile-d">{info.desc}</span>
                  </div>
                  <span className="pc-tile-st">{st.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* ----- Panel inferior: estado del anexo seleccionado ----- */}
      <section className="pc-panel">
        <header className="pc-panel-h">
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <span className="pc-code">{selInfo.code}</span>
            <span className="pc-panel-t">{selInfo.name}</span>
          </div>
          <span className="pc-panel-m">
            {STATUS_DISPLAY[selAnexo.status || "empty"].label.toUpperCase()}
          </span>
        </header>
        <div className="pc-panel-b">
          <p style={{ color: "var(--text-soft)", margin: "0 0 16px", fontSize: 13 }}>
            {selInfo.desc}
          </p>

          {/* Documentos que requiere este anexo (lectura, no acción) */}
          {selInfo.uploads.length > 0 ? (
            <div>
              <div style={{ fontSize: 12, color: "var(--text-soft)", marginBottom: 8 }}>
                📄 Documentos usados por este anexo (súbelos en la barra superior):
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {selInfo.uploads.map((upKey) => {
                  const upMeta = GLOBAL_UPLOADS.find((g) => g.key === upKey);
                  if (!upMeta) return null;
                  const got = uploadedKeys.has(upKey);
                  return (
                    <span
                      key={upKey}
                      className={got ? "pc-chip on" : "pc-chip warn"}
                      style={{ cursor: "default" }}
                    >
                      {got ? "✓" : "○"} {upMeta.label}
                    </span>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="pc-tile" style={{ cursor: "default" }}>
              <span className="pc-tile-n dim">i</span>
              <div className="pc-tile-txt">
                <span className="pc-tile-t">Llenado automático</span>
                <span className="pc-tile-d">
                  Este anexo se construye a partir de los datos del contribuyente
                  y los demás anexos. No necesitas subir nada aquí.
                </span>
              </div>
            </div>
          )}

          {selAnexo.warnings?.length > 0 && (
            <details style={{ marginTop: 16 }} open>
              <summary style={{ cursor: "pointer", color: "var(--warn)", fontSize: 13 }}>
                ⚠ {selAnexo.warnings.length} advertencia(s)
              </summary>
              <ul style={{ fontSize: 12, color: "var(--text-soft)", marginTop: 8, paddingLeft: 18 }}>
                {selAnexo.warnings.slice(0, 10).map((w, i) => <li key={i}>{w}</li>)}
                {selAnexo.warnings.length > 10 && (
                  <li>... y {selAnexo.warnings.length - 10} más</li>
                )}
              </ul>
            </details>
          )}
        </div>
      </section>

      <ICTEditContribuyenteModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        session={session}
        onSaved={refresh}
      />
    </PortalShell>
  );
}

/* ============================================================
   Panel para crear sesión ICT cuando no existe.
   ============================================================ */
function ICTLandingPanel() {
  const nav = useNavigate();
  const [ruc, setRuc] = useState("");
  const [razon, setRazon] = useState("");
  const [anio, setAnio] = useState("2025");
  const [adhesivo, setAdhesivo] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    if (!/^\d{10,13}$/.test(ruc)) { setErr("RUC debe tener 10-13 dígitos"); return; }
    if (!razon.trim()) { setErr("Razón social es requerida"); return; }
    if (!/^\d{4}$/.test(anio)) { setErr("Ejercicio fiscal: 4 dígitos"); return; }
    setBusy(true);
    try {
      await createSession({
        ejercicio_fiscal: anio, ruc, razon_social: razon,
        numero_adhesivo: adhesivo || null,
      });
      window.location.reload();
    } catch (e2) { setErr(e2.message); }
    finally { setBusy(false); }
  }

  return (
    <>
      <section className="pc-hero">
        <h1>Crear <span>proyecto ICT 2025</span></h1>
        <p>
          Iniciamos tu Informe de Cumplimiento Tributario del SRI.
          Vas a poder subir los documentos cuando los tengas listos;
          el proyecto persiste 90 días en tu portal.
        </p>
      </section>

      <section className="pc-panel" style={{ maxWidth: 640 }}>
        <header className="pc-panel-h">
          <span className="pc-panel-t">Datos del contribuyente</span>
          <span className="pc-panel-m">PASO 1 / 3</span>
        </header>
        <div className="pc-panel-b">
          <form onSubmit={submit}>
            <label>RUC (10-13 dígitos)</label>
            <input value={ruc} onChange={(e) => setRuc(e.target.value)} required maxLength={13} />

            <label>Razón Social</label>
            <input value={razon} onChange={(e) => setRazon(e.target.value)} required />

            <label>Ejercicio Fiscal</label>
            <input value={anio} onChange={(e) => setAnio(e.target.value)} required maxLength={4} />

            <label>Número de Adhesivo (opcional)</label>
            <input value={adhesivo} onChange={(e) => setAdhesivo(e.target.value)} />

            {err && <div style={{ color: "var(--danger)", fontSize: 13, marginTop: 12 }}>{err}</div>}

            <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
              <button type="submit" className="pc-btn" disabled={busy}>
                {busy ? "Creando..." : "Crear proyecto ICT"}
              </button>
              <button type="button" className="pc-btn secondary" onClick={() => nav("/catalog")}>
                Cancelar
              </button>
            </div>
          </form>
        </div>
      </section>
    </>
  );
}
