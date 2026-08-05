import { useEffect, useState } from "react";
import * as api from "../../api.js";
import { STRINGS } from "../strings.js";
import { calcularCorrecciones, contarRequierenRevision, ordenarPorConfianza } from "./ofLogic.js";

const fmtMonto = new Intl.NumberFormat("es-EC", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function chipConfianza(confianza) {
  if (confianza === "alta") return "pc-chip on";
  if (confianza === "media") return "pc-chip warn";
  if (confianza === "baja") return "pc-chip danger";
  return "pc-chip";
}

/*
 * Pantalla de revisión de la clasificación — el corazón de la herramienta:
 * aquí el auditor confirma (o corrige) lo que el motor propuso para cada
 * cuenta del Mayor General antes de aprobar y generar el Excel.
 *
 * Se ordena por confianza ASCENDENTE (baja → media → alta): lo dudoso
 * primero, para que el auditor no tenga que buscarlo entre lo resuelto.
 *
 * Props:
 *   jobId       id del job en estado 'revision'
 *   onAprobado(jobActualizado)  se llama tras aprobarOF exitoso
 */
export default function RevisionClasificacion({ jobId, onAprobado }) {
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [cuentas, setCuentas] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [edits, setEdits] = useState({}); // { codigo_cuenta: categoriaElegida } — sin guardar
  const [guardando, setGuardando] = useState(false);
  const [aprobando, setAprobando] = useState(false);
  const [aviso, setAviso] = useState("");

  async function cargar() {
    setCargando(true);
    setError("");
    try {
      const resp = await api.getClasificacionOF(jobId);
      setCuentas(resp.cuentas || []);
      setCategorias(resp.categorias || []);
      setEdits({});
    } catch (e) {
      setError(e.message || STRINGS.of_rev_error_cargar);
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    if (jobId) cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const correcciones = calcularCorrecciones(cuentas, edits);
  const hayCambiosSinGuardar = correcciones.length > 0;
  const requierenRevision = contarRequierenRevision(cuentas);
  const filas = ordenarPorConfianza(cuentas);

  function handleCambioCategoria(codigoCuenta, nuevaCategoria) {
    setEdits((prev) => ({ ...prev, [codigoCuenta]: nuevaCategoria }));
    setAviso("");
  }

  async function guardarCorrecciones() {
    setGuardando(true);
    setError("");
    setAviso("");
    try {
      const resp = await api.guardarCorreccionesOF(jobId, correcciones);
      setCuentas(resp.cuentas || []);
      setEdits({});
      setAviso(STRINGS.of_rev_guardado_ok);
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  }

  async function aprobar() {
    if (hayCambiosSinGuardar) return;
    setAprobando(true);
    setError("");
    try {
      const job = await api.aprobarOF(jobId);
      onAprobado?.(job);
    } catch (e) {
      setError(e.message);
    } finally {
      setAprobando(false);
    }
  }

  if (cargando) {
    return <div style={{ color: "var(--text-soft)", fontSize: 13 }}>{STRINGS.of_rev_cargando}</div>;
  }

  if (error && cuentas.length === 0) {
    return <div className="err">{error}</div>;
  }

  if (cuentas.length === 0) {
    return <div style={{ color: "var(--text-soft)", fontSize: 13 }}>{STRINGS.of_rev_sin_cuentas}</div>;
  }

  return (
    <div>
      <div
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          flexWrap: "wrap", gap: 10, marginBottom: 14,
        }}
      >
        <div style={{ fontSize: 13, color: "var(--text-soft)" }}>
          <b style={{ color: "var(--text)" }}>{cuentas.length}</b> {STRINGS.of_rev_cuentas} ·{" "}
          <b style={{ color: requierenRevision > 0 ? "var(--warn)" : "var(--accent)" }}>
            {requierenRevision}
          </b>{" "}
          {STRINGS.of_rev_requieren_revision}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            type="button"
            className="pc-chip"
            onClick={guardarCorrecciones}
            disabled={!hayCambiosSinGuardar || guardando}
          >
            {guardando ? STRINGS.of_rev_guardando : `${STRINGS.of_rev_guardar}${hayCambiosSinGuardar ? ` (${correcciones.length})` : ""}`}
          </button>
          <button
            type="button"
            className="pc-chip accent"
            onClick={aprobar}
            disabled={hayCambiosSinGuardar || aprobando}
            title={hayCambiosSinGuardar ? STRINGS.of_rev_aprobar_disabled : undefined}
            style={{ fontWeight: 700 }}
          >
            {aprobando ? STRINGS.of_rev_aprobando : STRINGS.of_rev_aprobar}
          </button>
        </div>
      </div>

      {error && <div className="err" style={{ marginBottom: 10 }}>{error}</div>}
      {aviso && !error && (
        <div className="ok-msg" style={{ marginTop: 0, marginBottom: 10 }}>{aviso}</div>
      )}

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--line)" }}>
              {[
                STRINGS.of_rev_col_codigo, STRINGS.of_rev_col_cuenta, STRINGS.of_rev_col_movs,
                STRINGS.of_rev_col_debe, STRINGS.of_rev_col_haber, STRINGS.of_rev_col_categoria,
                STRINGS.of_rev_col_confianza, STRINGS.of_rev_col_porque,
              ].map((h) => (
                <th
                  key={h}
                  style={{
                    textAlign: "left", padding: "8px 10px", color: "var(--text-dim)",
                    fontSize: 10.5, letterSpacing: "0.08em", textTransform: "uppercase",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.map((c) => {
              const valorActual = edits[c.codigo_cuenta] ?? c.categoria_final ?? "";
              const editadaLocal = Object.prototype.hasOwnProperty.call(edits, c.codigo_cuenta)
                && edits[c.codigo_cuenta] !== c.categoria_final;
              const destacada = c.corregida || editadaLocal;
              const justificacion = (c.justificacion || []).filter(Boolean);
              const textoJustificacion = justificacion.join(" · ");
              const esLarga = justificacion.length > 2 || textoJustificacion.length > 70;

              return (
                <tr
                  key={c.codigo_cuenta}
                  style={{
                    borderBottom: "1px solid var(--line-soft)",
                    background: destacada ? "var(--accent-dim)" : "transparent",
                  }}
                >
                  <td style={{ padding: "8px 10px", fontFamily: "var(--mono)", whiteSpace: "nowrap" }}>
                    {c.codigo_cuenta}
                  </td>
                  <td style={{ padding: "8px 10px" }}>{c.nombre_cuenta}</td>
                  <td style={{ padding: "8px 10px", textAlign: "right" }}>{c.n_movimientos}</td>
                  <td style={{ padding: "8px 10px", textAlign: "right", fontFamily: "var(--mono)" }}>
                    {fmtMonto.format(c.debe || 0)}
                  </td>
                  <td style={{ padding: "8px 10px", textAlign: "right", fontFamily: "var(--mono)" }}>
                    {fmtMonto.format(c.haber || 0)}
                  </td>
                  <td style={{ padding: "8px 10px", minWidth: 200 }}>
                    <select
                      value={valorActual}
                      onChange={(e) => handleCambioCategoria(c.codigo_cuenta, e.target.value)}
                      style={{ padding: "6px 8px", fontSize: 12 }}
                    >
                      <option value="">{STRINGS.of_rev_categoria_sin_asignar}</option>
                      {categorias.map((cat) => (
                        <option key={cat.codigo} value={cat.codigo}>{cat.nombre}</option>
                      ))}
                    </select>
                    {destacada && c.categoria_sugerida && c.categoria_sugerida !== valorActual && (
                      <div style={{ fontSize: 10.5, color: "var(--text-soft)", marginTop: 3 }}>
                        {STRINGS.of_rev_sugerido}{" "}
                        {categorias.find((cat) => cat.codigo === c.categoria_sugerida)?.nombre
                          || c.categoria_sugerida}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: "8px 10px", whiteSpace: "nowrap" }}>
                    <span className={chipConfianza(c.confianza)} style={{ cursor: "default", padding: "3px 9px" }}>
                      {c.confianza || "?"}
                    </span>
                  </td>
                  <td style={{ padding: "8px 10px", maxWidth: 320, color: "var(--text-soft)" }}>
                    {justificacion.length === 0 ? (
                      STRINGS.of_rev_sin_justificacion
                    ) : esLarga ? (
                      <details>
                        <summary style={{ cursor: "pointer", color: "var(--accent)" }}>
                          {STRINGS.of_rev_ver_motivos} ({justificacion.length})
                        </summary>
                        <ul style={{ margin: "6px 0 0", paddingLeft: 16 }}>
                          {justificacion.map((j, i) => <li key={i}>{j}</li>)}
                        </ul>
                      </details>
                    ) : (
                      textoJustificacion
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
