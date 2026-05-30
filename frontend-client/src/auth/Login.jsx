import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Input } from "@auditbrain/shared";
import { useAuth } from "./AuthProvider.jsx";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pwd, setPwd] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      const r = await login(email, pwd);
      if (r.password_reset_required) nav("/change-password");
      else nav("/catalog");
    } catch (e2) {
      if (e2.code === "device_unauthorized") nav("/device-blocked");
      else setErr(e2.message || "Error al iniciar sesión.");
    } finally { setBusy(false); }
  }

  return (
    <div style={{ maxWidth: 380, margin: "60px auto", padding: 30, background: "#fff", borderRadius: 8, boxShadow: "0 2px 10px rgba(0,0,0,0.08)" }}>
      <h2 style={{ marginTop: 0, textAlign: "center" }}>Portal Cliente</h2>
      <p style={{ textAlign: "center", color: "#666", fontSize: 13, marginBottom: 24 }}>
        Audit Consulting Group · Powered by Audit-IA
      </p>
      <form onSubmit={submit}>
        <Input label="Correo electrónico" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Input label="Contraseña" type="password" required value={pwd} onChange={(e) => setPwd(e.target.value)} />
        {err && <div style={{ color: "#c0392b", fontSize: 13, marginBottom: 12 }}>{err}</div>}
        <Button type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? "Ingresando..." : "Ingresar"}
        </Button>
      </form>
    </div>
  );
}
