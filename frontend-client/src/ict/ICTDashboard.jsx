import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getActiveSession, deleteSession, downloadExcel, createSession } from "./ictApi.js";
import ICTUploader from "./ICTUploader.jsx";
import ICTEditContribuyenteModal from "./ICTEditContribuyenteModal.jsx";
import PortalShell from "../shell/PortalShell.jsx";

/* ============================================================
   Portal Cliente · Dashboard ICT 2025
   Mismo lenguaje visual que la herramienta TAX del Command Center:
   - Header de la herramienta con título + meta + acciones rápidas
   - Barra de "scenarios" (vista actual, descargas, ejemplo)
   - Grid numerado [0]-[9] con los 10 anexos
   - Panel inferior con el detalle del anexo seleccionado
     (uploads, estado, warnings)
   ============================================================ */

const ANEXOS_INFO = [
  { code: "INDICE", n: "0", name: "Índice",        desc: "Identificación + Aplica SI/NO por anexo", autoFill: true },
  { code: "A1",     n: "1", name: "A1 Mapeo Decl.", desc: "Cruce casilleros F-101 con balance",
    slots: [
      { key: "f101",            label: "Formulario 101 (PDF)",                       required: true },
      { key: "balance_mapeado", label: "Balance Mapeado (Excel — con códigos SRI)",  required: true },
    ] },
  { code: "A2",     n: "2", name: "A2 Ingresos",    desc: "Ordinarios + IVA vs Facturación + Conciliación",
    slots: [
      { key: "f104",        label: "Formularios 104 (12 meses, varios a la vez)", required: true, multi: true },
      { key: "facturacion", label: "Reporte Facturación SRI (Excel)",             required: true },
    ] },
  { code: "A3",     n: "3", name: "A3 Costos y Gastos", desc: "9 bloques de deducibilidad",
    slots: [{ key: "f101", label: "Formulario 101 (reutilizable)", required: true }] },
  { code: "A4",     n: "4", name: "A4 Concil. Ingresos", desc: "Exentos / no objeto / RIMPE",
    slots: [
      { key: "f101",          label: "Formulario 101",                          required: true  },
      { key: "mayor_exentos", label: "Libro Mayor cuentas exentas (Excel)",     required: false },
    ] },
  { code: "A5",     n: "5", name: "A5 Concil. C/G",  desc: "5 cuadros + prorrateo",
    slots: [
      { key: "f101",                label: "Formulario 101",                       required: true  },
      { key: "mayor_no_deducibles", label: "Libro Mayor no deducibles (Excel)",    required: false },
    ] },
  { code: "A6",     n: "6", name: "A6 Beneficios",   desc: "Deducciones + contratos + exoneraciones",
    slots: [{ key: "f101", label: "Formulario 101", required: true }] },
  { code: "A7",     n: "7", name: "A7 Crédito Trib.", desc: "IR multi-año + ISD",
    slots: [{ key: "f101", label: "Formulario 101", required: true }] },
  { code: "A8",     n: "8", name: "A8 Com. Exterior", desc: "Pagos al exterior (CDI / sin CDI / reembolsos)",
    slots: [{ key: "ats", label: "ATS XML (SRI)", required: true }] },
  { code: "A9",     n: "9", name: "A9 Inventarios",   desc: "9 casilleros + Kardex",
    slots: [
      { key: "f101",   label: "Formulario 101",            required: true  },
      { key: "kardex", label: "Kardex (Excel) opcional",   required: false },
    ] },
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

  // Contexto extra para el sidebar derecho
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
      <div className="pc-ctx-k">Progreso</div>
      <div className="pc-ctx-v">
        <b>{readyCount}/{totalAnexos}</b> anexos · {percent}%
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
      {/* ----- Panel maestro: barra de acciones tipo scenarios ----- */}
      <section className="pc-panel">
        <header className="pc-panel-h">
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <span className="pc-code">ICT</span>
            <span className="pc-panel-t">Workspace de Cumplimiento Tributario</span>
          </div>
          <span className="pc-panel-m">
            EJERCICIO {session.ejercicio_fiscal} · {readyCount}/{totalAnexos} ANEXOS
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

          {/* Barra de scenarios / acciones rápidas */}
          <div className="pc-scenarios">
            <span className="pc-scenarios-l">Contribuyente</span>
            <span className="pc-chip on" style={{ cursor: "default" }}>
              {session.razon_social}
            </span>
            <button className="pc-chip" onClick={() => setEditOpen(true)}>
              ✏ Editar datos
            </button>
            <div style={{ flex: 1 }} />
            <button
              className="pc-chip accent"
              onClick={handleDownload}
              disabled={downloading}
            >
              {downloading ? "⏳ Generando..." : "↓ Descargar Excel ICT"}
            </button>
            <button className="pc-chip danger" onClick={handleClose}>
              ✕ Cerrar proyecto
            </button>
          </div>

          {/* Barra progreso visual */}
          <div style={{
            background: "var(--panel-2)",
            border: "1px solid var(--line)",
            borderRadius: 8,
            height: 8,
            overflow: "hidden",
            marginBottom: 8,
          }}>
            <div style={{
              width: `${percent}%`,
              height: "100%",
              background: "var(--accent)",
              transition: "width 0.3s",
            }} />
          </div>
          <div style={{ fontSize: 11, color: "var(--text-soft)", letterSpacing: 0.1 }}>
            <b style={{ color: "var(--accent)" }}>{readyCount}</b> de {totalAnexos} anexos completados · {percent}% del informe
          </div>

          {/* Grid numerado de anexos */}
          <div className="pc-tiles" style={{ marginTop: 18 }}>
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

      {/* ----- Panel inferior: detalle del anexo seleccionado ----- */}
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

          {selInfo.autoFill && (
            <div className="pc-tile" style={{ cursor: "default" }}>
              <span className="pc-tile-n dim">i</span>
              <div className="pc-tile-txt">
                <span className="pc-tile-t">Llenado automático</span>
                <span className="pc-tile-d">
                  Este anexo se construye a partir de los datos del contribuyente y los demás anexos.
                </span>
              </div>
            </div>
          )}

          {selInfo.slots && selInfo.slots.map((slot) => {
            const uploaded = selAnexo.uploaded_files?.[slot.key];
            return (
              <div key={slot.key} style={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: 12,
                alignItems: "center",
                padding: "14px 0",
                borderTop: "1px solid var(--line-soft)",
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>
                    {slot.label}
                    {slot.required && <span style={{ color: "var(--accent)", marginLeft: 6 }}>*</span>}
                    {slot.multi && (
                      <span className="pc-chip" style={{
                        padding: "2px 8px", fontSize: 10, marginLeft: 8, cursor: "default",
                      }}>multi</span>
                    )}
                  </div>
                  {uploaded ? (
                    <div style={{ color: "var(--accent)", fontSize: 12, marginTop: 4 }}>
                      ✓ {uploaded.filename} <span style={{ color: "var(--text-dim)" }}>({bytes(uploaded.size)})</span>
                    </div>
                  ) : (
                    <div style={{ color: "var(--text-dim)", fontSize: 12, marginTop: 4 }}>
                      Sin archivo subido
                    </div>
                  )}
                </div>
                <ICTUploader
                  sessionId={session.id}
                  anexoCode={selAnexo.anexo_code}
                  slotName={slot.key}
                  onUploaded={refresh}
                  hasFile={!!uploaded}
                  multi={!!slot.multi}
                />
              </div>
            );
          })}

          {selAnexo.warnings?.length > 0 && (
            <details style={{ marginTop: 16 }}>
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
   Sub-componente: panel para crear sesión ICT cuando no existe.
   Reutilizamos la lógica de ICTLanding pero envuelta en un
   pc-panel oscuro para integrarse con el shell.
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
      // tras crear, el refresh del padre lo detecta
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
