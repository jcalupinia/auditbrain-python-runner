import { useState } from "react";
import { validarCoherenciaSri } from "../api.js";
import PortalShell from "../shell/PortalShell.jsx";
import "./validadorSri.css";

// Validador de coherencia SRI (portal cliente, Fase 9). El cliente sube sus
// F-101/F-103/F-104 y ve el cruce entre ellos ANTES de generar el ICT. No
// genera el ICT ni toca su flujo: es un chequeo informativo que consume el
// Motor de Ingesta en el backend.

const BADGE = {
  ok: ["vs-ok", "CUADRA"],
  diferencia: ["vs-dif", "DIFERENCIA"],
  faltante: ["vs-falta", "FALTA"],
  informativo: ["vs-info", "INFO"],
};

const fmt = (n) =>
  n === null || n === undefined
    ? null
    : n.toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function ValidadorSriDashboard() {
  const [f101, setF101] = useState(null);
  const [f103, setF103] = useState([]);
  const [f104, setF104] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [rep, setRep] = useState(null);

  const validar = async () => {
    if (!f101 || busy) return;
    setBusy(true);
    setError("");
    try {
      const r = await validarCoherenciaSri(f101, f103, f104);
      setRep(r);
    } catch (e) {
      setError(e?.message || "No se pudo completar la validación.");
    } finally {
      setBusy(false);
    }
  };

  const resumenClase = rep
    ? rep.resumen.includes("DIFERENCIAS")
      ? "dif"
      : rep.resumen.includes("FALTAN")
        ? "falta"
        : "ok"
    : "";

  return (
    <PortalShell title="VALIDADOR SRI" subtitle="Chequeo de coherencia previo al ICT">
      <section className="pc-hero">
        <h1>
          Valida tus <span>formularios SRI</span>
        </h1>
        <p>
          Sube el F-101 anual y tus F-103/F-104 mensuales. Revisamos el cruce entre ellos
          (ventas del Renta vs base del IVA, los 12 meses y pagos al exterior) antes de que
          generes el ICT. Es un chequeo informativo; no genera el ICT.
        </p>
      </section>

      <section className="pc-panel">
        <header className="pc-panel-h">
          <span className="pc-panel-t">Formularios</span>
        </header>
        <div className="pc-panel-b">
          <div className="vs-drop">
            <label className="vs-slot">
              <span className="vs-slot-t">F-101 · Renta (anual)</span>
              <span className="vs-slot-d">1 archivo PDF</span>
              <input type="file" accept=".pdf" onChange={(e) => setF101(e.target.files?.[0] || null)} />
              {f101 && <span className="vs-count">{f101.name}</span>}
            </label>
            <label className="vs-slot">
              <span className="vs-slot-t">F-103 · Retenciones (mensual)</span>
              <span className="vs-slot-d">Hasta 12 PDFs</span>
              <input type="file" accept=".pdf" multiple onChange={(e) => setF103([...e.target.files])} />
              {f103.length > 0 && <span className="vs-count">{f103.length} archivo(s)</span>}
            </label>
            <label className="vs-slot">
              <span className="vs-slot-t">F-104 · IVA (mensual)</span>
              <span className="vs-slot-d">Hasta 12 PDFs</span>
              <input type="file" accept=".pdf" multiple onChange={(e) => setF104([...e.target.files])} />
              {f104.length > 0 && <span className="vs-count">{f104.length} archivo(s)</span>}
            </label>
          </div>
          <button className="pc-btn" disabled={!f101 || busy} onClick={validar}>
            {busy ? "Validando…" : "Validar coherencia"}
          </button>
          {error && (
            <p style={{ color: "var(--danger)", marginTop: 10, fontSize: 13 }} role="alert">
              {error}
            </p>
          )}
        </div>
      </section>

      {rep && (
        <section className="pc-panel">
          <header className="pc-panel-h">
            <span className="pc-panel-t">Resultado</span>
            <span className="pc-panel-m">
              {rep.f101} F-101 · {rep.f103} F-103 · {rep.f104} F-104
            </span>
          </header>
          <div className="pc-panel-b">
            <div className={`vs-resumen ${resumenClase}`}>{rep.resumen}</div>

            {rep.chequeos.map((c, i) => {
              const [cls, txt] = BADGE[c.estado] || BADGE.informativo;
              return (
                <div className="vs-check" key={i}>
                  <span className={`vs-badge ${cls}`}>{txt}</span>
                  <div className="vs-check-txt">
                    <div className="vs-check-t">{c.titulo}</div>
                    <div className="vs-check-d">{c.detalle}</div>
                    {(c.esperado != null || c.encontrado != null || c.diferencia != null) && (
                      <div className="vs-nums">
                        {c.esperado != null && <>Esperado: {fmt(c.esperado)} · </>}
                        {c.encontrado != null && <>Encontrado: {fmt(c.encontrado)}</>}
                        {c.diferencia != null && <> · Diferencia: {fmt(c.diferencia)}</>}
                      </div>
                    )}
                    {c.casilleros?.length > 0 && (
                      <div className="vs-cas">Casilleros: {c.casilleros.join(", ")}</div>
                    )}
                  </div>
                </div>
              );
            })}

            <p className="vs-disclaimer">
              Chequeo informativo y determinista. La validación final del auditor sigue siendo
              necesaria; esta herramienta no genera ni reemplaza el ICT.
            </p>
          </div>
        </section>
      )}
    </PortalShell>
  );
}
