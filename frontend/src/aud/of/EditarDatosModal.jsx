import { useEffect, useState } from "react";
import * as api from "../../api.js";
import { STRINGS } from "../strings.js";
import { datosEncargoParaGuardar } from "./ofLogic.js";

const FIRMAS = [
  { value: "audit_consulting", label: STRINGS.of_firma_audit_consulting },
  { value: "partner_auditing", label: STRINGS.of_firma_partner_auditing },
];

function datosIniciales(job) {
  return {
    cliente_name: job?.cliente_name || "",
    period_label: job?.period_label || "",
    period_end: job?.period_end || "",
    prepared_by_name: job?.prepared_by_name || "",
    reviewed_by_name: job?.reviewed_by_name || "",
    firma_auditora: job?.firma_auditora || "audit_consulting",
  };
}

/*
 * Datos del encargo (cliente, período, corte, preparado/revisado por,
 * firma auditora) — crea el job (mode="crear", sin job activo) o
 * actualiza sus metadatos in situ (mode="editar", job activo) vía
 * PATCH /jobs/{id} (actualizarJobOF), sin tocar archivos ni clasificación.
 */
export default function EditarDatosModal({ open, mode, projectId, job, onClose, onSaved }) {
  const [form, setForm] = useState(() => datosIniciales(job));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setForm(datosIniciales(job));
      setError("");
    }
  }, [open, job]);

  if (!open) return null;

  function set(campo, valor) {
    setForm((prev) => ({ ...prev, [campo]: valor }));
  }

  async function submit(e) {
    e.preventDefault();
    if (!form.cliente_name.trim() || !form.period_label.trim()) {
      setError(`${STRINGS.of_form_cliente} y ${STRINGS.of_form_periodo} son obligatorios.`);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const datos = datosEncargoParaGuardar(form);
      const guardado =
        mode === "editar" && job
          ? await api.actualizarJobOF(job.id, datos)
          : await api.crearJobOF({ project_id: projectId, ...datos });
      onSaved(guardado);
      onClose();
    } catch (e2) {
      setError(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 20,
      }}
      onClick={busy ? undefined : onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--panel)", border: "1px solid var(--line)",
          borderRadius: 14, maxWidth: 620, width: "100%",
          maxHeight: "88vh", overflow: "auto",
        }}
      >
        <header style={{
          padding: "16px 20px", borderBottom: "1px solid var(--line-soft)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span className="pc-panel-t">
            {mode === "editar" ? STRINGS.of_modal_title_editar : STRINGS.of_modal_title_nuevo}
          </span>
          <button
            type="button"
            className="pc-chip"
            onClick={onClose}
            disabled={busy}
            style={{ padding: "4px 10px" }}
          >
            ×
          </button>
        </header>

        <form onSubmit={submit} style={{ padding: 20 }}>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <label style={{ flex: "1 1 220px" }}>
              {STRINGS.of_form_cliente}*
              <input
                value={form.cliente_name}
                required
                onChange={(e) => set("cliente_name", e.target.value)}
              />
            </label>
            <label style={{ flex: "1 1 220px" }}>
              {STRINGS.of_form_periodo}*
              <input
                value={form.period_label}
                required
                onChange={(e) => set("period_label", e.target.value)}
              />
            </label>
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <label style={{ flex: "1 1 160px" }}>
              {STRINGS.of_form_period_end}
              <input
                type="date"
                value={form.period_end}
                onChange={(e) => set("period_end", e.target.value)}
              />
            </label>
            <label style={{ flex: "1 1 200px" }}>
              {STRINGS.of_form_prepared_by}
              <input
                value={form.prepared_by_name}
                onChange={(e) => set("prepared_by_name", e.target.value)}
              />
            </label>
            <label style={{ flex: "1 1 200px" }}>
              {STRINGS.of_form_reviewed_by}
              <input
                value={form.reviewed_by_name}
                onChange={(e) => set("reviewed_by_name", e.target.value)}
              />
            </label>
          </div>

          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: 12, color: "var(--text-soft)", marginBottom: 8 }}>
              {STRINGS.of_form_firma}*
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {FIRMAS.map((f) => (
                <button
                  key={f.value}
                  type="button"
                  className={form.firma_auditora === f.value ? "pc-chip on" : "pc-chip"}
                  onClick={() => set("firma_auditora", f.value)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {error && <div className="err">{error}</div>}

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 20 }}>
            <button type="button" className="pc-btn secondary" onClick={onClose} disabled={busy}>
              {STRINGS.of_modal_cancelar}
            </button>
            <button type="submit" className="pc-btn" disabled={busy}>
              {busy
                ? STRINGS.of_modal_guardando
                : mode === "editar" ? STRINGS.of_modal_guardar : STRINGS.of_modal_crear}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
