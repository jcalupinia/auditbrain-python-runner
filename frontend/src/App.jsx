import { useState, useEffect, useCallback } from "react";
import * as api from "./api.js";
import ToolCatalog from "./aud/ToolCatalog.jsx";
import TaxCatalog from "./tax/TaxCatalog.jsx";
import FinCatalog from "./fin/FinCatalog.jsx";

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
            src="/assets/ai-girl-figure.png"
            alt=""
            className="login-figure-img"
            fallback={<div className="figure-ph"><span>AUDIT</span><b>IA</b></div>}
          />
        </div>
      </div>
      <AssetImg
        src="/assets/logo-auditconsulting-group.png"
        alt="Audit Consulting Group"
        className="login-logo"
        fallback={null}
      />
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand login-brand--logo">
          <img className="login-audit-ia" src="/assets/logo-audit-ia.png"
            alt="AUDIT-IA · Artificial Intelligence" />
          <div className="btag">Enterprise Intelligence OS</div>
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

/* ---------------- Panel de Tokens IA (sidebar derecho) ----------------
   Muestra el proveedor actual y enlaces directos a las páginas de
   facturación de cada proveedor LLM soportado. */
const LLM_PROVIDER_INFO = {
  anthropic: {
    label: "Anthropic · Claude",
    free: false,
    rechargeUrl: "https://console.anthropic.com/settings/billing",
    note: "De pago · top-up desde $5",
  },
  openai: {
    label: "OpenAI · GPT",
    free: false,
    rechargeUrl: "https://platform.openai.com/account/billing",
    note: "De pago · top-up desde $5",
  },
  gemini: {
    label: "Google · Gemini",
    free: true,
    rechargeUrl: "https://aistudio.google.com/apikey",
    note: "Gratis · ~1M tokens/día",
  },
  groq: {
    label: "Groq · Llama 3.3",
    free: true,
    rechargeUrl: "https://console.groq.com/keys",
    note: "Gratis · ~14k req/día",
  },
  openrouter: {
    label: "OpenRouter (multi)",
    free: false,
    rechargeUrl: "https://openrouter.ai/credits",
    note: "Hub · todos los modelos · top-up desde $5",
  },
};

