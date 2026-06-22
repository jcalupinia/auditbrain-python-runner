import { useState } from "react";
import ChartSelector from "./ChartSelector";

// Botón + modal del asistente Skill 051. `onChartSelected(chart)` recibe el
// objeto del gráfico recomendado ({id,name,code,...}) cuando el usuario aplica.
export default function ChartSelectorModal({ onChartSelected }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)} style={{
        fontSize: 13, padding: "6px 16px", borderRadius: 8,
        border: "0.5px solid #AFA9EC", background: "#EEEDFE",
        color: "#3C3489", cursor: "pointer", fontWeight: 500,
        display: "flex", alignItems: "center", gap: 6,
      }}>
        📊 Seleccionar gráfico
      </button>
      {open && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 1000,
          background: "rgba(0,0,0,0.45)", display: "flex",
          alignItems: "center", justifyContent: "center", padding: 24,
        }}>
          <div style={{
            background: "#fff", borderRadius: 16, width: "100%",
            maxWidth: 720, maxHeight: "90vh", overflowY: "auto",
            padding: "1.5rem", position: "relative",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 15, fontWeight: 500 }}>Selección de gráfico</span>
                <span style={{ background: "#EEEDFE", color: "#3C3489", fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 99 }}>Skill 051 · AUDIT-IA</span>
              </div>
              <button onClick={() => setOpen(false)} style={{ border: "none", background: "transparent", fontSize: 20, cursor: "pointer", color: "#888" }}>×</button>
            </div>
            <ChartSelector onSelect={(chart) => { onChartSelected?.(chart); setOpen(false); }} />
          </div>
        </div>
      )}
    </>
  );
}
