import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCatalog } from "../api.js";
import { useAuth } from "../auth/AuthProvider.jsx";
import "./catalog.css";

/* ============================================================
   Portal Cliente · Catálogo de herramientas
   Mismo lenguaje visual que el Command Center de AuditBrain staff:
   fondo oscuro premium, paneles, acento verde, monoespaciada para
   códigos. Categorías servidas por /api/v1/client/catalog del
   backend (tool_registry.CATEGORIES).
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

export default function ClientCatalog() {
  const { logout, user } = useAuth();
  const nav = useNavigate();
  const [cats, setCats] = useState([]);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCatalog()
      .then((r) => setCats(r.categories))
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, []);

  const totalTools = cats.reduce((n, c) => n + (c.tools?.length || 0), 0);
  const userName = user?.email
    ? user.email.split("@")[0].split(/[._-]/)[0]
    : "Cliente";
  const displayName = userName.charAt(0).toUpperCase() + userName.slice(1);

  return (
    <div className="ab-cat">
      {/* ----- Header ----- */}
      <header className="ab-cat-head">
        <div className="ab-cat-head-brand">
          <BrandMark size={30} />
          <div>
            <div className="bname">AuditBrain<span> IA</span></div>
            <div className="btag">Enterprise Intelligence OS</div>
          </div>
          <span className="ab-cat-head-pill">● Portal Clientes</span>
        </div>

        <div className="ab-cat-head-r">
          <div className="ab-cat-user">
            <span className="ab-cat-user-n">{user?.email || displayName}</span>
            <span className="ab-cat-user-r">cliente</span>
          </div>
          <button
            className="ab-cat-btn-ghost"
            onClick={() => logout().then(() => nav("/login"))}
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      {/* ----- Hero ----- */}
      <div className="ab-cat-hero">
        <h1>
          Hola <span>{displayName}</span>, bienvenido a{" "}
          <span>AuditBrain</span>
        </h1>
        <p>
          Plataforma operativa de cumplimiento e inteligencia empresarial ·
          {totalTools > 0
            ? ` ${totalTools} herramienta${totalTools === 1 ? "" : "s"} disponible${totalTools === 1 ? "" : "s"} para ti.`
            : " herramientas próximamente."}
        </p>
      </div>

      {/* ----- Main ----- */}
      <main className="ab-cat-main">
        {loading && (
          <div className="ab-cat-empty">
            <span>Cargando catálogo…</span>
          </div>
        )}

        {err && <div className="ab-cat-err">{err}</div>}

        {!loading && !err && cats.map((cat) => (
          <section key={cat.id} className="ab-cat-section">
            <div className="ab-cat-section-h">
              <span className="ab-cat-section-code">{cat.id}</span>
              <span className="ab-cat-section-t">{cat.label}</span>
              {cat.description && (
                <span className="ab-cat-section-sub">{cat.description}</span>
              )}
            </div>

            {cat.tools.length === 0 ? (
              <div className="ab-cat-empty">
                <span className="ab-cat-empty-tag">Próximamente</span>
                <span>
                  Las herramientas de esta categoría estarán disponibles en
                  breve. Pregunta a tu auditor por el calendario de release.
                </span>
              </div>
            ) : (
              <div className="ab-cat-grid">
                {cat.tools.map((t) => (
                  <button
                    key={t.code}
                    className="ab-cat-card"
                    onClick={() => {
                      if (t.code === "ICT_2025") {
                        nav("/tools/ICT_2025");
                      } else {
                        nav(`/tools/${t.code}`);
                      }
                    }}
                  >
                    <div className="ab-cat-card-h">
                      <span className="ab-cat-card-code">{t.code}</span>
                    </div>
                    <div className="ab-cat-card-t">{t.label}</div>
                    <p className="ab-cat-card-d">{t.description}</p>
                    <div className="ab-cat-card-cta">Abrir herramienta →</div>
                  </button>
                ))}
              </div>
            )}
          </section>
        ))}
      </main>

      {/* ----- Footer ----- */}
      <footer className="ab-cat-foot">
        <span>
          <b>AuditBrain IA</b> · Portal Cliente · Audit Consulting Group
        </span>
        <span>
          <span className="ok-dot" /> Sesión segura · JWT + Device binding
        </span>
      </footer>
    </div>
  );
}
