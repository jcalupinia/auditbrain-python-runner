import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@auditbrain/shared";
import { getCatalog, createJob } from "../api.js";
import JobProgress from "./JobProgress.jsx";

export default function ToolShell() {
  const { toolCode } = useParams();
  const nav = useNavigate();
  const [tool, setTool] = useState(null);
  const [files, setFiles] = useState({}); // {slot: File or [File,...]}
  const [jobId, setJobId] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getCatalog().then((r) => {
      for (const c of r.categories) {
        const t = c.tools.find((x) => x.code === toolCode);
        if (t) { setTool(t); return; }
      }
      setErr("Herramienta no encontrada.");
    }).catch((e) => setErr(e.message));
  }, [toolCode]);

  function onFileChange(slotName, fileList, multi) {
    setFiles((prev) => ({
      ...prev,
      [slotName]: multi ? Array.from(fileList) : fileList[0] || null,
    }));
  }

  async function submit() {
    setErr(null); setBusy(true);
    try {
      const r = await createJob(toolCode, files);
      setJobId(r.id);
    } catch (e) {
      setErr(e.message);
    } finally { setBusy(false); }
  }

  if (!tool) return <div style={{padding:30}}>{err || "Cargando..."}</div>;
  if (jobId) return <JobProgress jobId={jobId} onClose={() => nav("/catalog")} />;

  return (
    <div style={{ maxWidth: 720, margin: "30px auto", padding: 20 }}>
      <button onClick={() => nav("/catalog")} style={{ background: "none", border: "none", color: "#0a2540", cursor: "pointer", marginBottom: 16 }}>
        ← Volver al catálogo
      </button>
      <h2>{tool.label}</h2>
      <p style={{ color: "#555" }}>{tool.description}</p>

      <div style={{ background: "#fff", padding: 24, borderRadius: 8, marginTop: 20 }}>
        {tool.slots.map((s) => (
          <div key={s.name} style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontWeight: 600, marginBottom: 6 }}>
              {s.name} {s.required && <span style={{ color: "#c0392b" }}>*</span>}
            </label>
            <input
              type="file"
              accept={s.mimes_allowed.join(",")}
              multiple={s.multi}
              onChange={(e) => onFileChange(s.name, e.target.files, s.multi)}
            />
            <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
              Tipos permitidos: {s.mimes_allowed.join(", ")} {s.multi && "(múltiples)"}
            </div>
          </div>
        ))}
        {err && <div style={{ color: "#c0392b", marginBottom: 12 }}>{err}</div>}
        <Button onClick={submit} disabled={busy}>
          {busy ? "Enviando..." : "Procesar"}
        </Button>
      </div>
    </div>
  );
}
