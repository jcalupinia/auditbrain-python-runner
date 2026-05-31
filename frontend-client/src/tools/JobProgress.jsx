import { useEffect, useState } from "react";
import { Button, ProgressBar } from "@auditbrain/shared";
import { getJob, downloadJob } from "../api.js";
import { usePolling } from "../shared/usePolling.js";

export default function JobProgress({ jobId, onClose }) {
  const [job, setJob] = useState(null);
  const [err, setErr] = useState(null);

  const isTerminal = job && ["done", "error", "error_partial", "expired"].includes(job.status);

  usePolling(async () => {
    try {
      const j = await getJob(jobId);
      setJob(j);
    } catch (e) { setErr(e.message); }
  }, 2000, !isTerminal);

  if (err) return <div style={{padding:30, color:"#c0392b"}}>Error: {err}</div>;
  if (!job) return <div style={{padding:30}}>Cargando estado...</div>;

  const statusMap = {
    pending: { pct: 10, label: "En cola..." },
    processing: { pct: 60, label: "Procesando..." },
    done: { pct: 100, label: "¡Listo!" },
    error: { pct: 100, label: "Falló" },
    error_partial: { pct: 100, label: "Completado con advertencias" },
    expired: { pct: 100, label: "Expirado" },
  };
  const s = statusMap[job.status] || { pct: 0, label: job.status };

  return (
    <div style={{ maxWidth: 600, margin: "60px auto", padding: 30, background: "#fff", borderRadius: 8 }}>
      <h2>Trabajo #{job.id}</h2>
      <ProgressBar value={s.pct} label={s.label} />
      {job.status === "done" && (
        <Button
          style={{ marginTop: 16 }}
          onClick={async () => {
            try {
              await downloadJob(job.id);
            } catch (e) {
              setErr(e.message);
            }
          }}
        >
          Descargar entregable
        </Button>
      )}
      {job.status === "error" && (
        <div style={{ color: "#c0392b", marginTop: 12, background: "#fdecea", padding: 12, borderRadius: 6 }}>
          {job.error_message || "Error desconocido."}
        </div>
      )}
      <div style={{ marginTop: 24 }}>
        <Button variant="secondary" onClick={onClose}>Volver al catálogo</Button>
      </div>
      <p style={{ fontSize: 12, color: "#888", marginTop: 20 }}>
        Por política de seguridad, este archivo estará disponible solo 24 horas.
      </p>
    </div>
  );
}
