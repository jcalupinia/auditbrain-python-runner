import { Button } from "@auditbrain/shared";
import { useNavigate } from "react-router-dom";

export function Hero() {
  const nav = useNavigate();
  return (
    <section style={{ background: "#0a2540", color: "#fff", padding: "80px 20px", textAlign: "center" }}>
      <h1 style={{ fontSize: 42, margin: 0 }}>
        Automatiza tu cumplimiento tributario y NIIF
      </h1>
      <p style={{ fontSize: 18, maxWidth: 700, margin: "16px auto", opacity: 0.9 }}>
        Sube tus documentos contables y descarga entregables ya llenados en minutos.
        Procesos auditados, seguros y disponibles por solo 24h por tu privacidad.
      </p>
      <div style={{ marginTop: 30 }}>
        <Button onClick={() => nav("/login")}>Ingresar al portal</Button>
      </div>
      <p style={{ fontSize: 13, marginTop: 24, opacity: 0.7 }}>
        Audit Consulting Group · Powered by <strong>Audit-IA</strong>
      </p>
    </section>
  );
}
