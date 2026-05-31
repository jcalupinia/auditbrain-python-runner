import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Input } from "@auditbrain/shared";
import { createSession } from "./ictApi.js";

export default function ICTLanding() {
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
    if (!/^\d{10,13}$/.test(ruc)) { setErr("RUC debe ser 10-13 dígitos"); return; }
    if (!razon.trim()) { setErr("Razón social es requerida"); return; }
    if (!/^\d{4}$/.test(anio)) { setErr("Año fiscal: 4 dígitos"); return; }
    setBusy(true);
    try {
      await createSession({
        ejercicio_fiscal: anio,
        ruc,
        razon_social: razon,
        numero_adhesivo: adhesivo || null,
      });
      nav("/tools/ICT_2025");
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 480, margin: "60px auto", padding: 30, background: "#fff", borderRadius: 8, boxShadow: "0 2px 10px rgba(0,0,0,0.08)" }}>
      <h2 style={{ marginTop: 0 }}>Nuevo proyecto ICT 2025</h2>
      <p style={{ color: "#666", fontSize: 14 }}>
        Crea tu Informe de Cumplimiento Tributario del SRI. Sube los documentos
        cuando los tengas; el proyecto persiste 90 días.
      </p>
      <form onSubmit={submit}>
        <Input label="RUC (10-13 dígitos)" value={ruc} onChange={(e) => setRuc(e.target.value)} required />
        <Input label="Razón Social" value={razon} onChange={(e) => setRazon(e.target.value)} required />
        <Input label="Ejercicio Fiscal" value={anio} onChange={(e) => setAnio(e.target.value)} required />
        <Input label="Número de Adhesivo (opcional)" value={adhesivo} onChange={(e) => setAdhesivo(e.target.value)} />
        {err && <div style={{ color: "#c0392b", marginBottom: 12 }}>{err}</div>}
        <Button type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? "Creando..." : "Crear proyecto ICT"}
        </Button>
      </form>
    </div>
  );
}
