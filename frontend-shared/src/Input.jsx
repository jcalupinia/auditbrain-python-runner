export function Input({ label, error, ...rest }) {
  return (
    <div style={{ marginBottom: 12 }}>
      {label && (
        <label style={{ display: "block", marginBottom: 4, fontSize: 13, color: "#555" }}>
          {label}
        </label>
      )}
      <input
        style={{
          width: "100%",
          padding: "10px 12px",
          borderRadius: 6,
          border: error ? "1px solid #c0392b" : "1px solid #ccc",
          fontSize: 14,
          boxSizing: "border-box",
        }}
        {...rest}
      />
      {error && (
        <div style={{ color: "#c0392b", fontSize: 12, marginTop: 4 }}>{error}</div>
      )}
    </div>
  );
}
