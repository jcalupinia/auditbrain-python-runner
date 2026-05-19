import { useState, useEffect, useCallback } from "react";
import * as api from "./api.js";

/* ---------------- Theme ---------------- */
const THEME_KEY = "ab_theme";
function useTheme() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem(THEME_KEY) || "light"
  );
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "light" ? "dark" : "light"))];
}

/* ---------------- Login ---------------- */
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
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="brand">
          <span className="logo">AB</span> AuditBrain
        </div>
        <div className="sub">Plataforma privada · acceso con cuenta</div>
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
        <button className="btn" disabled={busy}>
          {busy ? "Entrando…" : "Entrar"}
        </button>
        {err && <div className="err">{err}</div>}
      </form>
    </div>
  );
}

/* ---------------- Views ---------------- */
function StatCard({ label, value, status }) {
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className="value">
        {status && <span className={`dot ${status}`} />}
        {value}
      </div>
    </div>
  );
}

function Dashboard({ user }) {
  const [hp, setHp] = useState({ state: "idle", data: null });
  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((d) => alive && setHp({ state: "ok", data: d }))
      .catch(() => alive && setHp({ state: "bad", data: null }));
    return () => {
      alive = false;
    };
  }, []);
  const isAdmin = user.role === "admin";
  return (
    <>
      <h1 className="page-title">Dashboard</h1>
      <p className="page-sub">Estado general de la plataforma AuditBrain.</p>
      {!isAdmin && (
        <div className="notice warn">
          Acceso limitado según rol. Tu rol <b>user</b> no incluye el Python
          Runner ni la gestión de usuarios.
        </div>
      )}
      <div className="grid">
        <StatCard
          label="Estado backend"
          value={
            hp.state === "ok"
              ? "Operativo"
              : hp.state === "bad"
              ? "No disponible"
              : "Comprobando…"
          }
          status={hp.state === "ok" ? "ok" : hp.state === "bad" ? "bad" : "idle"}
        />
        <StatCard
          label="PostgreSQL"
          value={hp.state === "ok" ? "Activo" : "Desconocido"}
          status={hp.state === "ok" ? "ok" : "idle"}
        />
        <StatCard label="Usuario actual" value={user.email} />
        <StatCard
          label="Rol actual"
          value={user.role}
          status={isAdmin ? "ok" : "idle"}
        />
        <StatCard
          label="Python Runner"
          value={isAdmin ? "Disponible" : "Restringido"}
          status={isAdmin ? "ok" : "idle"}
        />
        <StatCard label="Frontend" value="Desplegado (SaaS v2)" status="ok" />
        <StatCard
          label="Versión API"
          value={hp.data?.version || "—"}
          status={hp.state === "ok" ? "ok" : "idle"}
        />
        <StatCard
          label="Auth"
          value={hp.data?.auth_enabled ? "JWT + API Key" : "Abierta"}
          status="ok"
        />
      </div>
    </>
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
    <>
      <h1 className="page-title">Python Runner</h1>
      <p className="page-sub">
        Ejecución de código Python en el sandbox del backend.
      </p>
      <div className="notice warn">
        Acción restringida al rol <b>admin</b>. Se ejecuta server-side bajo
        sandbox Tier 0.
      </div>
      <div className="card">
        <label>Script</label>
        <textarea value={script} onChange={(e) => setScript(e.target.value)} />
        <button className="btn" onClick={run} disabled={busy}>
          {busy ? "Ejecutando…" : "Ejecutar"}
        </button>
        {err && <div className="err">{err}</div>}
      </div>
      {out && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Resultado</h3>
          <pre>{JSON.stringify(out, null, 2)}</pre>
        </div>
      )}
    </>
  );
}

