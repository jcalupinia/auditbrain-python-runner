import { useCallback, useEffect, useState } from "react";
import * as api from "../../api.js";
import { STRINGS } from "../strings.js";
import "./ofWorkspace.css";
import SlotChip from "./SlotChip.jsx";
import EditarDatosModal from "./EditarDatosModal.jsx";
import RevisionClasificacion from "./RevisionClasificacion.jsx";
import { contarSubidos, estadoTile, etiquetaEstadoTile, encontrarJobActivo } from "./ofLogic.js";

// `label` es el texto corto del chip (para que la barra quepa en una fila,
// como en el ICT); `descripcion` es el detalle completo, que va como tooltip
// y se muestra en el panel inferior de cada cédula.
const SLOTS = [
  { key: "f104", label: STRINGS.of_chip_f104, descripcion: STRINGS.of_slot_f104, accept: "application/pdf", multiple: true, required: true },
  { key: "f103", label: STRINGS.of_chip_f103, descripcion: STRINGS.of_slot_f103, accept: "application/pdf", multiple: true },
  // El ATS llega en XML o en PDF (el "Talón Resumen" del SRI), según lo que
  // el cliente entregue. El backend acepta ambos; la UI no debe restringirlo.
  { key: "ats", label: STRINGS.of_chip_ats, descripcion: STRINGS.of_slot_ats, accept: ".xml,application/xml,text/xml,application/pdf", multiple: true },
  { key: "mayor_general", label: STRINGS.of_chip_mayor_general, descripcion: STRINGS.of_slot_mayor_general, accept: ".xlsx,.xls,.csv", multiple: false, required: true },
  { key: "mayor_especifico", label: STRINGS.of_chip_mayor_especifico, descripcion: STRINGS.of_slot_mayor_especifico, accept: ".xlsx,.xls,.csv", multiple: false },
  { key: "f101", label: STRINGS.of_chip_f101, descripcion: STRINGS.of_slot_f101, accept: "application/pdf", multiple: false },
];
const SLOT_KEYS = SLOTS.map((s) => s.key);

const CEDULAS = [
  { key: "clasificacion", n: "0", t: STRINGS.of_tile_clasificacion_t, d: STRINGS.of_tile_clasificacion_d, uploads: ["mayor_general"] },
  { key: "dm3", n: "1", t: STRINGS.of_tile_dm3_t, d: STRINGS.of_tile_dm3_d, uploads: ["mayor_general"] },
  { key: "dm4", n: "2", t: STRINGS.of_tile_dm4_t, d: STRINGS.of_tile_dm4_d, uploads: ["f104", "mayor_general"] },
  { key: "dm5", n: "3", t: STRINGS.of_tile_dm5_t, d: STRINGS.of_tile_dm5_d, uploads: ["f104", "mayor_general"] },
  { key: "dm6", n: "4", t: STRINGS.of_tile_dm6_t, d: STRINGS.of_tile_dm6_d, uploads: ["f104"] },
  { key: "dm7", n: "5", t: STRINGS.of_tile_dm7_t, d: STRINGS.of_tile_dm7_d, uploads: ["f103"] },
];

function nombreCliente(job) {
  const cliente = (job.cliente_name || "cliente").replace(/[^a-zA-Z0-9]/g, "_");
  const periodo = (job.period_label || "").replace(/[^a-zA-Z0-9]/g, "_");
  return `DM_Obligaciones_Fiscales_${cliente}_${periodo}.xlsx`;
}

/*
 * Panel maestro del workspace de Obligaciones Fiscales, calcado del
 * workspace del ICT (frontend-client/src/ict/ICTDashboard.jsx): cabecera
 * con contribuyente + acciones, barra de chips de documentos, barra de
 * progreso y grid de cédulas con panel inferior.
 *
 * Al montar retoma el job en 'borrador'/'revision' del proyecto si existe
 * (así recargar la página no pierde los documentos subidos); si no hay
 * ninguno, ofrece crear un encargo nuevo.
 */
