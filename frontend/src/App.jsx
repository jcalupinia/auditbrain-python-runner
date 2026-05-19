import { useState, useEffect } from "react";
import * as api from "./api.js";

function Login({ onLogged }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await api.login(email, password);
      onLogged();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="wrap">
      <div className="card">
        <h1>AuditBrain</h1>
        <h2>Acceso privado</h2>
        <form onSubmit={submit}>
          <label>Email</label>
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
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
          <button disabled={busy}>{busy ? "Entrando…" : "Entrar"}</button>
          {err && <div className="err">{err}</div>}
        </form>
      </div>
    </div>
  );
}

function Runner() {
  const [script, setScript] = useState("result = 2 + 2");
  const [out, setOut] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function run() {
    setErr("");
    setOut(null);
    setBusy(true);
    try {
      setOut(await api.runPython(script));
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Ejecutar Python (solo admin)</h2>
      <textarea value={script} onChange={(e) => setScript(e.target.value)} />
      <button onClick={run} disabled={busy}>
        {busy ? "Ejecutando…" : "Ejecutar"}
      </button>
      {err && <div className="err">{err}</div>}
      {out && <pre>{JSON.stringify(out, null, 2)}</pre>}
    </div>
  );
}

function CreateUser() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  async function submit(e) {
    e.preventDefault();
    setMsg("");
    setErr("");
    try {
      const u = await api.createUser(email, password, role);
      setMsg(`Usuario creado: ${u.email} (${u.role})`);
      setEmail("");
      setPassword("");
    } catch (e2) {
      setErr(e2.message);
    }
  }

  return (
    <div className="card">
      <h2>Alta de usuario (solo admin)</h2>
      <form onSubmit={submit}>
        <label>Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <label>Contraseña (mín. 8)</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={8}
          required
        />
        <label>Rol</label>
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
        <button>Crear</button>
        {msg && <div className="muted">{msg}</div>}
        {err && <div className="err">{err}</div>}
      </form>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  async function loadMe() {
    if (!api.getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      api.clearSession();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMe();
  }, []);

  if (loading) return <div className="wrap">Cargando…</div>;
  if (!user) return <Login onLogged={loadMe} />;

  const isAdmin = user.role === "admin";

  return (
    <div className="wrap">
      <div className="card">
        <div className="row">
          <div>
            <h1>AuditBrain</h1>
            <span className="muted">
              {user.email} · rol <b>{user.role}</b>
            </span>
          </div>
          <button
            className="linkbtn"
            onClick={() => {
              api.clearSession();
              setUser(null);
            }}
          >
            Salir
          </button>
        </div>
      </div>

      {isAdmin ? (
        <>
          <Runner />
          <CreateUser />
        </>
      ) : (
        <div className="card">
          <h2>Sin permisos de ejecución</h2>
          <p className="muted">
            Tu rol es <b>{user.role}</b>. El runner está restringido a
            administradores. Contacta a un admin si necesitas acceso.
          </p>
        </div>
      )}
    </div>
  );
}
