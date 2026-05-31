import ICTUploader from "./ICTUploader.jsx";

const STATUS_DISPLAY = {
  empty:   { icon: "⚪", label: "Pendiente",  color: "#888" },
  partial: { icon: "🟡", label: "Parcial",    color: "#d4a72c" },
  ready:   { icon: "✅", label: "Completado", color: "#2ecc71" },
  error:   { icon: "❌", label: "Error",      color: "#c0392b" },
};

export default function ICTAnexoCard({ info, anexo, sessionId, onChanged }) {
  const display = STATUS_DISPLAY[anexo.status] || STATUS_DISPLAY.empty;

  return (
    <div style={{ background: "#fff", border: "1px solid #e0e6ed", borderRadius: 8, padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16 }}>{info.name}</h3>
          <p style={{ color: "#666", fontSize: 13, margin: "4px 0 0" }}>{info.desc}</p>
        </div>
        <span style={{ color: display.color, fontWeight: 600, whiteSpace: "nowrap", marginLeft: 16 }}>
          {display.icon} {display.label}
        </span>
      </div>

      {info.autoFill && (
        <p style={{ color: "#888", fontSize: 13, marginTop: 12, fontStyle: "italic" }}>
          Se llena automáticamente desde los datos del contribuyente y los demás anexos.
        </p>
      )}

      {info.slots && (
        <div style={{ marginTop: 16 }}>
          {info.slots.map((slot) => {
            const uploaded = anexo.uploaded_files?.[slot.key];
            return (
              <div key={slot.key} style={{ marginBottom: 12, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <span style={{ fontWeight: 500, fontSize: 14 }}>{slot.label}</span>
                  {slot.required && <span style={{ color: "#c0392b", marginLeft: 4 }}>*</span>}
                  {uploaded && (
                    <div style={{ color: "#2ecc71", fontSize: 12, marginTop: 2 }}>
                      ✅ {uploaded.filename} ({Math.round(uploaded.size / 1024)} KB)
                    </div>
                  )}
                </div>
                <ICTUploader
                  sessionId={sessionId}
                  anexoCode={anexo.anexo_code}
                  slotName={slot.key}
                  onUploaded={onChanged}
                  hasFile={!!uploaded}
                  multi={!!slot.multi}
                />
              </div>
            );
          })}
        </div>
      )}

      {anexo.warnings && anexo.warnings.length > 0 && (
        <details style={{ marginTop: 12 }}>
          <summary style={{ cursor: "pointer", color: "#d4a72c", fontSize: 13 }}>
            {anexo.warnings.length} advertencia(s)
          </summary>
          <ul style={{ fontSize: 13, color: "#666", marginTop: 8 }}>
            {anexo.warnings.slice(0, 10).map((w, i) => <li key={i}>{w}</li>)}
            {anexo.warnings.length > 10 && <li>... y {anexo.warnings.length - 10} más</li>}
          </ul>
        </details>
      )}
    </div>
  );
}
