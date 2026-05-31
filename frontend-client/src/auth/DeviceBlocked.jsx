export default function DeviceBlocked() {
  return (
    <div style={{ maxWidth: 480, margin: "80px auto", padding: 30, background: "#fff", borderRadius: 8, textAlign: "center", boxShadow: "0 2px 10px rgba(0,0,0,0.08)" }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>🛡️</div>
      <h2>Dispositivo no autorizado</h2>
      <p style={{ color: "#555" }}>
        Por política de seguridad, tu cuenta solo permite acceso desde un único computador.
        Este equipo no está registrado o tu dispositivo previo fue revocado.
      </p>
      <p style={{ color: "#555" }}>
        Solicita al equipo de Audit Consulting Group que autorice este nuevo equipo:
      </p>
      <p style={{ background: "#f4f7fb", padding: 12, borderRadius: 6, fontWeight: 600 }}>
        soporte@auditconsulting.com
      </p>
    </div>
  );
}
