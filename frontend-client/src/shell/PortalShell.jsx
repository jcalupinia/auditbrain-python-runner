import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider.jsx";
import { getCatalog } from "../api.js";
import "./shell.css";

/* ============================================================
   Portal Cliente · Shell Command Center
   Wrapper visual común a TODAS las pantallas autenticadas del
   portal cliente. Replica el layout del Command Center del staff
   (sidebar módulos · header · main · sidebar contexto · footer)
   pero con las categorías reales del cliente y el contexto activo
   reducido a lo relevante para el cliente.
   ============================================================ */

function BrandMark({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect x="2" y="2" width="36" height="36" rx="9"
        fill="none" stroke="var(--accent)" strokeWidth="2.5" />
      <path d="M11 28 L20 12 L29 28"
        fill="none" stroke="var(--accent)" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" />
      <line x1="15" y1="22" x2="25" y2="22"
        stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/**
 * Logo corporativo de Audit Consulting Group con fallback al BrandMark+texto
 * cuando la imagen no carga (entornos sin la asset, vista previa rápida, etc.).
 */
function CorporateLogo() {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <>
        <BrandMark size={30} />
        <div className="pc-brand-txt">
          <span>AUDIT CONSULTING</span>
          <b>GROUP</b>
        </div>
      </>
    );
  }
  return (
    <img
      src="/assets/logo-auditconsulting-group.png"
      alt="Audit Consulting Group"
      onError={() => setFailed(true)}
      style={{
        maxHeight: 44,
        maxWidth: "100%",
        objectFit: "contain",
        filter: "drop-shadow(0 1px 4px rgba(0,0,0,0.4))",
      }}
    />
  );
}

export default function PortalShell({
  title = "PORTAL CLIENTES",
  subtitle = "Workspace de Cumplimiento e Inteligencia",
  activeCategory = null,    // ID de categoría activa para resaltar en sidebar
  activeNodeCode = null,    // ej. "ICT_2025" para resaltar herramienta abierta
  contextExtras = null,     // contenido extra para el panel derecho (ej. progreso ICT)
  children,
}) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const [categories, setCategories] = useState([]);
  const [navOpen, setNavOpen] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    getCatalog().then((r) => setCategories(r.categories || [])).catch(() => {});
  }, []);

  const userName = user?.email
    ? user.email.split("@")[0].split(/[._-]/)[0]
    : "Cliente";
  const displayName = userName.charAt(0).toUpperCase() + userName.slice(1);

  const onCatClick = (cat) => {
    setNavOpen(false);
    // Si la categoría tiene una sola herramienta, ir directo. Si no, al catálogo.
    if (cat.tools?.length === 1) {
      const code = cat.tools[0].code;
      if (code === "ICT_2025") nav("/tools/ICT_2025");
      else nav(`/tools/${code}`);
    } else {
      nav("/catalog");
    }
  };

  return (
    <div className={`pc${navOpen ? " nav-open" : ""}`}>
      {navOpen && <div className="pc-scrim" onClick={() => setNavOpen(false)} />}

      {/* ----- Brand cell (esq sup izq) — logo PNG real ----- */}
      <div className="pc-brand-cell">
        <CorporateLogo />
      </div>

      {/* ----- Sidebar izquierdo (módulos = categorías) ----- */}
      <aside className="pc-side">
        <nav>
          <div className="pc-group-l">Módulos</div>
          {categories.map((cat) => {
            const isActive = activeCategory === cat.id;
            const enabled = cat.tools?.length > 0;
            return (
              <button
                key={cat.id}
                className={`pc-node${isActive ? " on" : ""}`}
                onClick={() => onCatClick(cat)}
                disabled={!enabled}
                style={!enabled ? { opacity: 0.5, cursor: "not-allowed" } : {}}
                title={!enabled ? "Próximamente" : cat.label}
              >
                <span className="pc-code">{cat.id.slice(0, 4)}</span>
                <span className="pc-label">{cat.label.replace(/^Herramientas\s+/i, "")}</span>
                <span className="pc-chev">›</span>
              </button>
            );
          })}
          <div className="pc-group-l" style={{ marginTop: 18 }}>Operación</div>
          <button
            className={`pc-node${location.pathname === "/catalog" ? " on" : ""}`}
            onClick={() => { setNavOpen(false); nav("/catalog"); }}
          >
            <span className="pc-code">CAT</span>
            <span className="pc-label">Catálogo</span>
            <span className="pc-chev">›</span>
          </button>
        </nav>
        <div className="pc-side-foot">
          <div className="pc-group-l">Estado de la sesión</div>
          <div className="pc-status">
            <span className="pc-dot ok" />
            Sesión activa
          </div>
          <div className="pc-status-sub">JWT · Device binding</div>
        </div>
      </aside>

      {/* ----- Header ----- */}
      <header className="pc-head">
        <button className="pc-burger" onClick={() => setNavOpen((o) => !o)} aria-label="Menú">≡</button>
        <div className="pc-head-title">
          <b>{title}</b>
          <span>{subtitle}</span>
        </div>
        <div className="pc-head-ws">
          <span className="pc-head-ws-l">Cliente</span>
          <span className="pc-head-ws-v">
            {user?.email
              ? user.email.split("@")[1] || "—"
              : "—"}
          </span>
        </div>
        <div className="pc-head-search">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar herramientas… (próximamente)"
            aria-label="Buscar"
          />
          <kbd>⌘K</kbd>
        </div>
        <div className="pc-head-r">
          <div className="pc-user">
            <span className="pc-user-n">{user?.email || displayName}</span>
            <span className="pc-role">cliente</span>
          </div>
          <button
            className="pc-btn-ghost"
            onClick={() => logout().then(() => nav("/login"))}
          >
            Salir
          </button>
        </div>
      </header>

      {/* ----- Main ----- */}
      <main className="pc-main">{children}</main>

      {/* ----- Sidebar derecho (contexto activo) ----- */}
      <aside className="pc-ctx">
        <div className="pc-ctx-h">Contexto activo</div>
        <div className="pc-ctx-card">
          <div className="pc-ctx-h2">👤 Identidad</div>
          <div className="pc-ctx-k">Operador</div>
          <div className="pc-ctx-v" style={{ wordBreak: "break-all" }}>
            {user?.email || "—"}
          </div>
          <div className="pc-ctx-k">Privilegio</div>
          <div className="pc-ctx-v">
            <span className="pc-role" style={{ marginTop: 0 }}>cliente</span>
          </div>
          <div className="pc-ctx-k">Sesión</div>
          <div className="pc-ctx-v">
            <span className="pc-dot ok" /> Vinculada
          </div>
        </div>

        {contextExtras}

        <div className="pc-ctx-card">
          <div className="pc-ctx-h2">💡 Tips</div>
          <div className="pc-ctx-v" style={{ gridColumn: "1/-1", fontSize: 12 }}>
            <ul style={{ margin: 0, paddingLeft: 16, color: "var(--text-soft)" }}>
              <li>Sube los archivos de cada anexo en orden.</li>
              <li>Puedes descargar el Excel parcial en cualquier momento.</li>
              <li>Tu sesión es única por dispositivo (seguridad).</li>
            </ul>
          </div>
        </div>
      </aside>

      {/* ----- Footer ----- */}
      <footer className="pc-foot">
        <span>
          <b>AuditBrain IA</b> · Portal Cliente · Audit Consulting Group
        </span>
        <span className="pc-foot-r">
          <span><span className="pc-dot ok" /> Operativo</span>
          <span>Auth JWT</span>
          <span>Device binding</span>
        </span>
      </footer>
    </div>
  );
}
