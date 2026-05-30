import { Button } from "@auditbrain/shared";
import { useNavigate } from "react-router-dom";

export function CTAs() {
  const nav = useNavigate();
  return (
    <section style={{ background: "#fff", padding: "60px 20px", textAlign: "center", borderTop: "1px solid #e0e6ed" }}>
      <h2 style={{ marginTop: 0 }}>¿Ya tienes cuenta?</h2>
      <p style={{ color: "#555", marginBottom: 24 }}>
        Tu cuenta fue creada por el equipo de Audit Consulting Group.
        Solicita tus credenciales si aún no las has recibido.
      </p>
      <Button onClick={() => nav("/login")}>Ingresar</Button>
      <p style={{ marginTop: 30, fontSize: 13, color: "#888" }}>
        ¿Aún no eres cliente? Escríbenos: <a href="mailto:contacto@auditconsulting.com">contacto@auditconsulting.com</a>
      </p>
    </section>
  );
}
