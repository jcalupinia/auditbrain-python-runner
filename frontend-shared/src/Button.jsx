export function Button({ children, variant = "primary", ...rest }) {
  const styles = {
    primary: { background: "#0a2540", color: "#fff" },
    secondary: { background: "#fff", color: "#0a2540", border: "1px solid #0a2540" },
    danger: { background: "#c0392b", color: "#fff" },
  };
  return (
    <button
      style={{
        padding: "10px 18px",
        borderRadius: 6,
        border: "none",
        fontWeight: 600,
        cursor: "pointer",
        ...styles[variant],
      }}
      {...rest}
    >
      {children}
    </button>
  );
}
