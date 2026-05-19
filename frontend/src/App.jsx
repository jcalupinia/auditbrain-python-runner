import { useState, useEffect, useCallback } from "react";
import * as api from "./api.js";

/* ---------------- Theme (oscuro premium por defecto) ---------------- */
const THEME_KEY = "ab_theme";
function useTheme() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem(THEME_KEY) || "dark"
  );
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

function Logo({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect x="1" y="1" width="30" height="30" rx="7" fill="none"
        stroke="var(--accent)" strokeWidth="2" />
      <path d="M8 22 L16 9 L24 22" fill="none" stroke="var(--accent)"
        strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      <line x1="11.5" y1="17" x2="20.5" y2="17" stroke="var(--accent)"
        strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
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
        <div className="login-brand">
          <Logo size={40} />
          <div>
            <div className="bname">AuditBrain<span> IA</span></div>
            <div className="btag">Enterprise Intelligence OS</div>
          </div>
        </div>
        <div className="login-sub">Acceso restringido · sesión con cuenta</div>
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
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="current-password"
        />
        <button className="btn primary block" disabled={busy}>
          {busy ? "Autenticando…" : "Acceder al Command Center"}
        </button>
        {err && <div className="err">{err}</div>}
        <div className="login-foot">JWT · sandbox Tier 0 · API Key no expuesta</div>
      </form>
    </div>
  );
}

/* ---------------- Primitivas de panel ---------------- */
function Panel({ title, meta, children, max }) {
  return (
    <section className="panel" style={max ? { maxWidth: max } : undefined}>
      {(title || meta) && (
        <header className="panel-h">
          <span className="panel-t">{title}</span>
          {meta && <span className="panel-m">{meta}</span>}
        </header>
      )}
      <div className="panel-b">{children}</div>
    </section>
  );
}

function ViewHead({ code, title, sub }) {
  return (
    <div className="view-head">
      <span className="view-code">{code}</span>
      <div>
        <h1>{title}</h1>
        <p>{sub}</p>
      </div>
    </div>
  );
}

