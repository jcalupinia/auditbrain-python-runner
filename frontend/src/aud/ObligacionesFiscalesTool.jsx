import { useState, useEffect, useRef, useCallback } from "react";
import * as api from "../api.js";
import { STRINGS } from "./strings.js";

const SLOTS = [
  { key: "f104", label: STRINGS.of_slot_f104, accept: "application/pdf", multiple: true, required: true },
  { key: "f103", label: STRINGS.of_slot_f103, accept: "application/pdf", multiple: true },
  { key: "ats", label: STRINGS.of_slot_ats, accept: ".xml,application/xml,text/xml", multiple: true },
  { key: "mayor_compras", label: STRINGS.of_slot_mayor_compras, accept: ".xlsx,.xls", multiple: false },
  { key: "mayor_ventas", label: STRINGS.of_slot_mayor_ventas, accept: ".xlsx,.xls", multiple: false },
  { key: "f101", label: STRINGS.of_slot_f101, accept: "application/pdf", multiple: false },
];

export default function ObligacionesFiscalesTool({ projectId }) {
  const [stage, setStage] = useState("form"); // form | processing | done | failed
  const [form, setForm] = useState({
    cliente_name: "",
    period_label: "",
    period_end: "",
    prepared_by_name: "",
    reviewed_by_name: "",
  });
  const [files, setFiles] = useState({});
  const [job, setJob] = useState(null);
  const [recent, setRecent] = useState([]);
  const [err, setErr] = useState("");
  const pollRef = useRef();

  const loadRecent = useCallback(async () => {
    if (!projectId) return;
    try {
      setRecent(await api.listObligacionesFiscalesJobs(projectId));
    } catch (e) {
      // no crítico
    }
  }, [projectId]);

  useEffect(() => { loadRecent(); }, [loadRecent]);

  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current);
  }, []);

  function setFilesForSlot(slot, fileList) {
    setFiles((prev) => ({ ...prev, [slot]: Array.from(fileList || []) }));
  }

  async function submit(e) {
    e.preventDefault();
    setErr("");
    if (!(files.f104?.length)) {
      setErr(STRINGS.of_need_pdf);
      return;
    }
    try {
      const fileMap = {
        f103: files.f103 || [],
        f104: files.f104 || [],
        ats: files.ats || [],
        mayor_compras: files.mayor_compras?.[0],
        mayor_ventas: files.mayor_ventas?.[0],
        f101: files.f101?.[0],
      };
      const j = await api.createObligacionesFiscalesJob(
        { project_id: projectId, ...form },
        fileMap,
      );
      setJob(j);
      setStage("processing");
      pollRef.current = setInterval(async () => {
        try {
          const updated = await api.getObligacionesFiscalesJob(j.id);
          setJob(updated);
          if (updated.status === "done") {
            clearInterval(pollRef.current);
            setStage("done");
            loadRecent();
          } else if (
            updated.status === "failed" || updated.status === "expired"
          ) {
            clearInterval(pollRef.current);
            setStage("failed");
          }
        } catch (e2) {
          /* intermitencia; sigue intentando */
        }
      }, 2000);
    } catch (e2) {
      setErr(e2.message);
    }
  }

  function reset() {
    setStage("form");
    setJob(null);
    setFiles({});
    setErr("");
    setForm({
      cliente_name: "", period_label: "", period_end: "",
      prepared_by_name: "", reviewed_by_name: "",
    });
  }

  async function downloadJob(j) {
    try {
      const cliente = (j.cliente_name || "cliente").replace(/[^a-zA-Z0-9]/g, "_");
      const periodo = (j.period_label || "").replace(/[^a-zA-Z0-9]/g, "_");
      const filename = `DM_Obligaciones_Fiscales_${cliente}_${periodo}.xlsx`;
      await api.downloadObligacionesFiscalesJob(j.id, filename);
    } catch (e) {
      setErr(`Error al descargar: ${e.message}`);
    }
  }

  if (!projectId) {
    return (
      <div className="notice warn">
        Selecciona un proyecto del módulo AUD primero (botón Workspace
        en la cabecera).
      </div>
    );
  }

  return (
    <div className="of-tool">
      <header className="of-head">
        <h2>{STRINGS.of_title}</h2>
        <p className="muted">{STRINGS.of_subtitle}</p>
      </header>

      {stage === "form" && (
        <form onSubmit={submit} className="of-form">
          <div className="of-form-row">
            <label>{STRINGS.of_form_cliente}*
              <input
                value={form.cliente_name}
                required
                onChange={(e) => setForm({ ...form, cliente_name: e.target.value })}
              />
            </label>
            <label>{STRINGS.of_form_periodo}*
              <input
                value={form.period_label}
                required
                onChange={(e) => setForm({ ...form, period_label: e.target.value })}
              />
            </label>
          </div>
          <div className="of-form-row">
            <label>{STRINGS.of_form_period_end}
              <input
                type="date"
                value={form.period_end}
                onChange={(e) => setForm({ ...form, period_end: e.target.value })}
              />
            </label>
            <label>{STRINGS.of_form_prepared_by}
              <input
                value={form.prepared_by_name}
                onChange={(e) => setForm({ ...form, prepared_by_name: e.target.value })}
              />
            </label>
            <label>{STRINGS.of_form_reviewed_by}
              <input
                value={form.reviewed_by_name}
                onChange={(e) => setForm({ ...form, reviewed_by_name: e.target.value })}
              />
            </label>
          </div>

          <div className="of-slots">
            {SLOTS.map((s) => (
              <div key={s.key} className={`of-slot ${s.required ? "req" : ""}`}>
                <label>
                  {s.label}
                  <input
                    type="file"
                    accept={s.accept}
                    multiple={s.multiple}
                    onChange={(e) => setFilesForSlot(s.key, e.target.files)}
                  />
                </label>
                {files[s.key]?.length > 0 && (
                  <span className="of-slot-count">
                    {files[s.key].length} archivo(s)
                  </span>
                )}
              </div>
            ))}
          </div>

          {err && <div className="err">{err}</div>}
          <button type="submit" className="btn primary lg">
            {STRINGS.of_generate}
          </button>
        </form>
      )}

      {stage === "processing" && (
        <div className="of-stage">
          <div className="spinner" />
          <h3>{STRINGS.of_processing}</h3>
          <p className="muted">Job #{job?.id} · estado: {job?.status}</p>
        </div>
      )}

      {stage === "done" && (
        <div className="of-stage">
          <h3>✅ {STRINGS.of_done}</h3>
          {job?.summary_json && (
            <pre className="of-summary">{JSON.stringify(job.summary_json, null, 2)}</pre>
          )}
          <div className="of-stage-actions">
            <button
              type="button"
              className="btn primary lg"
              onClick={() => downloadJob(job)}
            >
              {STRINGS.of_download}
            </button>
            <button className="btn" onClick={reset}>{STRINGS.of_new}</button>
          </div>
          <p className="muted small">
            El Excel se borra automáticamente del servidor 5 minutos después
            de la descarga. Guárdalo en tu PC.
          </p>
        </div>
      )}

      {stage === "failed" && (
        <div className="of-stage">
          <h3>❌ {STRINGS.of_failed}</h3>
          <pre className="of-summary err">
            {job?.error_message || "Error desconocido"}
          </pre>
          <button className="btn" onClick={reset}>{STRINGS.of_new}</button>
        </div>
      )}

      {recent.length > 0 && stage === "form" && (
        <div className="of-recent">
          <h3>{STRINGS.of_recent}</h3>
          <ul className="of-recent-list">
            {recent.slice(0, 10).map((j) => (
              <li key={j.id}>
                #{j.id} · {j.cliente_name} · {j.period_label}{" "}
                <span className={`badge ${j.status}`}>{j.status}</span>
                {j.status === "done" && (
                  <button
                    type="button"
                    className="link"
                    onClick={() => downloadJob(j)}
                  > · ↓ descargar</button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
