import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Input } from "@auditbrain/shared";
import { useAuth } from "./AuthProvider.jsx";
import { changePassword } from "../api.js";

export default function ChangePassword() {
  const { refresh, user } = useAuth();
  const nav = useNavigate();
  const [oldP, setOldP] = useState("");
  const [newP, setNewP] = useState("");
  const [newP2, setNewP2] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    if (newP !== newP2) { setErr("Las contraseñas nuevas no coinciden."); return; }
    if (newP.length < 8) { setErr("Mínimo 8 caracteres."); return; }
    setBusy(true);
    try {
      await changePassword(oldP, newP);
      await refresh();
      nav("/catalog");
    } catch (e2) {
      setErr(e2.message);
    } finally { setBusy(false); }
  }

  return (
    <div style={{ maxWidth: 420, margin: "60px auto", padding: 30, background: "#fff", borderRadius: 8, boxShadow: "0 2px 10px rgba(0,0,0,0.08)" }}>
      <h2 style={{ marginTop: 0 }}>Cambia tu contraseña</h2>
      <p style={{ color: "#666", fontSize: 13 }}>
        Por seguridad, debes establecer una nueva contraseña antes de continuar.
      </p>
      <form onSubmit={submit}>
        <Input label="Contraseña actual (temporal)" type="password" required value={oldP} onChange={(e) => setOldP(e.target.value)} />
        <Input label="Nueva contraseña (mín. 8 caracteres)" type="password" required value={newP} onChange={(e) => setNewP(e.target.value)} />
        <Input label="Repite la nueva contraseña" type="password" required value={newP2} onChange={(e) => setNewP2(e.target.value)} />
        {err && <div style={{ color: "#c0392b", fontSize: 13, marginBottom: 12 }}>{err}</div>}
        <Button type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? "Cambiando..." : "Cambiar contraseña"}
        </Button>
      </form>
    </div>
  );
}
