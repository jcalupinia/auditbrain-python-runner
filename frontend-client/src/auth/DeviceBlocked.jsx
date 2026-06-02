export default function DeviceBlocked() {
  function clearAndRetry() {
    // Limpia TODO el localStorage (tokens viejos, flags, sid expirados)
    // y redirige a la pantalla de login para empezar desde cero. Útil
    // cuando el bloqueo se produjo por un JWT obsoleto (p. ej. tras un
    // reset administrativo del device, o tras una actualización del
    // backend que cambió la estructura del token).
    try {
      localStorage.clear();
      sessionStorage.clear();
    } catch {
      /* no-op */
    }
    window.location.href = "/login";
  }

  return (
    <div style={{
      maxWidth: 520, margin: "80px auto", padding: 32,
      background: "#fff", borderRadius: 10, textAlign: "center",
      boxShadow: "0 2px 14px rgba(0,0,0,0.08)",
      fontFamily: "Inter, system-ui, sans-serif",
    }}>
      <div style={{ fontSize: 52, marginBottom: 14 }}>🛡️</div>
      <h2 style={{ marginTop: 0, color: "#0a2540" }}>Dispositivo no autorizado</h2>
      <p style={{ color: "#555", lineHeight: 1.55 }}>
        Tu sesión local quedó desfasada o este equipo todavía no está
        registrado para tu cuenta. Suele pasar al cambiar de navegador,
        modo incógnito, o tras una actualización del portal.
      </p>

      <button
        onClick={clearAndRetry}
        style={{
          marginTop: 14, padding: "12px 24px",
          background: "#34d36a", color: "#04130b",
          border: "none", borderRadius: 8,
          fontSize: 14, fontWeight: 700,
          cursor: "pointer",
        }}
      >
        🔄 Limpiar sesión y volver a entrar
      </button>

      <p style={{ color: "#888", fontSize: 12, marginTop: 16 }}>
        Esto borra los datos locales del navegador (tokens, preferencias) y
        te lleva a la pantalla de login. Tus archivos del portal NO se borran.
      </p>

      <hr style={{ border: 0, borderTop: "1px solid #e0e6ed", margin: "24px 0 18px" }} />

      <p style={{ color: "#555", fontSize: 13 }}>
        Si después de limpiar y reintentar sigue bloqueado, contacta a
        Audit Consulting Group para autorizar este equipo:
      </p>
      <p style={{
        background: "#f4f7fb", padding: 12, borderRadius: 6,
        fontWeight: 600, fontSize: 14,
      }}>
        soporte@auditconsulting.com
      </p>
    </div>
  );
}
