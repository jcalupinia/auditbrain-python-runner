export function ProgressBar({ value = 0, label }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div style={{ marginBottom: 12 }}>
      {label && (
        <div style={{ fontSize: 13, marginBottom: 4, color: "#555" }}>{label}</div>
      )}
      <div style={{ background: "#eee", borderRadius: 4, overflow: "hidden", height: 10 }}>
        <div
          style={{
            background: "#0a2540", height: "100%", width: `${pct}%`,
            transition: "width 0.3s ease",
          }}
        />
      </div>
    </div>
  );
}