/* ---------------- Vistas funcionales (lógica intacta) ---------------- */
function Metric({ label, value, state }) {
  return (
    <div className="metric">
      <div className="metric-l">{label}</div>
      <div className="metric-v">
        {state && <span className={`dot ${state}`} />}
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
  const ok = hp.state === "ok";
  return (
    <>
      <ViewHead
        code="DSH"
        title="Centro de Operaciones"
        sub="Estado consolidado de la plataforma AuditBrain IA."
      />
      {!isAdmin && (
        <div className="notice warn">
          Acceso limitado según rol. El rol <b>user</b> no incluye ejecución
          (Runner) ni administración de cuentas.
        </div>
      )}
      <Panel title="Telemetría del sistema" meta={ok ? "LIVE" : "—"}>
        <div className="metrics">
          <Metric
            label="Núcleo backend"
            value={ok ? "Operativo" : hp.state === "bad" ? "No disponible" : "Comprobando…"}
            state={ok ? "ok" : hp.state === "bad" ? "bad" : "idle"}
          />
          <Metric label="PostgreSQL" value={ok ? "Activo" : "Desconocido"} state={ok ? "ok" : "idle"} />
          <Metric label="Versión API" value={hp.data?.version || "—"} state={ok ? "ok" : "idle"} />
          <Metric
            label="Capa de auth"
            value={hp.data?.auth_enabled ? "JWT + API Key" : "Abierta"}
            state="ok"
          />
          <Metric
            label="Motor de ejecución"
            value={isAdmin ? "Habilitado" : "Restringido"}
            state={isAdmin ? "ok" : "idle"}
          />
          <Metric label="Servicio documental" value="Integrado" state="ok" />
        </div>
      </Panel>
      <Panel title="Identidad de sesión">
        <div className="kv">
          <span className="k">Operador</span><span className="v">{user.email}</span>
          <span className="k">Rol</span><span className="v">{user.role}</span>
          <span className="k">Endpoint API</span><span className="v mono">{api.getApiBase()}</span>
        </div>
      </Panel>
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
      <ViewHead
        code="RUN"
        title="Motor de Ejecución Python"
        sub="Ejecución server-side bajo sandbox Tier 0."
      />
      <div className="notice warn">
        Nodo restringido al rol <b>admin</b>. La API Key nunca sale al navegador.
      </div>
      <Panel title="Consola de ejecución" meta="PYTHON · TIER 0">
        <label>Script</label>
        <textarea value={script} onChange={(e) => setScript(e.target.value)} />
        <button className="btn primary" onClick={run} disabled={busy}>
          {busy ? "Ejecutando…" : "Ejecutar"}
        </button>
        {err && <div className="err">{err}</div>}
      </Panel>
      {out && (
        <Panel title="Resultado" meta="JSON">
          <pre>{JSON.stringify(out, null, 2)}</pre>
        </Panel>
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
      <ViewHead
        code="USR"
        title="Administración de Cuentas"
        sub="Provisión de operadores. Solo administradores."
      />
      <Panel title="Alta de operador" max={520}>
        <form onSubmit={submit}>
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
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
          <button className="btn primary" disabled={busy}>
            {busy ? "Creando…" : "Crear operador"}
          </button>
          {msg && <div className="ok-msg">{msg}</div>}
          {err && <div className="err">{err}</div>}
        </form>
      </Panel>
    </>
  );
}

function Security({ user }) {
  const rows = [
    ["Sesión JWT", "Activa (Bearer en localStorage)"],
    ["API Key en el navegador", "NO expuesta — el frontend solo usa JWT"],
    ["Motor de ejecución", "Restringido al rol admin"],
    ["Sandbox de ejecución", "Tier 0 (hardening server-side)"],
    ["GPTs / ChatGPT", "X-API-Key server-to-server (fuera del navegador)"],
    ["Endpoint backend", api.getApiBase()],
    ["Rol de sesión", user.role],
  ];
  return (
    <>
      <ViewHead
        code="SEC"
        title="Postura de Seguridad"
        sub="Modelo de seguridad vigente de AuditBrain IA."
      />
      <Panel title="Controles activos" max={680}>
        <div className="kv">
          {rows.map(([k, v]) => (
            <div key={k} style={{ display: "contents" }}>
              <span className="k">{k}</span>
              <span className="v">{v}</span>
            </div>
          ))}
        </div>
      </Panel>
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
      <ViewHead
        code="DOC"
        title="Generación Documental"
        sub="PDF, Word, Excel y PowerPoint vía el servicio documental."
      />
      <div className="notice">
        Disponible para cualquier operador autenticado. Procesado server-side
        con tu sesión JWT.
      </div>
      <Panel title="Nueva generación" max={680}>
        <form onSubmit={submit}>
          <label>Tipo de documento</label>
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
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
          <button className="btn primary" disabled={busy}>
            {busy ? "Generando…" : "Generar documento"}
          </button>
          {err && <div className="err">{err}</div>}
        </form>
      </Panel>
      {res && (
        <Panel title="Documento generado" meta="OK" max={680}>
          {url ? (
            <p>
              <a href={url} target="_blank" rel="noopener noreferrer">
                ⇩ Descargar documento
              </a>
            </p>
          ) : (
            <div className="notice warn">
              Documento generado pero sin URL de descarga directa. Respuesta
              cruda abajo.
            </div>
          )}
          <pre>{JSON.stringify(res.response ?? res, null, 2)}</pre>
        </Panel>
      )}
    </>
  );
}

/* ---------------- Command Center Shell ---------------- */
const NAV_GROUPS = [
  {
    label: "Operación",
    items: [
      { id: "dashboard", code: "DSH", label: "Centro de Operaciones" },
      { id: "documents", code: "DOC", label: "Generación Documental" },
    ],
  },
  {
    label: "Ejecución",
    items: [
      { id: "runner", code: "RUN", label: "Motor de Ejecución", admin: true },
    ],
  },
  {
    label: "Administración",
    items: [
      { id: "users", code: "USR", label: "Cuentas", admin: true },
      { id: "security", code: "SEC", label: "Seguridad" },
    ],
  },
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

  if (loading) return <div className="login-wrap"><span className="muted">Inicializando Command Center…</span></div>;
  if (!user) return <Login onLogged={loadMe} />;

  const isAdmin = user.role === "admin";
  const groups = NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((it) => !it.admin || isAdmin),
  })).filter((g) => g.items.length);
  const flat = groups.flatMap((g) => g.items);
  const current = flat.find((n) => n.id === section) ? section : "dashboard";
  const active = flat.find((n) => n.id === current);

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
      case "documents":
        return <Documents />;
      default:
        return <Dashboard user={user} />;
    }
  }

  return (
    <div className="cc">
      {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}

      <aside className={`cc-side${navOpen ? " open" : ""}`}>
        <div className="cc-brand">
          <Logo size={28} />
          <div className="cc-bname">AuditBrain<span> IA</span></div>
        </div>
        <div className="cc-side-tag">Enterprise Intelligence OS</div>
        <nav className="cc-nav">
          {groups.map((g) => (
            <div className="cc-group" key={g.label}>
              <div className="cc-group-l">{g.label}</div>
              {g.items.map((n) => (
                <button
                  key={n.id}
                  className={`cc-node${n.id === current ? " on" : ""}`}
                  onClick={() => go(n.id)}
                >
                  <span className="cc-code">{n.code}</span>
                  <span className="cc-label">{n.label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="cc-side-foot">
          <div className="cc-group-l">Próxima fase</div>
          <div className="cc-soon">Orchestration · Governance · Agentes · Workflows</div>
        </div>
      </aside>

      <header className="cc-head">
        <div className="cc-head-l">
          <button
            className="cc-burger"
            onClick={() => setNavOpen((o) => !o)}
            aria-label="Menú"
          >
            ≡
          </button>
          <div className="cc-crumb">
            <span className="cc-crumb-code">{active?.code}</span>
            <span>{active?.label}</span>
          </div>
        </div>
        <div className="cc-search" aria-hidden="true">
          <span>Búsqueda global</span><kbd>⌘K</kbd>
        </div>
        <div className="cc-head-r">
          <button className="cc-icon" onClick={toggleTheme} title="Tema">
            {theme === "dark" ? "◑" : "◐"}
          </button>
          <div className="cc-user">
            <span className="cc-user-n">{user.email}</span>
            <span className={`cc-role ${user.role}`}>{user.role}</span>
          </div>
          <button
            className="btn ghost"
            onClick={() => {
              api.clearSession();
              setUser(null);
            }}
          >
            Salir
          </button>
        </div>
      </header>

      <main className="cc-main">
        <div className="cc-work">{render()}</div>
        <aside className="cc-ctx">
          <div className="cc-ctx-h">Contexto operativo</div>
          <div className="cc-ctx-card">
            <div className="cc-ctx-k">Sesión</div>
            <div className="cc-ctx-v">{user.email}</div>
            <div className="cc-ctx-k">Privilegio</div>
            <div className="cc-ctx-v">
              <span className={`cc-role ${user.role}`}>{user.role}</span>
            </div>
            <div className="cc-ctx-k">Nodo activo</div>
            <div className="cc-ctx-v">{active?.code} · {active?.label}</div>
          </div>
          <div className="cc-ctx-card">
            <div className="cc-ctx-k">Seguridad</div>
            <div className="cc-ctx-v small">JWT activo · API Key no expuesta</div>
            <div className="cc-ctx-k">Ejecución</div>
            <div className="cc-ctx-v small">Sandbox Tier 0 · Runner solo admin</div>
          </div>
        </aside>
      </main>

      <footer className="cc-foot">
        <span><b>AuditBrain IA</b> · Enterprise Intelligence OS</span>
        <span className="cc-foot-r">
          <span><span className="dot ok" /> Operativo</span>
          <span>Auth JWT</span>
          <span>Sandbox Tier 0</span>
          <span className="mono">{new Date().toISOString().slice(0, 16).replace("T", " ")}</span>
        </span>
      </footer>
    </div>
  );
}
