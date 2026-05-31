import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCatalog } from "../api.js";
import { useAuth } from "../auth/AuthProvider.jsx";

export default function ClientCatalog() {
  const { logout } = useAuth();
  const nav = useNavigate();
  const [cats, setCats] = useState([]);
  const [err, setErr] = useState(null);

  useEffect(() => {
    getCatalog().then((r) => setCats(r.categories)).catch((e) => setErr(e.message));
  }, []);

  return (
    <div>
      <header style={{ background: "#0a2540", color: "#fff", padding: "16px 24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <strong>Audit Consulting Group</strong>
          <span style={{ marginLeft: 8, opacity: 0.7, fontSize: 13 }}>· Powered by Audit-IA</span>
        </div>
        <button onClick={() => logout().then(() => nav("/login"))}
          style={{ background: "transparent", color: "#fff", border: "1px solid #fff", padding: "6px 14px", borderRadius: 6, cursor: "pointer" }}>
          Cerrar sesión
        </button>
      </header>

      <main style={{ maxWidth: 1100, margin: "30px auto", padding: 20 }}>
        <h1>Tus herramientas</h1>
        {err && <div style={{ color: "#c0392b" }}>{err}</div>}
        {cats.map((cat) => (
          <section key={cat.id} style={{ marginBottom: 32 }}>
            <h3 style={{ borderBottom: "2px solid #0a2540", paddingBottom: 6 }}>{cat.label}</h3>
            {cat.tools.length === 0 ? (
              <p style={{ color: "#888", fontStyle: "italic" }}>Próximamente</p>
            ) : (
              <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
                {cat.tools.map((t) => (
                  <button key={t.code}
                    onClick={() => {
                      if (t.code === "ICT_2025") {
                        nav("/tools/ICT_2025");
                      } else {
                        nav(`/tools/${t.code}`);
                      }
                    }}
                    style={{ textAlign: "left", background: "#fff", padding: 20, borderRadius: 8, border: "1px solid #e0e6ed", cursor: "pointer" }}>
                    <strong>{t.label}</strong>
                    <p style={{ color: "#555", fontSize: 14 }}>{t.description}</p>
                  </button>
                ))}
              </div>
            )}
          </section>
        ))}
      </main>
    </div>
  );
}