function TokensPanel({ llm }) {
  const primary = llm?.primary;
  const configured = llm?.configured || [];
  const primaryInfo = primary ? LLM_PROVIDER_INFO[primary] : null;

  return (
    <div className="cc-ctx-card">
      <div className="cc-ctx-h2">💳 Tokens IA</div>
      {primaryInfo ? (
        <ul className="cc-tips">
          <li>
            <b>Proveedor activo</b>
            <span>
              {primaryInfo.label}
              {primaryInfo.free ? " · gratis" : " · de pago"}
            </span>
          </li>
          <li>
            <b>Configurados</b>
            <span>{configured.join(", ") || "ninguno"}</span>
          </li>
        </ul>
      ) : (
        <ul className="cc-tips">
          <li>
            <b>Sin proveedor IA</b>
            <span>Configura una API key en Render.</span>
          </li>
        </ul>
      )}
      {primaryInfo && (
        <a
          href={primaryInfo.rechargeUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="btn primary block"
          style={{ marginTop: 10, textAlign: "center", textDecoration: "none" }}
        >
          {primaryInfo.free ? "Gestionar key" : "💳 Recargar tokens"}
        </a>
      )}
      <div
        style={{
          marginTop: 12,
          paddingTop: 10,
          borderTop: "1px solid var(--border, #334155)",
          fontSize: 12,
          color: "var(--muted, #94a3b8)",
        }}
      >
        <div style={{ marginBottom: 6 }}>Otros proveedores:</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {Object.entries(LLM_PROVIDER_INFO)
            .filter(([key]) => key !== primary)
            .map(([key, info]) => (
              <a
                key={key}
                href={info.rechargeUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="link"
                style={{ fontSize: 12 }}
                title={info.note}
              >
                {info.label} {info.free ? "(gratis)" : "↗"}
              </a>
            ))}
        </div>
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
        sub="Estado consolidado de la plataforma AUDIT-IA." />
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

  // Listas de gestión
  const [operators, setOperators] = useState([]);
  const [clients, setClients] = useState([]);
  const [selClient, setSelClient] = useState("");
  const [portalUsers, setPortalUsers] = useState([]);
  const [newPuEmail, setNewPuEmail] = useState("");
  const [reveal, setReveal] = useState(null); // { who, temp }
  const [listErr, setListErr] = useState("");

  // Carga masiva de clientes (licencias) + lista global de cuentas de portal
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkRes, setBulkRes] = useState(null);
  const [allPortal, setAllPortal] = useState([]);
  const [puFilter, setPuFilter] = useState("");

  async function loadOperators() {
    try { setOperators(await api.listOperators()); } catch (e) { setListErr(e.message); }
  }
  async function loadClients() {
    try { setClients(await api.listClients()); } catch (e) { setListErr(e.message); }
  }
  async function loadPortalUsers(cid) {
    if (!cid) { setPortalUsers([]); return; }
    try { setPortalUsers(await api.listPortalUsers(cid)); } catch (e) { setListErr(e.message); }
  }
  async function loadAllPortal() {
    try { setAllPortal(await api.listAllPortalUsers()); } catch (e) { setListErr(e.message); }
  }
  useEffect(() => { loadOperators(); loadClients(); loadAllPortal(); }, []);
  useEffect(() => { loadPortalUsers(selClient); }, [selClient]);

  async function doBulkUpload(e) {
    e.preventDefault();
    const f = e.target.elements.bulkfile.files[0];
    if (!f) { setListErr("Selecciona el archivo Excel primero."); return; }
    setBulkBusy(true); setBulkRes(null); setListErr("");
    try {
      const res = await api.bulkUploadPortalUsers(f);
      setBulkRes(res);
      loadAllPortal();
    } catch (e2) { setListErr(e2.message); }
    finally { setBulkBusy(false); }
  }
  function downloadCredsCsv(creados) {
    const headers = ["Email", "Clave temporal", "Empresas", "RUC"];
    const esc = (v) => { const s = String(v ?? ""); return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const lines = [headers.join(",")];
    for (const c of creados) {
      lines.push([c.email, c.temp_password, (c.empresas || []).join(" / "), c.ruc].map(esc).join(","));
    }
    const blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "credenciales_clientes.csv";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  }
  async function resetGlobal(u) {
    if (!window.confirm(`¿Resetear la clave de ${u.email}?`)) return;
    setReveal(null); setListErr("");
    try { const r = await api.resetPortalUserById(u.id); setReveal({ who: u.email, temp: r.temp_password }); }
    catch (e) { setListErr(e.message); }
  }
  async function toggleGlobal(u) {
    const next = !u.is_active;
    if (!window.confirm(`¿${next ? "Habilitar" : "Deshabilitar"} a ${u.email}?`)) return;
    setListErr("");
    try { await api.setPortalUserActiveById(u.id, next); loadAllPortal(); }
    catch (e) { setListErr(e.message); }
  }
  async function deleteGlobal(u) {
    if (!window.confirm(`¿BORRAR definitivamente a ${u.email}?\nEsta acción es irreversible.`)) return;
    if (!window.confirm(`Confirma de nuevo: se eliminará ${u.email}.`)) return;
    setListErr("");
    try { await api.deletePortalUserById(u.id); loadAllPortal(); }
    catch (e) { setListErr(e.message); }
  }

  async function submit(e) {
    e.preventDefault(); setMsg(""); setErr(""); setBusy(true);
    try {
      const u = await api.createUser(email, password, role);
      setMsg(`Usuario creado: ${u.email} · rol ${u.role}`);
      setEmail(""); setPassword(""); setRole("user");
      loadOperators();
    } catch (e2) { setErr(e2.message); }
    finally { setBusy(false); }
  }

  async function resetOperator(u) {
    if (!window.confirm(`¿Resetear la clave del operador ${u.email}?`)) return;
    setReveal(null); setListErr("");
    try {
      const r = await api.resetOperatorPassword(u.id);
      setReveal({ who: u.email, temp: r.temp_password });
    } catch (e) { setListErr(e.message); }
  }
  async function resetPortal(u) {
    if (!window.confirm(`¿Resetear la clave del cliente ${u.email}?`)) return;
    setReveal(null); setListErr("");
    try {
      const r = await api.resetPortalUserPassword(selClient, u.id);
      setReveal({ who: u.email, temp: r.temp_password });
    } catch (e) { setListErr(e.message); }
  }
  async function addPortalUser(e) {
    e.preventDefault(); setReveal(null); setListErr("");
    try {
      const r = await api.createPortalUser(selClient, newPuEmail);
      setReveal({ who: r.email, temp: r.temp_password });
      setNewPuEmail(""); loadPortalUsers(selClient);
    } catch (e2) { setListErr(e2.message); }
  }

  async function delOperator(u) {
    if (!window.confirm(`¿BORRAR definitivamente al operador ${u.email}?\nEsta acción es irreversible.`)) return;
    if (!window.confirm(`Confirma de nuevo: se eliminará ${u.email} y sus datos asociados.`)) return;
    setReveal(null); setListErr("");
    try { await api.deleteOperator(u.id); loadOperators(); }
    catch (e) { setListErr(e.message); }
  }
  async function delPortal(u) {
    if (!window.confirm(`¿BORRAR definitivamente al usuario ${u.email}?\nEsta acción es irreversible.`)) return;
    if (!window.confirm(`Confirma de nuevo: se eliminará ${u.email} y sus datos asociados.`)) return;
    setReveal(null); setListErr("");
    try { await api.deletePortalUser(selClient, u.id); loadPortalUsers(selClient); }
    catch (e) { setListErr(e.message); }
  }
  async function toggleOperator(u) {
    const next = !u.is_active;
    if (!window.confirm(`¿${next ? "Habilitar" : "Deshabilitar"} al operador ${u.email}?`)) return;
    setListErr("");
    try { await api.setOperatorActive(u.id, next); loadOperators(); }
    catch (e) { setListErr(e.message); }
  }
  async function togglePortal(u) {
    const next = !u.is_active;
    if (!window.confirm(`¿${next ? "Habilitar" : "Deshabilitar"} al usuario ${u.email}?`)) return;
    setListErr("");
    try { await api.setPortalUserActive(selClient, u.id, next); loadPortalUsers(selClient); }
    catch (e) { setListErr(e.message); }
  }

  const clientLabel = (c) => c.name ?? c.razon_social ?? c.nombre ?? `Cliente #${c.id}`;

  return (
    <>
      <ViewHead code="USR" title="Administración de Cuentas"
        sub="Operadores y usuarios de portal · alta y reseteo de claves. Solo administradores." />

      {reveal && (
        <Panel title="🔑 Clave temporal generada" meta="copiar" max={680}>
          <p className="muted">
            Clave temporal para <b>{reveal.who}</b>. Cópiala y compártela por canal
            seguro — <b>no se vuelve a mostrar</b>.
          </p>
          <pre style={{ fontSize: 16, userSelect: "all" }}>{reveal.temp}</pre>
          <button className="btn" onClick={() => setReveal(null)}>Entendido</button>
        </Panel>
      )}
      {listErr && <div className="err" style={{ marginBottom: 12 }}>{listErr}</div>}

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

      {/* Operadores existentes + reset */}
      <Panel title={`Operadores (${operators.length})`} max={680}>
        {operators.length === 0 ? (
          <p className="muted">Sin operadores que mostrar.</p>
        ) : (
          <div className="kv">
            {operators.map((o) => (
              <div key={o.id} style={{ display: "flex", alignItems: "center",
                justifyContent: "space-between", gap: 12, padding: "8px 0",
                borderBottom: "1px solid var(--line)" }}>
                <span>
                  {o.email} <span className="muted">· {o.role}{o.is_active ? "" : " · inactivo"}</span>
                </span>
                <span style={{ display: "flex", gap: 8 }}>
                  <button className="btn" onClick={() => resetOperator(o)}>Resetear clave</button>
                  <button className="btn" onClick={() => toggleOperator(o)}>
                    {o.is_active ? "Deshabilitar" : "Habilitar"}
                  </button>
                  <button className="btn" style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
                    onClick={() => delOperator(o)}>Borrar</button>
                </span>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {/* Carga masiva de clientes (licencias) */}
      <Panel title="📋 Carga masiva de clientes (licencias)" max={680}>
        <p className="muted">
          Sube el Excel con columnas <b>CLIENTE · RUC · Email Contador</b>. Se
          crea <b>una cuenta por correo</b> (si un contador lleva varios
          clientes, una sola cuenta). Los correos inválidos se omiten y se
          reportan; los ya existentes no se duplican.
        </p>
        <form onSubmit={doBulkUpload}>
          <input type="file" name="bulkfile" accept=".xlsx,.xls" />
          <button className="btn primary" disabled={bulkBusy} style={{ marginTop: 10 }}>
            {bulkBusy ? "Procesando…" : "Crear cuentas en bloque"}
          </button>
        </form>
        {bulkRes && (
          <div style={{ marginTop: 14 }}>
            <div className="ok-msg">
              Creadas: <b>{bulkRes.resumen.creados}</b> · Omitidas:{" "}
              <b>{bulkRes.resumen.omitidos}</b> · Ya existían:{" "}
              <b>{bulkRes.resumen.existentes}</b>
            </div>
            {bulkRes.creados.length > 0 && (
              <>
                <button className="btn" style={{ margin: "10px 0" }}
                  onClick={() => downloadCredsCsv(bulkRes.creados)}>
                  ⇩ Descargar credenciales (CSV)
                </button>
                <div className="kv">
                  {bulkRes.creados.map((c) => (
                    <div key={c.email} style={{ display: "flex", justifyContent: "space-between",
                      gap: 12, padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
                      <span>{c.email}<span className="muted"> · {(c.empresas || []).join(", ")}</span></span>
                      <code style={{ userSelect: "all" }}>{c.temp_password}</code>
                    </div>
                  ))}
                </div>
                <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                  Comparte cada clave con su cliente por canal seguro — no se vuelven a mostrar.
                </p>
              </>
            )}
            {bulkRes.omitidos.length > 0 && (
              <details style={{ marginTop: 10 }}>
                <summary className="muted">{bulkRes.omitidos.length} omitidos (sin correo válido)</summary>
                {bulkRes.omitidos.map((o, i) => (
                  <div key={i} className="muted" style={{ fontSize: 13 }}>{o.cliente} — {o.motivo}</div>
                ))}
              </details>
            )}
          </div>
        )}
      </Panel>

      {/* Todas las cuentas de cliente — gestión global */}
      <Panel title={`Todas las cuentas de cliente (${allPortal.length})`} max={680}>
        <input placeholder="Filtrar por correo o empresa…" value={puFilter}
          onChange={(e) => setPuFilter(e.target.value)} style={{ marginBottom: 10 }} />
        {allPortal.length === 0 ? (
          <p className="muted">Aún no hay cuentas de cliente.</p>
        ) : (
          <div className="kv">
            {allPortal
              .filter((u) => {
                const t = puFilter.trim().toLowerCase();
                return !t || `${u.email} ${u.cliente}`.toLowerCase().includes(t);
              })
              .map((u) => (
                <div key={u.id} style={{ display: "flex", alignItems: "center",
                  justifyContent: "space-between", gap: 12, padding: "8px 0",
                  borderBottom: "1px solid var(--line)" }}>
                  <span>{u.email}
                    <span className="muted"> · {u.cliente}{u.is_active ? "" : " · inactivo"}</span>
                  </span>
                  <span style={{ display: "flex", gap: 8 }}>
                    <button className="btn" onClick={() => resetGlobal(u)}>Resetear</button>
                    <button className="btn" onClick={() => toggleGlobal(u)}>
                      {u.is_active ? "Deshabilitar" : "Habilitar"}
                    </button>
                    <button className="btn" style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
                      onClick={() => deleteGlobal(u)}>Borrar</button>
                  </span>
                </div>
              ))}
          </div>
        )}
      </Panel>

      {/* Clientes del portal + reset */}
      <Panel title="Usuarios de portal (clientes) · por cliente" max={680}>
        <label>Cliente</label>
        <select value={selClient} onChange={(e) => setSelClient(e.target.value)}>
          <option value="">— Selecciona un cliente —</option>
          {clients.map((c) => (
            <option key={c.id} value={c.id}>{clientLabel(c)}</option>
          ))}
        </select>

        {selClient && (
          <>
            <div style={{ marginTop: 16 }}>
              {portalUsers.length === 0 ? (
                <p className="muted">Este cliente no tiene usuarios de portal.</p>
              ) : (
                portalUsers.map((u) => (
                  <div key={u.id} style={{ display: "flex", alignItems: "center",
                    justifyContent: "space-between", gap: 12, padding: "8px 0",
                    borderBottom: "1px solid var(--line)" }}>
                    <span>
                      {u.email}
                      <span className="muted">{u.is_active ? "" : " · inactivo"}
                        {u.password_reset_required ? " · clave temporal" : ""}</span>
                    </span>
                    <span style={{ display: "flex", gap: 8 }}>
                      <button className="btn" onClick={() => resetPortal(u)}>Resetear clave</button>
                      <button className="btn" onClick={() => togglePortal(u)}>
                        {u.is_active ? "Deshabilitar" : "Habilitar"}
                      </button>
                      <button className="btn" style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
                        onClick={() => delPortal(u)}>Borrar</button>
                    </span>
                  </div>
                ))
              )}
            </div>

            <form onSubmit={addPortalUser} style={{ marginTop: 16 }}>
              <label>Crear usuario de portal para este cliente</label>
              <input type="email" value={newPuEmail}
                onChange={(e) => setNewPuEmail(e.target.value)}
                placeholder="cliente@empresa.com" required />
              <button className="btn primary" style={{ marginTop: 8 }}>Crear usuario de portal</button>
            </form>
          </>
        )}
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
        sub="Modelo de seguridad vigente de AUDIT-IA." />
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

/* ---------------- Mi Perfil (admin) ----------------
   Muestra la identidad del operador y la clave de protección de los Excel
   SRI del ICT. La clave solo la sirve el backend a usuarios con rol admin
   (GET /auth/sri-protection-key), y esta vista solo aparece en el menú para
   admins. Se muestra oculta por defecto con un botón "Mostrar". */
function Profile({ user }) {
  const [creds, setCreds] = useState(null);
  const [err, setErr] = useState("");
  const [reveal, setReveal] = useState(false);

  useEffect(() => {
    api.getSriProtectionKey().then(setCreds).catch((e) => setErr(e.message));
  }, []);

  return (
    <>
      <ViewHead code="PRF" title="Mi Perfil"
        sub="Cuenta del operador y credenciales de la firma." />
      <Panel title="Identidad" max={680}>
        <div className="kv">
          <span className="k">Operador</span><span className="v">{user.email}</span>
          <span className="k">Rol</span><span className="v">{user.role}</span>
          <span className="k">Endpoint API</span>
          <span className="v mono">{api.getApiBase()}</span>
        </div>
      </Panel>
      <Panel title="🔒 Clave de protección · Excel SRI (ICT)" max={680}>
        <p className="muted">
          Contraseña que bloquea la estructura de los Excel «para el SRI» del
          ICT: impide que el cliente des-oculte las hojas DATOS/internas. Solo
          AuditConsulting debe conocerla. Para des-proteger un archivo en
          Excel: <b>Revisar → Proteger libro</b> → escribir esta clave.
        </p>
        {err && <div className="err">{err}</div>}
        {creds ? (
          <>
            {reveal ? (
              <pre style={{ fontSize: 18, userSelect: "all" }}>{creds.password}</pre>
            ) : (
              <pre style={{ fontSize: 18, letterSpacing: 2 }}>••••••••••••</pre>
            )}
            <button className="btn" onClick={() => setReveal((r) => !r)}>
              {reveal ? "Ocultar clave" : "Mostrar clave"}
            </button>
          </>
        ) : (
          !err && <p className="muted">Cargando…</p>
        )}
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
  { name: "ChatGPT", href: "https://chatgpt.com", logo: "/assets/ai/chatgpt.svg" },
  { name: "Claude", href: "https://claude.ai", logo: "/assets/ai/claude.svg" },
  { name: "Gemini", href: "https://gemini.google.com", logo: "/assets/ai/gemini.svg" },
];

function CognitiveWorkspace({ user, module, ctx, goDocs, goRunner, isAdmin }) {
  const [tab, setTab] = useState("chat");
  const [chatText, setChatText] = useState("");
  const [chatNotice, setChatNotice] = useState("");
  const [conv, setConv] = useState(null);          // conversación activa
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const first = (user.email || "Operador").split("@")[0].split(/[._-]/)[0];
  const name = first.charAt(0).toUpperCase() + first.slice(1);

  // Reset chat al cambiar de módulo (cada módulo arranca su conversación).
  useEffect(() => {
    setConv(null);
    setMessages([]);
    setChatNotice("");
    setChatText("");
  }, [module.id]);

  async function submitChat(e) {
    e.preventDefault();
    const content = chatText.trim();
    if (!content || sending) return;
    setSending(true);
    setChatNotice("");
    try {
      let activeConv = conv;
      if (!activeConv) {
        activeConv = await api.createConversation({
          project_id: ctx?.active_project?.id ?? null,
          module_code: module.id,
        });
        setConv(activeConv);
      }
      const turn = await api.sendChatMessage(activeConv.id, content);
      setMessages((prev) => [
        ...prev,
        turn.user_message,
        ...(turn.assistant_message ? [turn.assistant_message] : []),
      ]);
      setChatText("");
      if (turn.provider_error) setChatNotice(turn.provider_error);
    } catch (err) {
      setChatNotice(err.message || "Error enviando el mensaje.");
    } finally {
      setSending(false);
    }
  }

  function newConversation() {
    setConv(null);
    setMessages([]);
    setChatNotice("");
    setChatText("");
  }

  return (
    <div className="cw">
      <div className="hero">
        <div className="hero-txt">
          <h1>Hola <span>{name}</span>,</h1>
          <h1>bienvenido a <span>AUDIT-IA</span></h1>
          <p>Plataforma operativa de inteligencia empresarial · módulo {module.id} · {module.label}.</p>
        </div>
        <div className="hero-wave" aria-hidden="true" />
      </div>

      <Panel
        title="Workspace cognitivo"
        meta={`${module.id} · ${ctx?.active_project?.name || "sin proyecto"}`}
      >
        <div className="cw-tabs">
          {["chat", "análisis", "documentos", "notas"].map((t) => (
            <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        {tab === "análisis" && module.id === "AUD" ? (
          <div className="cw-tool">
            <ToolCatalog projectId={ctx?.active_project?.id} />
          </div>
        ) : tab === "análisis" && module.id === "TAX" ? (
          <div className="cw-tool">
            <TaxCatalog projectId={ctx?.active_project?.id} />
          </div>
        ) : tab === "análisis" && module.id === "FIN" ? (
          <div className="cw-tool">
            <FinCatalog projectId={ctx?.active_project?.id} />
          </div>
        ) : tab === "documentos" ? (
          <div className="cw-docs">
            <Documents embedded />
          </div>
        ) : (
          <div className="cw-stage">
            <div className="cw-stage-girl" aria-hidden="true">
              <AssetImg
                src="/assets/ai-girl-holding.png"
                alt=""
                className="cw-stage-girl-img"
                fallback={<div className="figure-ph lg"><span>AUDIT</span><b>IA</b></div>}
              />
            </div>
            <div className="cw-stage-content">
              {messages.length > 0 && (
                <div className="cw-thread">
                  {messages.map((m) => (
                    <div key={m.id} className={`cw-msg ${m.role}`}>
                      <div className="cw-msg-role">{m.role === "user" ? name : "AUDIT-IA"}</div>
                      <div className="cw-msg-content">{m.content}</div>
                    </div>
                  ))}
                  {sending && (
                    <div className="cw-msg assistant pending">
                      <div className="cw-msg-role">AUDIT-IA</div>
                      <div className="cw-msg-content muted">Pensando…</div>
                    </div>
                  )}
                </div>
              )}
              <form className="cw-prompt" onSubmit={submitChat}>
                <div className="cw-prompt-q">
                  {messages.length === 0 ? "¿En qué podemos ayudarte hoy?" : "Continúa la conversación…"}
                </div>
                <textarea
                  value={chatText}
                  onChange={(e) => { setChatText(e.target.value); }}
                  placeholder={
                    tab === "chat"
                      ? "Escribe tu consulta…"
                      : `Modo ${tab} — todavía sin capa especializada (Fase 2 avanzada).`
                  }
                />
                <div className="cw-prompt-bar">
                  <button type="button" className="link" onClick={goDocs}>
                    ⌯ Adjuntar / generar documento
                  </button>
                  <div className="cw-prompt-actions">
                    {messages.length > 0 && (
                      <button type="button" className="link" onClick={newConversation}>
                        Nueva conversación
                      </button>
                    )}
                    <button
                      type="submit"
                      className="btn primary sm"
                      disabled={!chatText.trim() || sending}
                    >
                      {sending ? "Enviando…" : "Enviar"}
                    </button>
                  </div>
                </div>
                {chatNotice && (
                  <div className="notice warn cw-notice">
                    {chatNotice}
                    {/(quota|429|exceeded|billing|credit|saldo)/i.test(chatNotice) && (
                      <div style={{ marginTop: 8 }}>
                        <a
                          href="https://console.anthropic.com/settings/billing"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn primary sm"
                          style={{ textDecoration: "none" }}
                        >
                          💳 Recargar tokens ahora
                        </a>
                      </div>
                    )}
                  </div>
                )}
              </form>
              <div className="cw-ext">
                <div className="cw-ext-l">O continúa la conversación en:</div>
                <div className="cw-ext-grid">
                  {AI_LINKS.map((a) => (
                    <a key={a.name} className="cw-ext-card" href={a.href}
                      target="_blank" rel="noopener noreferrer">
                      <img className="cw-ext-logo" src={a.logo} alt="" aria-hidden="true" />
                      <b>{a.name}</b>
                      <span>Abrir {a.name} →</span>
                    </a>
                  ))}
                </div>
              </div>
            </div>
          </div>
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

/* ---------------- Workspaces (admin) — Fase 2 · M1 ---------------- */
function Workspaces({ onContextChanged }) {
  const [clients, setClients] = useState([]);
  const [projects, setProjects] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [cName, setCName] = useState("");
  const [cTax, setCTax] = useState("");
  const [cSector, setCSector] = useState("");
  const [pClient, setPClient] = useState("");
  const [pName, setPName] = useState("");
  const [pModule, setPModule] = useState("ADV");
  const [pPeriod, setPPeriod] = useState("");

  const reload = useCallback(async () => {
    try {
      setClients(await api.listClients());
      setProjects(await api.listProjects());
    } catch (e) { setErr(e.message); }
  }, []);
  useEffect(() => { reload(); }, [reload]);

  async function submitClient(e) {
    e.preventDefault(); setErr(""); setMsg(""); setBusy(true);
    try {
      const c = await api.createClient({
        name: cName, tax_id: cTax || null, sector: cSector || null,
      });
      setMsg(`Cliente creado: ${c.name}`);
      setCName(""); setCTax(""); setCSector("");
      await reload();
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }
  async function submitProject(e) {
    e.preventDefault(); setErr(""); setMsg(""); setBusy(true);
    try {
      const p = await api.createProject({
        client_id: Number(pClient),
        name: pName,
        module_code: pModule || null,
        period_label: pPeriod || null,
      });
      setMsg(`Proyecto creado: ${p.name}`);
      setPName(""); setPPeriod("");
      await reload();
      onContextChanged && onContextChanged();
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }

  return (
    <>
      <ViewHead code="WKS" title="Workspaces"
        sub="Gestión de clientes y proyectos de la organización." />
      <Panel title="Clientes" meta={`${clients.length} registro(s)`}>
        <form onSubmit={submitClient} className="row-form">
          <input placeholder="Nombre del cliente" value={cName}
            onChange={(e) => setCName(e.target.value)} required />
          <input placeholder="ID fiscal (opcional)" value={cTax}
            onChange={(e) => setCTax(e.target.value)} />
          <input placeholder="Sector (opcional)" value={cSector}
            onChange={(e) => setCSector(e.target.value)} />
          <button className="btn primary" disabled={busy}>Añadir cliente</button>
        </form>
        {clients.length > 0 && (
          <div className="table">
            <div className="tr th"><span>Cliente</span><span>ID fiscal</span><span>Sector</span></div>
            {clients.map((c) => (
              <div className="tr" key={c.id}>
                <span>{c.name}</span>
                <span className="muted">{c.tax_id || "—"}</span>
                <span className="muted">{c.sector || "—"}</span>
              </div>
            ))}
          </div>
        )}
      </Panel>
      <Panel title="Proyectos" meta={`${projects.length} registro(s)`}>
        <form onSubmit={submitProject} className="row-form">
          <select value={pClient} onChange={(e) => setPClient(e.target.value)} required>
            <option value="">— cliente —</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input placeholder="Nombre del proyecto" value={pName}
            onChange={(e) => setPName(e.target.value)} required />
          <select value={pModule} onChange={(e) => setPModule(e.target.value)}>
            {MODULES.map((m) => <option key={m.id} value={m.id}>{m.id} · {m.label}</option>)}
          </select>
          <input placeholder="Período (ej. Q1 2026)" value={pPeriod}
            onChange={(e) => setPPeriod(e.target.value)} />
          <button className="btn primary" disabled={busy || !clients.length}>
            Añadir proyecto
          </button>
        </form>
        {projects.length > 0 && (
          <div className="table">
            <div className="tr th">
              <span>Proyecto</span><span>Cliente</span>
              <span>Módulo</span><span>Período</span>
            </div>
            {projects.map((p) => {
              const c = clients.find((x) => x.id === p.client_id);
              return (
                <div className="tr" key={p.id}>
                  <span>{p.name}</span>
                  <span className="muted">{c?.name || "—"}</span>
                  <span className="muted">{p.module_code || "—"}</span>
                  <span className="muted">{p.period_label || "—"}</span>
                </div>
              );
            })}
          </div>
        )}
        {msg && <div className="ok-msg">{msg}</div>}
        {err && <div className="err">{err}</div>}
      </Panel>
    </>
  );
}

/* ---------------- Inscripciones a charlas (admin) ---------------- */
const CHARLA_SLUG = "charla-anexos-2026-06";
const INS_COLS = {
  gridTemplateColumns: "1.4fr 1.7fr 1fr 1.1fr 1.4fr 1fr 0.7fr",
};

function _insFecha(r) {
  return (r.created_at || "").slice(0, 16).replace("T", " ");
}

// Exporta las filas a CSV (UTF-8 con BOM para que Excel lea los acentos).
function descargarInscritosCsv(rows) {
  const headers = [
    "Nombre", "Email", "Celular", "Cedula/RUC", "Empresa",
    "Fecha", "Email enviado", "Aviso enviado",
  ];
  const esc = (v) => {
    const s = String(v ?? "");
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.join(",")];
  for (const r of rows) {
    lines.push(
      [
        r.nombre, r.email, r.telefono_e164, r.documento, r.empresa,
        _insFecha(r),
        r.email_enviado ? "si" : "no",
        r.aviso_interno_enviado ? "si" : "no",
      ].map(esc).join(",")
    );
  }
  const blob = new Blob(["﻿" + lines.join("\r\n")], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "inscritos_charla_anexos.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

function Inscripciones() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");

  const reload = useCallback(async () => {
    setBusy(true);
    setErr("");
    try {
      setRows(await api.listEventRegistrations(CHARLA_SLUG));
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }, []);
  useEffect(() => {
    reload();
  }, [reload]);

  const term = q.trim().toLowerCase();
  const filtered = term
    ? rows.filter((r) =>
        `${r.nombre} ${r.email} ${r.empresa} ${r.documento}`
          .toLowerCase()
          .includes(term)
      )
    : rows;

  const meta = term
    ? `${filtered.length} de ${rows.length}`
    : `${rows.length} registro(s)`;

  return (
    <>
      <ViewHead code="INS" title="Inscripciones a charlas"
        sub="Inscritos a la charla de Anexos Tributarios." />
      <Panel title="Inscritos" meta={meta}>
        <div className="row-form" style={{ marginBottom: 12 }}>
          <input
            placeholder="Buscar por nombre, email, empresa o RUC…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <button className="btn ghost" onClick={reload} disabled={busy}>
            {busy ? "Cargando…" : "Actualizar"}
          </button>
          <button
            className="btn primary"
            onClick={() => descargarInscritosCsv(filtered)}
            disabled={busy || filtered.length === 0}
            title="Descargar la lista (se abre en Excel)"
          >
            ⇩ Descargar Excel/CSV
          </button>
        </div>
        {err && <div className="err">{err}</div>}
        {filtered.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <div className="table" style={{ minWidth: 920 }}>
              <div className="tr th" style={INS_COLS}>
                <span>Nombre</span>
                <span>Email</span>
                <span>Celular</span>
                <span>Cédula/RUC</span>
                <span>Empresa</span>
                <span>Fecha</span>
                <span>Envíos</span>
              </div>
              {filtered.map((r) => (
                <div className="tr" key={r.id} style={INS_COLS}>
                  <span>{r.nombre}</span>
                  <span className="muted">{r.email}</span>
                  <span className="muted">{r.telefono_e164}</span>
                  <span className="muted">{r.documento}</span>
                  <span className="muted">{r.empresa}</span>
                  <span className="muted">{_insFecha(r)}</span>
                  <span className="muted">
                    {r.email_enviado ? "✉️" : "—"}
                    {r.aviso_interno_enviado ? " 🔔" : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          !busy && (
            <div className="notice">
              {rows.length === 0
                ? "Aún no hay inscritos."
                : "Sin resultados para la búsqueda."}
            </div>
          )
        )}
      </Panel>
    </>
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
  const [headerSearch, setHeaderSearch] = useState("");
  const [ctx, setCtx] = useState(null);
  const [wsOpen, setWsOpen] = useState(false);

  const loadMe = useCallback(async () => {
    if (!api.getToken()) { setUser(null); setLoading(false); return; }
    try { setUser(await api.me()); }
    catch { api.clearSession(); setUser(null); }
    finally { setLoading(false); }
  }, []);

  const loadContext = useCallback(async () => {
    try { setCtx(await api.getMyContext()); }
    catch { setCtx(null); }
  }, []);

  useEffect(() => { loadMe(); }, [loadMe]);

  useEffect(() => {
    if (!user) { setCtx(null); return; }
    let alive = true;
    api.health()
      .then((d) => alive && setHp({ state: "ok", data: d }))
      .catch(() => alive && setHp({ state: "bad", data: null }));
    loadContext();
    return () => { alive = false; };
  }, [user, loadContext]);

  async function pickProject(pid) {
    setWsOpen(false);
    try {
      const next = await api.setActiveProject(pid);
      setCtx(next);
      if (pid && next.active_project?.module_code) {
        setSection(next.active_project.module_code);
      }
    } catch (e) { /* silencioso, ya vendrá un refresh */ }
  }

  if (loading)
    return <div className="login-wrap"><span className="muted">Inicializando Command Center…</span></div>;
  if (!user) return <Login onLogged={loadMe} />;

  const isAdmin = user.role === "admin";

  const OPS = [
    { id: "dashboard", code: "DSH", label: "Centro de Operaciones" },
    { id: "documents", code: "DOC", label: "Documentos" },
    { id: "runner", code: "RUN", label: "Motor de Ejecución", admin: true },
    { id: "workspaces", code: "WKS", label: "Workspaces", admin: true },
    { id: "inscripciones", code: "INS", label: "Inscripciones", admin: true },
    { id: "users", code: "USR", label: "Cuentas", admin: true },
    { id: "profile", code: "PRF", label: "Mi Perfil", admin: true },
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
          ctx={ctx}
          isAdmin={isAdmin}
          goDocs={() => go("documents")}
          goRunner={() => go("runner")}
        />
      );
    switch (section) {
      case "runner": return isAdmin ? <Runner /> : <Dashboard user={user} health={hp} />;
      case "users": return isAdmin ? <Users /> : <Dashboard user={user} health={hp} />;
      case "workspaces":
        return isAdmin
          ? <Workspaces onContextChanged={loadContext} />
          : <Dashboard user={user} health={hp} />;
      case "inscripciones":
        return isAdmin ? <Inscripciones /> : <Dashboard user={user} health={hp} />;
      case "profile":
        return isAdmin ? <Profile user={user} /> : <Dashboard user={user} health={hp} />;
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
        <div className={`cc-ws${wsOpen ? " open" : ""}`}>
          <button
            type="button"
            className="cc-ws-btn"
            onClick={() => setWsOpen((o) => !o)}
            aria-haspopup="listbox"
            aria-expanded={wsOpen}
          >
            <span className="cc-ws-l">Workspace</span>
            <span className="cc-ws-v">
              {ctx?.active_project
                ? `${ctx.active_project.module_code || "—"} · ${ctx.active_project.name}`
                : "Sin proyecto activo"}
            </span>
            <span className="cc-ws-chev">▾</span>
          </button>
          {wsOpen && (
            <div className="cc-ws-pop" role="listbox">
              <button
                className={`cc-ws-opt${!ctx?.active_project ? " on" : ""}`}
                onClick={() => pickProject(null)}
              >
                <b>Sin proyecto activo</b>
                <span>Trabajar fuera de un proyecto</span>
              </button>
              {(ctx?.projects || []).map((p) => (
                <button key={p.id}
                  className={`cc-ws-opt${ctx?.active_project?.id === p.id ? " on" : ""}`}
                  onClick={() => pickProject(p.id)}>
                  <b>{p.name}</b>
                  <span>{p.module_code || "—"} · {p.period_label || "sin período"}</span>
                </button>
              ))}
              {(!ctx?.projects || ctx.projects.length === 0) && (
                <div className="cc-ws-empty">
                  No hay proyectos asignados.{" "}
                  {isAdmin && (
                    <button type="button" className="link"
                      onClick={() => { setWsOpen(false); go("workspaces"); }}>
                      Crear uno
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        <div className="cc-search">
          <input
            type="text"
            value={headerSearch}
            onChange={(e) => setHeaderSearch(e.target.value)}
            placeholder="Buscar en AUDIT-IA… (indexación en Fase 2)"
            aria-label="Buscar en AUDIT-IA"
          />
          <kbd>⌘K</kbd>
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
            <div className="cc-ctx-k">Organización</div>
            <div className="cc-ctx-v">
              {ctx?.organization?.name || <span className="dim">—</span>}
            </div>
            <div className="cc-ctx-k">Nodo activo</div>
            <div className="cc-ctx-v">{crumb.code} · {crumb.label}</div>
            <div className="cc-ctx-k">Cliente</div>
            <div className="cc-ctx-v">
              {ctx?.active_client?.name
                || <span className="dim">Sin cliente asignado</span>}
            </div>
            <div className="cc-ctx-k">Proyecto</div>
            <div className="cc-ctx-v">
              {ctx?.active_project?.name
                || <span className="dim">Sin proyecto activo</span>}
            </div>
            <div className="cc-ctx-k">Período</div>
            <div className="cc-ctx-v">
              {ctx?.active_project?.period_label
                || <span className="dim">—</span>}
            </div>
          </div>
          <TokensPanel llm={hp.data?.llm} />
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
        <span><b>AUDIT-IA</b> · v{hp.data?.version || "—"}</span>
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
