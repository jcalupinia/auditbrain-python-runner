const FEATURES = [
  { icon: "📄", title: "Anexo ICT 2025", desc: "Cumplimiento tributario SRI automatizado." },
  { icon: "💰", title: "NIIF 9 — ECL", desc: "Matriz de pérdidas esperadas en cartera." },
  { icon: "📦", title: "Inventarios NIC 2", desc: "Valor Neto Realización y obsolescencia." },
  { icon: "🏢", title: "Activos Fijos", desc: "Depreciación, deterioro y arrendamientos." },
  { icon: "🧾", title: "NIIF 15 Ingresos", desc: "Reconocimiento por obligaciones." },
  { icon: "🛡️", title: "Seguridad estricta", desc: "Datos eliminados a las 24h. Dispositivo vinculado." },
];

export function Features() {
  return (
    <section style={{ padding: "60px 20px", maxWidth: 1100, margin: "0 auto" }}>
      <h2 style={{ textAlign: "center", marginBottom: 40 }}>Herramientas disponibles</h2>
      <div style={{
        display: "grid", gap: 20,
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
      }}>
        {FEATURES.map((f) => (
          <div key={f.title} style={{
            background: "#fff", padding: 24, borderRadius: 8,
            boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
          }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>{f.icon}</div>
            <h3 style={{ margin: "0 0 8px", fontSize: 18 }}>{f.title}</h3>
            <p style={{ color: "#555", fontSize: 14, margin: 0 }}>{f.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