function Users() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setMsg("");
    setErr("");
    setBusy(true);
    try {
      const u = await api.createUser(email, password, role);
      setMsg(`Usuario creado: ${u.email} · rol ${u.role}`);
      setEmail("");
      setPassword("");
      setRole("user");
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="page-title">Usuarios</h1>
      <p className="page-sub">Alta de cuentas. Solo administradores.</p>
      <div className="card" style={{ maxWidth: 460 }}>
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
          <button className="btn" disabled={busy}>
            {busy ? "Creando…" : "Crear usuario"}
          </button>
          {msg && <div className="ok-msg">{msg}</div>}
          {err && <div className="err">{err}</div>}
        </form>
      </div>
    </>
  );
}

function Security({ user }) {
  const rows = [
    ["Sesión JWT", "Activa (Bearer en localStorage)"],
    ["API Key en el navegador", "NO expuesta — el frontend solo usa JWT"],
    ["Python Runner", "Restringido al rol admin"],
    ["Sandbox de ejecución", "Tier 0 (hardening server-side)"],
    ["GPTs / ChatGPT", "X-API-Key server-to-server (fuera del navegador)"],
    ["Backend API", api.getApiBase()],
    ["Tu rol", user.role],
  ];
  return (
    <>
      <h1 className="page-title">Seguridad</h1>
      <p className="page-sub">Modelo de seguridad vigente de AuditBrain.</p>
      <div className="card" style={{ maxWidth: 620 }}>
        <div className="kv">
          {rows.map(([k, v]) => (
            <div key={k} style={{ display: "contents" }}>
              <span className="k">{k}</span>
              <span className="v">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function GptIntegrations() {
  return (
    <>
      <h1 className="page-title">GPT Integrations</h1>
      <p className="page-sub">
        Arquitectura de integración con los GPTs de ChatGPT.
      </p>
      <div className="card">
        <div className="flow">
          <span className="node">ChatGPT GPTs</span>
          <span className="arrow">→</span>
          <span className="node">AuditBrain Router</span>
          <span className="arrow">→</span>
          <span className="node">Runner / Documents</span>
        </div>
        <p className="muted" style={{ marginTop: 16 }}>
          Los GPTs autentican server-to-server con <b>X-API-Key</b>; esa clave
          nunca llega al navegador. El panel de gestión de integraciones estará
          disponible en una próxima fase.
        </p>
      </div>
    </>
  );
}

const DOC_FORMATS = [
  { value: "pdf", label: "PDF" },
  { value: "word", label: "Word (.docx)" },
  { value: "excel", label: "Excel (.xlsx)" },
  { value: "ppt", label: "PowerPoint (.pptx)" },
];

function Documents() {
  const [format, setFormat] = useState("pdf");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setRes(null);
    setBusy(true);
    try {
      const out = await api.generateDocument({ format, title, content });
      if (out && out.status === "error") {
        setErr(out.error || "El servicio documental devolvió un error.");
      } else {
        setRes(out);
      }
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  const url = res ? api.findDownloadUrl(res) : null;

  return (
    <>
      <h1 className="page-title">Documentos</h1>
      <p className="page-sub">
        Generación de PDF, Word, Excel y PowerPoint vía el servicio documental
        de AuditBrain.
      </p>
      <div className="notice">
        Disponible para cualquier usuario autenticado. Se procesa server-side
        con tu sesión JWT (la API Key nunca sale al navegador).
      </div>
      <div className="card" style={{ maxWidth: 620 }}>
        <form onSubmit={submit}>
          <label>Tipo de documento</label>
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value)}
          >
            {DOC_FORMATS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
          <label>Título</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Informe trimestral"
            required
          />
          <label>Contenido principal</label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Texto principal del documento…"
            style={{ minHeight: 160 }}
            required
          />
          <button className="btn" disabled={busy}>
            {busy ? "Generando…" : "Generar documento"}
          </button>
          {err && <div className="err">{err}</div>}
        </form>
      </div>

      {res && (
        <div className="card" style={{ marginTop: 16, maxWidth: 620 }}>
          <h3>Documento generado</h3>
          {url ? (
            <p>
              <a href={url} target="_blank" rel="noopener noreferrer">
                ⇩ Descargar documento
              </a>
            </p>
          ) : (
            <div className="notice warn">
              Documento generado pero el servicio no devolvió una URL de
              descarga directa. Respuesta cruda abajo.
            </div>
          )}
          <pre>{JSON.stringify(res.response ?? res, null, 2)}</pre>
        </div>
      )}
    </>
  );
}

function Placeholder({ title, sub, icon, text }) {
  return (
    <>
      <h1 className="page-title">{title}</h1>
      <p className="page-sub">{sub}</p>
      <div className="card">
        <div className="placeholder">
          <div className="big">{icon}</div>
          <div>{text}</div>
          <div className="muted" style={{ marginTop: 8 }}>
            Módulo en preparación.
          </div>
        </div>
      </div>
    </>
  );
}

/* ---------------- Shell ---------------- */
const NAV = [
  { id: "dashboard", label: "Dashboard", ico: "▦" },
  { id: "runner", label: "Python Runner", ico: "⌘", admin: true },
  { id: "users", label: "Usuarios", ico: "☻", admin: true },
  { id: "documents", label: "Documentos", ico: "▤" },
  { id: "gpt", label: "GPT Integrations", ico: "✦" },
  { id: "security", label: "Seguridad", ico: "⛉" },
  { id: "logs", label: "Logs", ico: "≣" },
];

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [section, setSection] = useState("dashboard");
  const [navOpen, setNavOpen] = useState(false);
  const [theme, toggleTheme] = useTheme();

  const loadMe = useCallback(async () => {
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
  }, []);

  useEffect(() => {
    loadMe();
  }, [loadMe]);

  if (loading)
    return <div className="login-wrap muted">Cargando…</div>;
  if (!user) return <Login onLogged={loadMe} />;

  const isAdmin = user.role === "admin";
  const items = NAV.filter((n) => !n.admin || isAdmin);
  const current = items.find((n) => n.id === section) ? section : "dashboard";

  function go(id) {
    setSection(id);
    setNavOpen(false);
  }

  function render() {
    switch (current) {
      case "runner":
        return isAdmin ? <Runner /> : <Dashboard user={user} />;
      case "users":
        return isAdmin ? <Users /> : <Dashboard user={user} />;
      case "security":
        return <Security user={user} />;
      case "gpt":
        return <GptIntegrations />;
      case "documents":
        return <Documents />;
      case "logs":
        return (
          <Placeholder
            title="Logs"
            sub="Auditoría de actividad."
            icon="≣"
            text="Historial de ejecuciones estará disponible en próxima fase."
          />
        );
      default:
        return <Dashboard user={user} />;
    }
  }

  return (
    <div className="app">
      {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}
      <aside className={`sidebar${navOpen ? " open" : ""}`}>
        <div className="brand">
          <span className="logo">AB</span> AuditBrain
        </div>
        <div className="nav-sep">Plataforma</div>
        <nav className="nav">
          {items.map((n) => (
            <button
              key={n.id}
              className={n.id === current ? "active" : ""}
              onClick={() => go(n.id)}
            >
              <span className="ico">{n.ico}</span>
              {n.label}
            </button>
          ))}
        </nav>
      </aside>

      <header className="header">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            className="iconbtn hamburger"
            onClick={() => setNavOpen((o) => !o)}
            aria-label="Menú"
          >
            ☰
          </button>
          <h2>{items.find((n) => n.id === current)?.label}</h2>
        </div>
        <div className="right">
          <button
            className="iconbtn"
            onClick={toggleTheme}
            aria-label="Cambiar tema"
            title="Tema claro/oscuro"
          >
            {theme === "light" ? "☾" : "☀"}
          </button>
          <div className="userchip">
            <b>{user.email}</b>
            <span className={`badge ${user.role}`}>{user.role}</span>
          </div>
          <button
            className="btn ghost sm"
            onClick={() => {
              api.clearSession();
              setUser(null);
            }}
          >
            Salir
          </button>
        </div>
      </header>

      <main className="main">{render()}</main>
    </div>
  );
}
