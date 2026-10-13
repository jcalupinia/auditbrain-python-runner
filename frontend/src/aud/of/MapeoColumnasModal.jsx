import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import * as api from "../../api.js";

/*
 * Mapeo manual de columnas de un mayor que el detector no reconoció.
 * El auditor elige, para cada campo, qué columna del archivo le corresponde.
 * Exige al menos código, débito y haber (las columnas mínimas).
 *
 * Props:
 *   jobId, slot, nombre   identifican el archivo
 *   onClose()             cerrar sin guardar
 *   onSaved()             se llama tras guardar (el padre refresca / avisa)
 */

// Campos del lector, con etiqueta amigable. Los tres primeros son obligatorios.
const CAMPOS = [
  { key: "codigo", label: "Código de cuenta", req: true },
  { key: "debe", label: "Débito / Debe", req: true },
  { key: "haber", label: "Crédito / Haber", req: true },
  { key: "cuenta", label: "Nombre de la cuenta" },
  { key: "fecha", label: "Fecha" },
  { key: "asiento", label: "Asiento / Comprobante" },
  { key: "documento", label: "Documento / Factura" },
  { key: "identificacion", label: "RUC / Identificación" },
  { key: "persona", label: "Razón social / Tercero" },
  { key: "descripcion", label: "Descripción / Glosa" },
  { key: "saldo", label: "Saldo" },
];

const SIN_ASIGNAR = "";

export default function MapeoColumnasModal({ jobId, slot, nombre, onClose, onSaved }) {
  const [cargando, setCargando] = useState(true);
  const [headers, setHeaders] = useState([]);
  const [sel, setSel] = useState({}); // { campo: idx(string) }
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelado = false;
    setCargando(true);
    setError("");
    api
      .encabezadosMayorOF(jobId, slot, nombre)
      .then((info) => {
        if (cancelado) return;
        setHeaders(info.headers || []);
        // Pre-rellena con lo ya detectado + lo que el auditor hubiera guardado.
        const inicial = {
          ...(info.columnas_detectadas || {}),
          ...(info.mapeo_manual || {}),
        };
        const comoStr = {};
        Object.entries(inicial).forEach(([k, v]) => { comoStr[k] = String(v); });
        setSel(comoStr);
      })
      .catch((err) => { if (!cancelado) setError(err.message); })
      .finally(() => { if (!cancelado) setCargando(false); });
    return () => { cancelado = true; };
  }, [jobId, slot, nombre]);

  function cambiar(campo, valor) {
    setSel((s) => ({ ...s, [campo]: valor }));
  }

  // Columnas ya usadas por OTRO campo (para avisar del choque en la UI).
  function colUsadaPorOtro(campo, idx) {
    if (idx === SIN_ASIGNAR) return false;
    return Object.entries(sel).some(([k, v]) => k !== campo && v === idx);
  }

  async function guardar() {
    setError("");
    const mapeo = {};
    for (const [campo, idx] of Object.entries(sel)) {
      if (idx !== SIN_ASIGNAR) mapeo[campo] = Number(idx);
    }
    const faltan = CAMPOS.filter((c) => c.req && !(c.key in mapeo)).map((c) => c.label);
    if (faltan.length) {
      setError(`Asigna al menos: ${faltan.join(", ")}.`);
      return;
    }
    const indices = Object.values(mapeo);
    if (new Set(indices).size !== indices.length) {
      setError("Hay una columna asignada a dos campos a la vez.");
      return;
    }
    setBusy(true);
    try {
      await api.guardarMapeoColumnasOF(jobId, slot, nombre, mapeo);
      onSaved?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return createPortal(
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 9000,
        background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)",
        display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
      }}
      onClick={busy ? undefined : onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--panel)", border: "1px solid var(--line)",
          borderRadius: 14, maxWidth: 560, width: "100%",
          maxHeight: "88vh", overflowY: "auto", padding: "18px 20px",
        }}
      >
        <h3 style={{ marginTop: 0 }}>Mapear columnas del mayor</h3>
        <p style={{ fontSize: 12, color: "var(--text-soft)", marginTop: 0 }}>
          El sistema no reconoció algunas columnas de <b>{nombre}</b>. Indica qué
          columna del archivo corresponde a cada campo. Débito, crédito y código
          son obligatorios.
        </p>

        {cargando && <div style={{ fontSize: 13 }}>Leyendo encabezados…</div>}

        {!cargando && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 360, overflowY: "auto" }}>
            {CAMPOS.map((c) => (
              <label key={c.key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                <span style={{ minWidth: 190 }}>
                  {c.label}{c.req && <span style={{ color: "var(--danger, #d33)" }}> *</span>}
                </span>
                <select
                  value={sel[c.key] ?? SIN_ASIGNAR}
                  onChange={(e) => cambiar(c.key, e.target.value)}
                  style={{
                    flex: 1, padding: "5px 8px", fontSize: 12,
                    borderColor: colUsadaPorOtro(c.key, sel[c.key] ?? SIN_ASIGNAR)
                      ? "var(--danger, #d33)" : undefined,
                  }}
                >
                  <option value={SIN_ASIGNAR}>(sin asignar)</option>
                  {headers.map((h, i) => (
                    <option key={i} value={String(i)}>
                      Col {i + 1}: {h || "(vacía)"}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        )}

        {error && <div className="err" style={{ fontSize: 12, marginTop: 10 }}>{error}</div>}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
          <button type="button" className="pc-chip" onClick={onClose} disabled={busy}>
            Cancelar
          </button>
          <button type="button" className="pc-chip accent" onClick={guardar} disabled={busy || cargando}>
            {busy ? "Guardando…" : "Guardar mapeo"}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
