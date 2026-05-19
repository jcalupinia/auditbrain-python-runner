import { useState, useEffect, useCallback } from "react";
import * as api from "./api.js";

/* ---------------- Theme (oscuro premium fijo en el Command Center) ---------------- */
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

/* ---------------- Marca / assets ----------------
   Si existen los archivos reales en frontend/public/assets/ se usan;
   si no, cae a un placeholder vectorial premium (nunca se ve roto). */
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

function BrandMark({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect x="2" y="2" width="36" height="36" rx="9" fill="none"
        stroke="var(--accent)" strokeWidth="2.5" />
      <path d="M11 28 L20 12 L29 28" fill="none" stroke="var(--accent)"
        strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <line x1="15" y1="22" x2="25" y2="22" stroke="var(--accent)"
        strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function CorporateLogo() {
  return (
    <div className="cc-corp">
      <AssetImg
        src="/assets/logo-auditconsulting-group.png"
        alt="Audit Consulting Group"
        className="cc-corp-img"
        fallback={
          <>
            <BrandMark size={34} />
            <div className="cc-corp-txt">
              <span>AUDIT</span>
              <span>CONSULTING</span>
              <b>GROUP</b>
            </div>
          </>
        }
      />
    </div>
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
      <div className="login-aside">
        <div className="login-figure">
          <AssetImg
            src="/assets/ai-girl-with-logo.png"
            alt=""
            className="login-figure-img"
            fallback={<div className="figure-ph"><span>AUDIT</span><b>IA</b></div>}
          />
        </div>
      </div>
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <BrandMark size={38} />
          <div>
            <div className="bname">AuditBrain<span> IA</span></div>
            <div className="btag">Enterprise Intelligence OS</div>
          </div>
        </div>
        <div className="login-sub">Acceso restringido · sesión con cuenta</div>
        <label>Email corporativo</label>
        <input type="email" value={email}
          onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
        <label>Contraseña</label>
        <input type="password" value={password}
          onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
        <button className="btn primary block" disabled={busy}>
          {busy ? "Autenticando…" : "Acceder al Command Center"}
        </button>
        {err && <div className="err">{err}</div>}
        <div className="login-foot">JWT · sandbox Tier 0 · API Key no expuesta</div>
      </form>
    </div>
  );
}

/* ---------------- Primitivas ---------------- */
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

/* ---------------- Paneles funcionales reales (lógica intacta) ---------------- */
function Dashboard({ user, health }) {
  const hp = health;
  const isAdmin = user.role === "admin";
  const ok = hp.state === "ok";
  return (
    <>
      <ViewHead code="DSH" title="Centro de Operaciones"
        sub="Estado consolidado de la plataforma AuditBrain IA." />
      {!isAdmin && (
        <div className="notice warn">
          Acceso limitado según rol. El rol <b>user</b> no incluye ejecución
          (Runner) ni administración de cuentas.
        </div>
      )}
      <Panel title="Telemetría del sistema" meta={ok ? "LIVE" : "—"}>
        <div className="metrics">
          <Metric label="Núcleo backend"
            value={ok ? "Operativo" : hp.state === "bad" ? "No disponible" : "Comprobando…"}
            state={ok ? "ok" : hp.state === "bad" ? "bad" : "idle"} />
          <Metric label="PostgreSQL" value={ok ? "Activo" : "Desconocido"} state={ok ? "ok" : "idle"} />
          <Metric label="Versión API" value={hp.data?.version || "—"} state={ok ? "ok" : "idle"} />
          <Metric label="Capa de auth"
            value={hp.data?.auth_enabled ? "JWT + API Key" : "Abierta"} state="ok" />
          <Metric label="Motor de ejecución"
            value={isAdmin ? "Habilitado" : "Restringido"} state={isAdmin ? "ok" : "idle"} />
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
    setErr(""); setOut(null); setBusy(true);
    try { setOut(await api.runPython(script)); }
    catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }
  return (
    <>
      <ViewHead code="RUN" title="Motor de Ejecución Python"
        sub="Ejecución server-side bajo sandbox Tier 0." />
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
    e.preventDefault(); setMsg(""); setErr(""); setBusy(true);
    try {
      const u = await api.createUser(email, password, role);
      setMsg(`Usuario creado: ${u.email} · rol ${u.role}`);
      setEmail(""); setPassword(""); setRole("user");
    } catch (e2) { setErr(e2.message); }
    finally { setBusy(false); }
  }
  return (
    <>
      <ViewHead code="USR" title="Administración de Cuentas"
        sub="Provisión de operadores. Solo administradores." />
      <Panel title="Alta de operador" max={520}>
        <form onSubmit={submit}>
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <label>Contraseña (mín. 8)</label>
          <input type="password" value={password}
            onChange={(e) => setPassword(e.target.value)} minLength={8} required />
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
      <ViewHead code="SEC" title="Postura de Seguridad"
        sub="Modelo de seguridad vigente de AuditBrain IA." />
      <Panel title="Controles activos" max={680}>
        <div className="kv">
          {rows.map(([k, v]) => (
            <div key={k} style={{ display: "contents" }}>
              <span className="k">{k}</span><span className="v">{v}</span>
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

function Documents({ embedded }) {
  const [format, setFormat] = useState("pdf");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  async function submit(e) {
    e.preventDefault(); setErr(""); setRes(null); setBusy(true);
    try {
      const out = await api.generateDocument({ format, title, content });
      if (out && out.status === "error") setErr(out.error || "El servicio documental devolvió un error.");
      else setRes(out);
    } catch (e2) { setErr(e2.message); }
    finally { setBusy(false); }
  }
  const url = res ? api.findDownloadUrl(res) : null;
  return (
    <>
      {!embedded && (
        <ViewHead code="DOC" title="Generación Documental"
          sub="PDF, Word, Excel y PowerPoint vía el servicio documental." />
      )}
      <div className="notice">
        Procesado server-side con tu sesión JWT. Disponible para cualquier operador autenticado.
      </div>
      <Panel title="Nueva generación" max={680}>
        <form onSubmit={submit}>
          <label>Tipo de documento</label>
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            {DOC_FORMATS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <label>Título</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="Informe trimestral" required />
          <label>Contenido principal</label>
          <textarea value={content} onChange={(e) => setContent(e.target.value)}
            placeholder="Texto principal del documento…" style={{ minHeight: 160 }} required />
          <button className="btn primary" disabled={busy}>
            {busy ? "Generando…" : "Generar documento"}
          </button>
          {err && <div className="err">{err}</div>}
        </form>
      </Panel>
      {res && (
        <Panel title="Documento generado" meta="OK" max={680}>
          {url ? (
            <p><a href={url} target="_blank" rel="noopener noreferrer">⇩ Descargar documento</a></p>
          ) : (
            <div className="notice warn">
              Documento generado pero sin URL de descarga directa. Respuesta cruda abajo.
            </div>
          )}
          <pre>{JSON.stringify(res.response ?? res, null, 2)}</pre>
        </Panel>
      )}
    </>
  );
}

/* ---------------- Módulos sectoriales (nodos reales · capa cognitiva en Fase 2) ---------------- */
const MODULES = [
  { id: "ADV", label: "Executive Advisory" },
  { id: "AUD", label: "External Audit" },
  { id: "TAX", label: "Tax Structuring" },
  { id: "LEG", label: "Legal Intelligence" },
  { id: "FIN", label: "CFO Intelligence" },
  { id: "CYB", label: "Cybersecurity & IT Audit" },
  { id: "DATA", label: "Data & BI Intelligence" },
  { id: "AUT", label: "Automation Core" },
  { id: "GOV", label: "Governance Layer" },
  { id: "MKT", label: "Marketing Intelligence" },
  { id: "CRE", label: "Creative Studio" },
];

const AI_LINKS = [
  { name: "ChatGPT", href: "https://chatgpt.com" },
  { name: "Claude", href: "https://claude.ai" },
  { name: "Gemini", href: "https://gemini.google.com" },
];

function CognitiveWorkspace({ user, module, goDocs, goRunner, isAdmin }) {
  const [tab, setTab] = useState("chat");
  const first = (user.email || "Operador").split("@")[0].split(/[._-]/)[0];
  const name = first.charAt(0).toUpperCase() + first.slice(1);
  return (
    <div className="cw">
      <div className="hero">
        <div className="hero-txt">
          <h1>Hola <span>{name}</span>,</h1>
          <h1>bienvenido a <span>AuditBrain</span></h1>
          <p>Plataforma operativa de inteligencia empresarial · módulo {module.id} · {module.label}.</p>
        </div>
        <div className="hero-wave" aria-hidden="true" />
      </div>

      <div className="cw-figure" aria-hidden="true">
        <AssetImg
          src="/assets/ai-girl-with-logo.png"
          alt=""
          className="cw-figure-img"
          fallback={<div className="figure-ph lg"><span>AUDIT</span><b>IA</b></div>}
        />
      </div>

      <Panel
        title="Workspace cognitivo"
        meta={`${module.id} · CAPA COGNITIVA · FASE 2`}
      >
        <div className="cw-tabs">
          {["chat", "análisis", "documentos", "notas"].map((t) => (
            <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        {tab === "documentos" ? (
          <div className="cw-docs">
            <Documents embedded />
          </div>
        ) : (
          <>
            <div className="cw-prompt">
              <div className="cw-prompt-q">¿En qué podemos ayudarte hoy?</div>
              <textarea
                disabled
                placeholder="Orquestación cognitiva multi-agente — disponible en Fase 2"
              />
              <div className="cw-prompt-bar">
                <button className="link" onClick={goDocs}>⌯ Adjuntar / generar documento</button>
                <span className="cw-soon-tag">Fase 2</span>
              </div>
            </div>
            <div className="cw-ext">
              <div className="cw-ext-l">O continúa la conversación en:</div>
              <div className="cw-ext-grid">
                {AI_LINKS.map((a) => (
                  <a key={a.name} className="cw-ext-card" href={a.href}
                    target="_blank" rel="noopener noreferrer">
                    <b>{a.name}</b>
                    <span>Abrir {a.name} →</span>
                  </a>
                ))}
              </div>
            </div>
          </>
        )}
      </Panel>

      <Panel title="Accesos rápidos">
        <div className="qa">
          <button className="qa-item" onClick={goDocs}>
            <b>Subir / generar documento</b><span>PDF · Word · Excel · PPT</span>
          </button>
          <button className="qa-item" onClick={goDocs}>
            <b>Generar reporte</b><span>Informe ejecutivo</span>
          </button>
          {isAdmin ? (
            <button className="qa-item" onClick={goRunner}>
              <b>Ejecutar proceso</b><span>Motor Python · Tier 0</span>
            </button>
          ) : (
            <button className="qa-item off" disabled>
              <b>Ejecutar proceso</b><span>Solo admin</span>
            </button>
          )}
          <button className="qa-item off" disabled>
            <b>Buscar en biblioteca</b><span>Fase 2</span>
          </button>
          <button className="qa-item off" disabled>
            <b>Crear workflow</b><span>Fase 2</span>
          </button>
        </div>
      </Panel>
    </div>
  );
}

/* ---------------- Command Center Shell ---------------- */
export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [section, setSection] = useState("ADV");
  const [navOpen, setNavOpen] = useState(false);
  const [theme, toggleTheme] = useTheme();
  const [hp, setHp] = useState({ state: "idle", data: null });

  const loadMe = useCallback(async () => {
    if (!api.getToken()) { setUser(null); setLoading(false); return; }
    try { setUser(await api.me()); }
    catch { api.clearSession(); setUser(null); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadMe(); }, [loadMe]);

  useEffect(() => {
    if (!user) return;
    let alive = true;
    api.health()
      .then((d) => alive && setHp({ state: "ok", data: d }))
      .catch(() => alive && setHp({ state: "bad", data: null }));
    return () => { alive = false; };
  }, [user]);

  if (loading)
    return <div className="login-wrap"><span className="muted">Inicializando Command Center…</span></div>;
  if (!user) return <Login onLogged={loadMe} />;

  const isAdmin = user.role === "admin";

  const OPS = [
    { id: "dashboard", code: "DSH", label: "Centro de Operaciones" },
    { id: "documents", code: "DOC", label: "Documentos" },
    { id: "runner", code: "RUN", label: "Motor de Ejecución", admin: true },
    { id: "users", code: "USR", label: "Cuentas", admin: true },
    { id: "security", code: "SEC", label: "Seguridad" },
  ].filter((n) => !n.admin || isAdmin);

  const moduleActive = MODULES.find((m) => m.id === section);
  const opActive = OPS.find((o) => o.id === section);
  const crumb = moduleActive
    ? { code: moduleActive.id, label: moduleActive.label }
    : { code: opActive?.code, label: opActive?.label };

  function go(id) { setSection(id); setNavOpen(false); }

  function render() {
    if (moduleActive)
      return (
        <CognitiveWorkspace
          user={user}
          module={moduleActive}
          isAdmin={isAdmin}
          goDocs={() => go("documents")}
          goRunner={() => go("runner")}
        />
      );
    switch (section) {
      case "runner": return isAdmin ? <Runner /> : <Dashboard user={user} health={hp} />;
      case "users": return isAdmin ? <Users /> : <Dashboard user={user} health={hp} />;
      case "security": return <Security user={user} />;
      case "documents": return (
        <><ViewHead code="DOC" title="Generación Documental"
          sub="PDF, Word, Excel y PowerPoint vía el servicio documental." />
        <Documents /></>
      );
      default: return <Dashboard user={user} health={hp} />;
    }
  }

  const ok = hp.state === "ok";

  return (
    <div className="cc">
      {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}

      <div className="cc-brand-cell"><CorporateLogo /></div>

      <aside className={`cc-side${navOpen ? " open" : ""}`}>
        <nav className="cc-nav">
          <div className="cc-group-l">Módulos</div>
          {MODULES.map((m) => (
            <button key={m.id}
              className={`cc-node${section === m.id ? " on" : ""}`}
              onClick={() => go(m.id)}>
              <span className="cc-code">{m.id}</span>
              <span className="cc-label">{m.label}</span>
              <span className="cc-chev">›</span>
            </button>
          ))}
          <div className="cc-group-l" style={{ marginTop: 18 }}>Operación</div>
          {OPS.map((o) => (
            <button key={o.id}
              className={`cc-node${section === o.id ? " on" : ""}`}
              onClick={() => go(o.id)}>
              <span className="cc-code">{o.code}</span>
              <span className="cc-label">{o.label}</span>
              <span className="cc-chev">›</span>
            </button>
          ))}
        </nav>
        <div className="cc-side-foot">
          <div className="cc-group-l">Estado del sistema</div>
          <div className="cc-status">
            <span className={`dot ${ok ? "ok" : hp.state === "bad" ? "bad" : "idle"}`} />
            {ok ? "Óptimo" : hp.state === "bad" ? "Backend no disponible" : "Comprobando…"}
          </div>
          <div className="cc-status-sub">
            {ok ? "Servicios operativos" : "—"}
          </div>
        </div>
      </aside>

      <header className="cc-head">
        <button className="cc-burger" onClick={() => setNavOpen((o) => !o)} aria-label="Menú">≡</button>
        <div className="cc-head-title">
          <b>COMMAND CENTER</b>
          <span>Centro de Inteligencia Empresarial</span>
        </div>
        <div className="cc-ws">
          <span className="cc-ws-l">Workspace</span>
          <span className="cc-ws-v">{crumb.code} · {crumb.label}</span>
        </div>
        <div className="cc-search" aria-hidden="true">
          <span>Buscar en AuditBrain…</span><kbd>⌘K</kbd>
        </div>
        <div className="cc-head-r">
          <button className="cc-icon" onClick={toggleTheme} title="Tema">
            {theme === "dark" ? "◑" : "◐"}
          </button>
          <div className="cc-user">
            <span className="cc-user-n">{user.email}</span>
            <span className={`cc-role ${user.role}`}>{user.role}</span>
          </div>
          <button className="btn ghost"
            onClick={() => { api.clearSession(); setUser(null); }}>
            Salir
          </button>
        </div>
      </header>

      <main className="cc-main">
        <div className="cc-work">{render()}</div>
        <aside className="cc-ctx">
          <div className="cc-ctx-h">Contexto activo</div>
          <div className="cc-ctx-card">
            <div className="cc-ctx-k">Operador</div>
            <div className="cc-ctx-v">{user.email}</div>
            <div className="cc-ctx-k">Privilegio</div>
            <div className="cc-ctx-v"><span className={`cc-role ${user.role}`}>{user.role}</span></div>
            <div className="cc-ctx-k">Nodo activo</div>
            <div className="cc-ctx-v">{crumb.code} · {crumb.label}</div>
            <div className="cc-ctx-k">Cliente</div>
            <div className="cc-ctx-v dim">Sin cliente asignado</div>
            <div className="cc-ctx-k">Proyecto</div>
            <div className="cc-ctx-v dim">Sin proyecto activo</div>
          </div>
          <div className="cc-ctx-card">
            <div className="cc-ctx-h2">Tips &amp; acciones</div>
            <ul className="cc-tips">
              <li><b>Sube documentos</b><span>Genera PDF/Word/Excel/PPT server-side.</span></li>
              <li><b>Ejecuta procesos</b><span>Motor Python sandbox (rol admin).</span></li>
              <li><b>Revisa seguridad</b><span>Postura JWT y controles activos.</span></li>
            </ul>
          </div>
          <div className="cc-ctx-card">
            <div className="cc-ctx-h2">Atenciones prioritarias</div>
            <div className="cc-ok-row">
              <span className="dot ok" />
              <div>
                <b>{ok ? "Sin elementos críticos" : "Verificar backend"}</b>
                <span>{ok ? "Todo en orden" : "Salud del API no confirmada"}</span>
              </div>
            </div>
          </div>
        </aside>
      </main>

      <footer className="cc-foot">
        <span><b>AuditBrain IA</b> · v{hp.data?.version || "—"}</span>
        <span className="cc-foot-r">
          <span><span className={`dot ${ok ? "ok" : "idle"}`} /> {ok ? "Operativo" : "—"}</span>
          <span>Auth JWT</span>
          <span>Sandbox Tier 0</span>
          <span className="mono">{new Date().toISOString().slice(0, 16).replace("T", " ")}</span>
        </span>
      </footer>
    </div>
  );
}
