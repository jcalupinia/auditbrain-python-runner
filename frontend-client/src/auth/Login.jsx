import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./AuthProvider.jsx";
import "./login.css";

/* ============================================================
   Portal Cliente · pantalla de login
   Espejo del Command Center (frontend/src/App.jsx) con la
   diferencia de la frase "PORTAL CLIENTES" sobre la tarjeta.
   ============================================================ */

function AssetImg({ src, alt, className, fallback }) {
  const [failed, setFailed] = useState(false);
  if (failed || !src) return fallback || null;
  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setFailed(true)}
    />
  );
}

function BrandMark({ size = 38 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect
        x="2" y="2" width="36" height="36" rx="9"
        fill="none" stroke="var(--accent)" strokeWidth="2.5"
      />
      <path
        d="M11 28 L20 12 L29 28"
        fill="none" stroke="var(--accent)" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round"
      />
      <line
        x1="15" y1="22" x2="25" y2="22"
        stroke="var(--accent)" strokeWidth="3" strokeLinecap="round"
      />
    </svg>
  );
}

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pwd, setPwd] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const r = await login(email, pwd);
      if (r.password_reset_required) nav("/change-password");
      else nav("/catalog");
    } catch (e2) {
      if (e2.code === "device_unauthorized") nav("/device-blocked");
      else setErr(e2.message || "Error al iniciar sesión.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ab-login">
      {/* Columna izquierda: figura IA. */}
      <div className="ab-login-aside">
        <div className="ab-login-figure">
          <AssetImg
            src="/assets/ai-girl-figure.png"
            alt=""
            className="ab-login-figure-img"
            fallback={
              <div className="ab-login-figure-ph">
                <span>AUDIT</span>
                <b>IA</b>
              </div>
            }
          />
        </div>
      </div>

      {/* Logo corporativo superpuesto al centro. */}
      <AssetImg
        src="/assets/logo-auditconsulting-group.png"
        alt="Audit Consulting Group"
        className="ab-login-logo"
        fallback={null}
      />

      {/* Columna derecha: tarjeta del formulario. */}
      <form className="ab-login-card" onSubmit={submit}>
        <div className="ab-login-brand">
          <BrandMark size={38} />
          <div>
            <div className="ab-login-bname">
              AuditBrain<span> IA</span>
            </div>
            <div className="ab-login-btag">Enterprise Intelligence OS</div>
          </div>
        </div>

        <div className="ab-login-portal-tag">
          <span aria-hidden="true">●</span> Portal Clientes
        </div>

        <div className="ab-login-sub">
          Acceso restringido · sesión vinculada al dispositivo
        </div>

        <label>Email corporativo</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="username"
        />

        <label>Contraseña</label>
        <input
          type="password"
          value={pwd}
          onChange={(e) => setPwd(e.target.value)}
          required
          autoComplete="current-password"
        />

        <button className="ab-login-btn" type="submit" disabled={busy}>
          {busy ? "Autenticando…" : "Ingresar al Portal"}
        </button>

        {err && <div className="ab-login-err">{err}</div>}

        <div className="ab-login-foot">
          JWT · sesión única por dispositivo · API Key no expuesta
        </div>
      </form>
    </div>
  );
}