export default function ObligacionesFiscalesWorkspace({ projectId }) {
  const [job, setJob] = useState(undefined); // undefined=cargando, null=sin job, obj=activo
  const [jobsList, setJobsList] = useState([]);
  const [slotsEstado, setSlotsEstado] = useState({});
  const [selected, setSelected] = useState("clasificacion");
  const [error, setError] = useState("");
  const [procesando, setProcesando] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [encerando, setEncerando] = useState(false);
  const [modal, setModal] = useState({ open: false, mode: "crear" });

  const cargarSlots = useCallback(async (jobId) => {
    try {
      const estado = await api.estadoSlotsOF(jobId);
      setSlotsEstado(estado);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  const cargarTodo = useCallback(async () => {
    if (!projectId) return;
    setError("");
    try {
      const list = await api.listObligacionesFiscalesJobs(projectId);
      setJobsList(list);
      const activo = encontrarJobActivo(list);
      setJob(activo);
      if (activo) await cargarSlots(activo.id);
    } catch (e) {
      setError(e.message || STRINGS.of_ws_error_cargar);
      setJob(null);
    }
  }, [projectId, cargarSlots]);

  useEffect(() => { cargarTodo(); }, [cargarTodo]);

  if (!projectId) {
    return (
      <div className="notice warn">
        Selecciona un proyecto del módulo AUD primero (botón Workspace en la cabecera).
      </div>
    );
  }

  async function handleProcesar() {
    setProcesando(true);
    setError("");
    try {
      const actualizado = await api.procesarOF(job.id);
      setJob(actualizado);
      setSelected("clasificacion");
    } catch (e) {
      setError(e.message);
    } finally {
      setProcesando(false);
    }
  }

  async function handleDescargar() {
    setDescargando(true);
    setError("");
    try {
      await api.downloadObligacionesFiscalesJob(job.id, nombreCliente(job));
    } catch (e) {
      setError(e.message);
    } finally {
      setDescargando(false);
    }
  }

  async function handleEncerar() {
    if (!window.confirm(STRINGS.of_ws_encerar_confirm)) return;
    setEncerando(true);
    setError("");
    try {
      await api.eliminarJobOF(job.id);
      setJob(null);
      setSlotsEstado({});
      setSelected("clasificacion");
      await cargarTodo();
    } catch (e) {
      setError(e.message);
    } finally {
      setEncerando(false);
    }
  }

  function handleAprobado(jobActualizado) {
    setJob(jobActualizado);
    cargarTodo();
  }

  function handleGuardadoModal(nuevoJob) {
    setJob(nuevoJob);
    setSlotsEstado({});
    setSelected("clasificacion");
    cargarTodo();
  }

  // ---- Estado derivado para la cabecera ----
  const subidos = contarSubidos(slotsEstado, SLOT_KEYS);
  const tieneMayorGeneral = (slotsEstado.mayor_general?.n_archivos || 0) > 0;
  const jobEditable = job && (job.status === "borrador" || job.status === "revision");
  const puedeProcesar = jobEditable && tieneMayorGeneral && !procesando;
  let procesarTitle;
  if (!jobEditable) procesarTitle = STRINGS.of_ws_procesar_disabled_no_borrador;
  else if (!tieneMayorGeneral) procesarTitle = STRINGS.of_ws_procesar_disabled_sin_mayor;

  const puedeDescargar = job && job.status === "done" && !descargando;

  const recientes = jobsList.filter((j) => j.status === "done").slice(0, 10);

  return (
    <div className="of-tool">
      {job === undefined && (
        <div className="pc-panel">
          <div className="pc-panel-b" style={{ color: "var(--text-soft)" }}>
            {STRINGS.of_ws_cargando}
          </div>
        </div>
      )}

      {job === null && (
        <div className="pc-panel">
          <header className="pc-panel-h">
            <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
              <span className="pc-code">{STRINGS.of_ws_code}</span>
              <span className="pc-panel-t">{STRINGS.of_ws_title}</span>
            </div>
          </header>
          <div className="pc-panel-b">
            {error && <div className="err" style={{ marginBottom: 12 }}>{error}</div>}
            <p className="muted">{STRINGS.of_ws_sin_job_desc}</p>
            <button
              type="button"
              className="pc-btn"
              onClick={() => setModal({ open: true, mode: "crear" })}
            >
              {STRINGS.of_ws_nuevo_encargo}
            </button>

            {recientes.length > 0 && (
              <div className="of-recent" style={{ marginTop: 24 }}>
                <h3>{STRINGS.of_recent}</h3>
                <ul className="of-recent-list">
                  {recientes.map((j) => (
                    <li key={j.id}>
                      #{j.id} · {j.cliente_name} · {j.period_label}{" "}
                      <span className={`badge ${j.status}`}>{j.status}</span>
                      <button
                        type="button"
                        className="link"
                        onClick={() => api.downloadObligacionesFiscalesJob(j.id, nombreCliente(j))}
                      > · ↓ descargar</button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {job && (
        <>
          <section className="pc-panel">
            <header className="pc-panel-h">
              <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
                <span className="pc-code">{STRINGS.of_ws_code}</span>
                <span className="pc-panel-t">{STRINGS.of_ws_title}</span>
              </div>
              <span className="pc-panel-m">
                {job.period_label} · {job.status.toUpperCase()}
              </span>
            </header>
            <div className="pc-panel-b">
              {/* ===== BARRA 1: contribuyente + acciones ===== */}
              <div className="pc-scenarios">
                <span className="pc-scenarios-l">{STRINGS.of_ws_contribuyente}</span>
                <span className="pc-chip on" style={{ cursor: "default" }}>{job.cliente_name}</span>
                <button
                  type="button"
                  className="pc-chip"
                  onClick={() => setModal({ open: true, mode: "editar" })}
                >
                  {STRINGS.of_ws_edit_datos}
                </button>
                <div style={{ flex: 1 }} />
                <button
                  type="button"
                  className="pc-chip accent"
                  onClick={handleProcesar}
                  disabled={!puedeProcesar}
                  title={procesarTitle}
                  style={{ fontWeight: 700 }}
                >
                  {procesando ? STRINGS.of_ws_procesando : STRINGS.of_ws_procesar}
                </button>
                <button
                  type="button"
                  className="pc-chip accent"
                  onClick={handleDescargar}
                  disabled={!puedeDescargar}
                  title={job.status !== "done" ? STRINGS.of_ws_descargar_disabled : undefined}
                  style={{ fontWeight: 700 }}
                >
                  {descargando ? STRINGS.of_ws_descargando : STRINGS.of_ws_descargar}
                </button>
                <button
                  type="button"
                  className="pc-chip danger"
                  onClick={handleEncerar}
                  disabled={encerando}
                >
                  {STRINGS.of_ws_encerar}
                </button>
              </div>

              {/* ===== BARRA 2: subir documentos ===== */}
              <div
                className="pc-scenarios"
                style={{
                  padding: "12px 14px", background: "var(--panel-2)",
                  border: "1px solid var(--line)", borderRadius: 10, marginTop: 6,
                }}
              >
                <span className="pc-scenarios-l" style={{ color: "var(--accent)" }}>
                  {STRINGS.of_ws_subir_documentos}
                </span>
                {SLOTS.map((s) => (
                  <SlotChip
                    key={s.key}
                    slot={s}
                    jobId={job.id}
                    estado={slotsEstado[s.key]}
                    disabled={!jobEditable}
                    onChanged={() => cargarSlots(job.id)}
                  />
                ))}
              </div>

              {/* Barra de progreso */}
              <div style={{
                marginTop: 16, background: "var(--panel-2)", border: "1px solid var(--line)",
                borderRadius: 8, height: 8, overflow: "hidden",
              }}>
                <div style={{
                  width: `${Math.round((subidos / SLOT_KEYS.length) * 100)}%`,
                  height: "100%", background: "var(--accent)", transition: "width 0.3s",
                }} />
              </div>
              <div style={{ fontSize: 11, color: "var(--text-soft)", marginTop: 6 }}>
                <b style={{ color: "var(--accent)" }}>{subidos}</b> {STRINGS.of_ws_anexos_label}{" "}
                {SLOT_KEYS.length} {STRINGS.of_ws_documentos_subidos}
              </div>

              {error && <div className="err" style={{ marginTop: 12 }}>{error}</div>}

              {/* ===== GRID DE CÉDULAS ===== */}
              <div style={{ marginTop: 18, marginBottom: 8, fontSize: 11, color: "var(--text-soft)" }}>
                {STRINGS.of_ws_click_cedula}
              </div>
              <div className="pc-tiles">
                {CEDULAS.map((c) => {
                  const cls = estadoTile(job.status, c.key === "clasificacion");
                  const isSelected = selected === c.key;
                  return (
                    <button
                      key={c.key}
                      type="button"
                      className={`pc-tile ${cls}${isSelected ? " on" : ""}`}
                      onClick={() => setSelected(c.key)}
                    >
                      <span className={`pc-tile-n ${cls}`}>{c.n}</span>
                      <div className="pc-tile-txt">
                        <span className="pc-tile-t">{c.t}</span>
                        <span className="pc-tile-d">{c.d}</span>
                      </div>
                      <span className="pc-tile-st">{etiquetaEstadoTile(cls)}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </section>

          {/* ----- Panel inferior: cédula seleccionada ----- */}
          <section className="pc-panel">
            <PanelCedula
              cedula={CEDULAS.find((c) => c.key === selected)}
              job={job}
              slotsEstado={slotsEstado}
              slots={SLOTS}
              onAprobado={handleAprobado}
            />
          </section>

          {recientes.length > 0 && (
            <div className="of-recent">
              <h3>{STRINGS.of_recent}</h3>
              <ul className="of-recent-list">
                {recientes.map((j) => (
                  <li key={j.id}>
                    #{j.id} · {j.cliente_name} · {j.period_label}{" "}
                    <span className={`badge ${j.status}`}>{j.status}</span>
                    <button
                      type="button"
                      className="link"
                      onClick={() => api.downloadObligacionesFiscalesJob(j.id, nombreCliente(j))}
                    > · ↓ descargar</button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <EditarDatosModal
        open={modal.open}
        mode={modal.mode}
        projectId={projectId}
        job={modal.mode === "editar" ? job : null}
        onClose={() => setModal({ open: false, mode: "crear" })}
        onSaved={handleGuardadoModal}
      />
    </div>
  );
}

function PanelCedula({ cedula, job, slotsEstado, slots, onAprobado }) {
  const esClasificacion = cedula.key === "clasificacion";
  const cls = estadoTile(job.status, esClasificacion);

  return (
    <>
      <header className="pc-panel-h">
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <span className="pc-code">{cedula.n}</span>
          <span className="pc-panel-t">{cedula.t}</span>
        </div>
        <span className="pc-panel-m">{etiquetaEstadoTile(cls).toUpperCase()}</span>
      </header>
      <div className="pc-panel-b">
        <p style={{ color: "var(--text-soft)", margin: "0 0 16px", fontSize: 13 }}>{cedula.d}</p>

        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 12, color: "var(--text-soft)", marginBottom: 8 }}>
            {STRINGS.of_ws_docs_usados}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {cedula.uploads.map((slotKey) => {
              const meta = slots.find((s) => s.key === slotKey);
              if (!meta) return null;
              const got = (slotsEstado[slotKey]?.n_archivos || 0) > 0;
              return (
                <span
                  key={slotKey}
                  className={got ? "pc-chip on" : "pc-chip warn"}
                  style={{ cursor: "default" }}
                  title={meta.descripcion || meta.label}
                >
                  {got ? "✓" : "○"} {meta.descripcion || meta.label}
                </span>
              );
            })}
          </div>
        </div>

        {esClasificacion ? (
          job.status === "borrador" ? (
            <div className="pc-tile" style={{ cursor: "default" }}>
              <span className="pc-tile-n dim">i</span>
              <div className="pc-tile-txt">
                <span className="pc-tile-t">{STRINGS.of_ws_llenado_automatico_t}</span>
                <span className="pc-tile-d">{STRINGS.of_ws_procesar_disabled_sin_mayor}</span>
              </div>
            </div>
          ) : (
            <RevisionClasificacion
              jobId={job.id}
              onAprobado={onAprobado}
              soloLectura={job.status !== "revision"}
            />
          )
        ) : (
          <div className="pc-tile" style={{ cursor: "default" }}>
            <span className={`pc-tile-n ${cls}`}>i</span>
            <div className="pc-tile-txt">
              <span className="pc-tile-t">{STRINGS.of_ws_llenado_automatico_t}</span>
              <span className="pc-tile-d">{STRINGS.of_ws_llenado_automatico_d}</span>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
