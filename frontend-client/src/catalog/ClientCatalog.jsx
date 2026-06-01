import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCatalog } from "../api.js";
import { useAuth } from "../auth/AuthProvider.jsx";
import PortalShell from "../shell/PortalShell.jsx";

/* ============================================================
   Portal Cliente · Catálogo de herramientas
   Vista por defecto dentro del PortalShell. Listado de las 4
   categorías (Tributarias / NIIF / Laborales / Societarias)
   con sus herramientas.
   ============================================================ */

export default function ClientCatalog() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [cats, setCats] = useState([]);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCatalog()
      .then((r) => setCats(r.categories || []))
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, []);

  const totalTools = cats.reduce((n, c) => n + (c.tools?.length || 0), 0);
  const userName = user?.email
    ? user.email.split("@")[0].split(/[._-]/)[0]
    : "Cliente";
  const displayName = userName.charAt(0).toUpperCase() + userName.slice(1);

  return (
    <PortalShell
      title="CATÁLOGO"
      subtitle="Herramientas disponibles en tu portal"
    >
      <section className="pc-hero">
        <h1>
          Hola <span>{displayName}</span>,
          <br />
          bienvenido a <span>AuditBrain</span>
        </h1>
        <p>
          Plataforma operativa de cumplimiento e inteligencia empresarial ·{" "}
          {totalTools > 0
            ? `${totalTools} herramienta${totalTools === 1 ? "" : "s"} habilitada${totalTools === 1 ? "" : "s"} para ti.`
            : "herramientas próximamente."}
        </p>
      </section>

      {loading && (
        <div className="pc-panel">
          <div className="pc-panel-b" style={{ color: "var(--text-soft)" }}>
            Cargando catálogo…
          </div>
        </div>
      )}

      {err && (
        <div className="pc-panel" style={{ borderColor: "var(--danger)" }}>
          <div className="pc-panel-b" style={{ color: "var(--danger)" }}>
            {err}
          </div>
        </div>
      )}

      {!loading && !err && cats.map((cat) => (
        <section key={cat.id} className="pc-panel">
          <header className="pc-panel-h">
            <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
              <span className="pc-code">{cat.id.slice(0, 4)}</span>
              <span className="pc-panel-t">{cat.label}</span>
            </div>
            <span className="pc-panel-m">
              {cat.tools.length} TOOL{cat.tools.length === 1 ? "" : "S"}
            </span>
          </header>
          <div className="pc-panel-b">
            {cat.description && (
              <p style={{ color: "var(--text-soft)", margin: "0 0 14px", fontSize: 13 }}>
                {cat.description}
              </p>
            )}
            {cat.tools.length === 0 ? (
              <div className="pc-tile" style={{ cursor: "default", opacity: 0.7 }}>
                <span className="pc-tile-n dim">⏳</span>
                <div className="pc-tile-txt">
                  <span className="pc-tile-t">Próximamente</span>
                  <span className="pc-tile-d">
                    Las herramientas de esta categoría estarán disponibles pronto.
                  </span>
                </div>
              </div>
            ) : (
              <div className="pc-tiles">
                {cat.tools.map((t, i) => (
                  <button
                    key={t.code}
                    className="pc-tile"
                    onClick={() => {
                      if (t.code === "ICT_2025") nav("/tools/ICT_2025");
                      else nav(`/tools/${t.code}`);
                    }}
                  >
                    <span className="pc-tile-n">{i + 1}</span>
                    <div className="pc-tile-txt">
                      <span className="pc-tile-t">{t.label}</span>
                      <span className="pc-tile-d">{t.description}</span>
                    </div>
                    <span className="pc-tile-st">Abrir →</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>
      ))}
    </PortalShell>
  );
}
