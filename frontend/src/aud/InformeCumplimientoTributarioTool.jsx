import { useState, useEffect, useRef, useCallback } from "react";
import * as api from "../api.js";
import { STRINGS } from "./strings.js";

export default function InformeCumplimientoTributarioTool({ projectId }) {
  const [stage, setStage] = useState("form"); // form | processing | done | failed
  const [form, setForm] = useState({
    cliente_name: "",
    ejercicio: "",
    fecha_carga_sri: "",
    firma_auditora: "audit_consulting",
    hay_recomendaciones: false,
    texto_recomendaciones: "",
    override_fecha_emision: "",
    override_marco_contable: "",
    override_fecha_declaracion_ir: "",
  });
  const [files, setFiles] = useState({});
  const [job, setJob] = useState(null);
  const [recent, setRecent] = useState([]);
  const [err, setErr] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const pollRef = useRef();

  const loadRecent = useCallback(async () => {
    if (!projectId) return;
    try { setRecent(await api.listIctJobs(projectId)); } catch { /* */ }
  }, [projectId]);

  useEffect(() => { loadRecent(); }, [loadRecent]);
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  function setFile(slot, fileList) {
    setFiles((prev) => ({ ...prev, [slot]: (fileList && fileList[0]) || null }));
  }

  // Autocompletar los 3 campos "auto" al tener ambos PDFs
  async function tryPreview(next) {
    if (!(next.informe && next.f101)) return;
    setPreviewing(true);
    try {
      const p = await api.parseIctPreview(next);
      setForm((f) => ({
        ...f,
        override_fecha_emision: p.fecha_emision || f.override_fecha_emision,
        override_marco_contable: p.marco_contable || f.override_marco_contable,
        override_fecha_declaracion_ir: p.fecha_declaracion_ir || f.override_fecha_declaracion_ir,
      }));
    } catch (e) {
      setErr(`No se pudo autocompletar: ${e.message}`);
    } finally {
      setPreviewing(false);
    }
  }

  function onFile(slot, fileList) {
    const file = (fileList && fileList[0]) || null;
    const next = { ...files, [slot]: file };
    setFiles(next);
    if (slot === "informe" || slot === "f101") tryPreview(next);
  }

  async function submit(e) {
    e.preventDefault();
    setErr("");
    if (!(files.informe && files.f101)) { setErr(STRINGS.ict_need_files); return; }
    try {
      const j = await api.createIctJob({ project_id: projectId, ...form }, files);
      setJob(j);
      setStage("processing");
      pollRef.current = setInterval(async () => {
        try {
          const u = await api.getIctJob(j.id);
          setJob(u);
          if (u.status === "done") { clearInterval(pollRef.current); setStage("done"); loadRecent(); }
          else if (u.status === "failed" || u.status === "expired") { clearInterval(pollRef.current); setStage("failed"); }
        } catch { /* intermitencia */ }
      }, 2000);
    } catch (e2) { setErr(e2.message); }
  }

  function reset() {
    setStage("form"); setJob(null); setFiles({}); setErr("");
    setForm({
      cliente_name: "", ejercicio: "", fecha_carga_sri: "",
      firma_auditora: "audit_consulting", hay_recomendaciones: false,
      texto_recomendaciones: "", override_fecha_emision: "",
      override_marco_contable: "", override_fecha_declaracion_ir: "",
    });
  }

  async function downloadJob(j) {
    try {
      const safe = (j.cliente_name || "cliente").replace(/[^a-zA-Z0-9]/g, "_");
      await api.downloadIctJob(j.id, `Informe_Cumplimiento_Tributario_${safe}_${j.ejercicio}.docx`);
    } catch (e) { setErr(`Error al descargar: ${e.message}`); }
  }

  if (!projectId) {
    return <div className="notice warn">Selecciona un proyecto del módulo AUD primero.</div>;
  }

  return (
    <div className="of-tool">
      <header className="of-head">
        <h2>{STRINGS.ict_title}</h2>
        <p className="muted">{STRINGS.ict_subtitle}</p>
      </header>

      {stage === "form" && (
        <form onSubmit={submit} className="of-form">
          <div className="of-form-row">
            <label>{STRINGS.ict_cliente}*
              <input value={form.cliente_name} required
                onChange={(e) => setForm({ ...form, cliente_name: e.target.value })} />
            </label>
            <label>{STRINGS.ict_ejercicio}*
              <input value={form.ejercicio} required
                onChange={(e) => setForm({ ...form, ejercicio: e.target.value })} />
            </label>
            <label>{STRINGS.ict_fecha_carga_sri}
              <input value={form.fecha_carga_sri} placeholder="08 de julio de 2026"
                onChange={(e) => setForm({ ...form, fecha_carga_sri: e.target.value })} />
            </label>
          </div>

          <div className="of-form-row">
            <label>
              <input type="checkbox" checked={form.hay_recomendaciones}
                onChange={(e) => setForm({ ...form, hay_recomendaciones: e.target.checked })} />
              {" "}{STRINGS.ict_recomendaciones_q}
            </label>
          </div>
          {form.hay_recomendaciones && (
            <div className="of-form-row">
              <label style={{ flex: 1 }}>{STRINGS.ict_recomendaciones_txt}
                <textarea rows={4} value={form.texto_recomendaciones}
                  onChange={(e) => setForm({ ...form, texto_recomendaciones: e.target.value })} />
              </label>
            </div>
          )}

          <div className="of-firma">
            <div className="of-firma-label">{STRINGS.ict_firma}*</div>
            <div className="of-firma-options">
              <label className="of-firma-opt">
                <input type="radio" name="firma" value="audit_consulting"
                  checked={form.firma_auditora === "audit_consulting"}
                  onChange={(e) => setForm({ ...form, firma_auditora: e.target.value })} />
                <span>{STRINGS.of_firma_audit_consulting}</span>
              </label>
              <label className="of-firma-opt">
                <input type="radio" name="firma" value="partner_auditing"
                  checked={form.firma_auditora === "partner_auditing"}
                  onChange={(e) => setForm({ ...form, firma_auditora: e.target.value })} />
                <span>{STRINGS.of_firma_partner_auditing}</span>
              </label>
            </div>
          </div>

          <div className="of-slots">
            <div className="of-slot req">
              <label>{STRINGS.ict_slot_informe}
                <input type="file" accept="application/pdf"
                  onChange={(e) => onFile("informe", e.target.files)} />
              </label>
              {files.informe && <span className="of-slot-count">1 archivo</span>}
            </div>
            <div className="of-slot req">
              <label>{STRINGS.ict_slot_f101}
                <input type="file" accept="application/pdf"
                  onChange={(e) => onFile("f101", e.target.files)} />
              </label>
              {files.f101 && <span className="of-slot-count">1 archivo</span>}
            </div>
            <div className="of-slot">
              <label>{STRINGS.ict_slot_diferencias}
                <input type="file" accept="application/pdf"
                  onChange={(e) => setFile("diferencias", e.target.files)} />
              </label>
              {files.diferencias && <span className="of-slot-count">1 archivo</span>}
            </div>
          </div>

          <div className="of-form-row">
            <label>{STRINGS.ict_fecha_emision}
              <input value={form.override_fecha_emision}
                onChange={(e) => setForm({ ...form, override_fecha_emision: e.target.value })} />
            </label>
            <label>{STRINGS.ict_marco}
              <select value={form.override_marco_contable}
                onChange={(e) => setForm({ ...form, override_marco_contable: e.target.value })}>
                <option value="">(auto)</option>
                <option value="pymes">NIIF para las PYMES</option>
                <option value="plenas">NIIF plenas</option>
              </select>
            </label>
            <label>{STRINGS.ict_fecha_declaracion}
              <input value={form.override_fecha_declaracion_ir}
                onChange={(e) => setForm({ ...form, override_fecha_declaracion_ir: e.target.value })} />
            </label>
          </div>
          {previewing && <p className="muted small">Autocompletando desde los PDFs…</p>}

          {err && <div className="err">{err}</div>}
          <button type="submit" className="btn primary lg">{STRINGS.ict_generate}</button>
        </form>
      )}

      {stage === "processing" && (
        <div className="of-stage">
          <div className="spinner" />
          <h3>{STRINGS.ict_processing}</h3>
          <p className="muted">Job #{job?.id} · {job?.status}</p>
        </div>
      )}

      {stage === "done" && (
        <div className="of-stage">
          <h3>✅ {STRINGS.ict_done}</h3>
          <div className="of-stage-actions">
            <button type="button" className="btn primary lg" onClick={() => downloadJob(job)}>
              {STRINGS.ict_download}
            </button>
            <button className="btn" onClick={reset}>{STRINGS.ict_new}</button>
          </div>
        </div>
      )}

      {stage === "failed" && (
        <div className="of-stage">
          <h3>❌ {STRINGS.ict_failed}</h3>
          <pre className="of-summary err">{job?.error_message || "Error desconocido"}</pre>
          <button className="btn" onClick={reset}>{STRINGS.ict_new}</button>
        </div>
      )}

      {recent.length > 0 && stage === "form" && (
        <div className="of-recent">
          <h3>{STRINGS.ict_recent}</h3>
          <ul className="of-recent-list">
            {recent.slice(0, 10).map((j) => (
              <li key={j.id}>
                #{j.id} · {j.cliente_name} · {j.ejercicio}{" "}
                <span className={`badge ${j.status}`}>{j.status}</span>
                {j.status === "done" && (
                  <button type="button" className="link" onClick={() => downloadJob(j)}>
                    {" "}· ↓ descargar
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
