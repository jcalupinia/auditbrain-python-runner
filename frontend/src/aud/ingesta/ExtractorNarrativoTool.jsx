import { useState } from "react";
import * as api from "./api.js";
import {
  evidenciaTexto,
  formatValor,
  metodoEtiqueta,
  nivelClase,
  nivelEtiqueta,
  tipoEtiqueta,
} from "./logic.js";
import "./ingesta.css";

// Herramienta NUEVA (Fase 9): extrae datos puntuales de un documento narrativo
// (contrato, carta de control interno, informe, notas) con trazabilidad al
// origen. Solo consume el Motor de Ingesta; no toca ninguna herramienta
// existente. Determinístico primero: fechas, montos, RUCs y porcentajes por
// regex; la IA (opcional) solo enumera obligaciones/partes/cláusulas (texto).

const ETIQUETA_CAMPO = {
  fecha: "Fechas",
  monto: "Montos",
  ruc: "RUC",
  porcentaje: "Porcentajes",
  obligacion: "Obligaciones",
  parte: "Partes",
  clausula: "Cláusulas",
  otro: "Otros",
};

// Orden de presentación de los grupos.
const ORDEN = ["ruc", "fecha", "monto", "porcentaje", "parte", "obligacion", "clausula", "otro"];

function agrupar(campos) {
  const grupos = {};
  for (const c of campos || []) {
    const k = c.field in ETIQUETA_CAMPO ? c.field : "otro";
    (grupos[k] = grupos[k] || []).push(c);
  }
  return ORDEN.filter((k) => grupos[k]).map((k) => [k, grupos[k]]);
}

export default function ExtractorNarrativoTool() {
  const [file, setFile] = useState(null);
  const [usarIa, setUsarIa] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dataset, setDataset] = useState(null);
  const [cola, setCola] = useState([]);

  const onFile = (e) => {
    setFile(e.target.files?.[0] || null);
    setDataset(null);
    setCola([]);
    setError("");
  };

  const extraer = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.narrativo(file, undefined, { usarIa });
      setDataset(r?.dataset || null);
      setCola(Array.isArray(r?.cola_revision) ? r.cola_revision : []);
    } catch (e) {
      setError(e?.message || "No se pudo completar la operación.");
    } finally {
      setBusy(false);
    }
  };

  const grupos = dataset ? agrupar(dataset.campos) : [];

  return (
    <div className="ing-tool">
      <header className="ing-head">
        <h2>Extractor de documentos narrativos</h2>
        <p className="muted">
          Extrae los datos puntuales de un contrato, carta de control interno, informe o
          notas a los estados financieros —con <b>trazabilidad al origen</b> (línea y
          fragmento). Útil para los requerimientos narrativos que no tienen un parser de
          casilleros.
        </p>
        <p className="ing-nota">
          Determinístico primero: fechas, montos, RUCs y porcentajes salen por regla, sin IA.
          La opción de IA solo enumera obligaciones, partes y cláusulas (texto explícito,
          nunca cifras) y queda marcada para revisión del auditor.
        </p>
      </header>

      <section className="ing-form">
        <div className="ing-row">
          <label className="ing-file">
            <span>Documento narrativo</span>
            <input type="file" onChange={onFile} accept=".pdf,.txt,.doc,.docx" />
          </label>
        </div>
        <div className="ing-row ing-controls">
          <label className="ing-check">
            <input
              type="checkbox"
              checked={usarIa}
              onChange={(e) => setUsarIa(e.target.checked)}
            />
            <span>Enumerar obligaciones, partes y cláusulas con IA (opcional)</span>
          </label>
          <div className="ing-actions">
            <button type="button" className="btn" disabled={!file || busy} onClick={extraer}>
              {busy ? "Extrayendo…" : "Extraer"}
            </button>
          </div>
        </div>
        {file && (
          <p className="ing-filename muted">
            {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB (máx {api.MAX_MB} MB)
          </p>
        )}
        {error && (
          <p className="nf-error" role="alert">
            {error}
          </p>
        )}
      </section>

      {dataset && (
        <>
          <section className="ing-card ing-resumen">
            <div className="ing-resumen-head">
              <h3>{dataset.source_file}</h3>
              <span className="ing-chip">{tipoEtiqueta(dataset.document_type)}</span>
              <span className="ing-chip">{dataset.campos?.length ?? 0} datos</span>
              {dataset.review_required && (
                <span className="ing-nivel ing-nivel-revisar">Requiere revisión</span>
              )}
            </div>
            {dataset.campos?.length === 0 && (
              <p className="muted">
                No se encontraron datos puntuales. Si es un PDF escaneado, puede que no haya
                texto extraíble.
              </p>
            )}
          </section>

          {grupos.map(([clave, lista]) => (
            <section className="ing-card" key={clave}>
              <h3>
                {ETIQUETA_CAMPO[clave]} ({lista.length})
              </h3>
              <div className="ing-table-wrap">
                <table className="ing-table">
                  <thead>
                    <tr>
                      <th>Valor</th>
                      <th>Confianza</th>
                      <th>Método</th>
                      <th>Origen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lista.map((c, i) => (
                      <tr key={i} className={c.review_required ? "ing-row-rev" : ""}>
                        <td className="ing-valor">
                          {formatValor(c)}
                          {c.currency ? ` ${c.currency}` : ""}
                        </td>
                        <td>
                          <span className={`ing-nivel ${nivelClase(c.confidence)}`}>
                            {nivelEtiqueta(c.confidence)}
                          </span>
                        </td>
                        <td>{metodoEtiqueta(c.extraction_method)}</td>
                        <td className="ing-origen">{evidenciaTexto(c.evidence) || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}

          {dataset.warnings?.length > 0 && (
            <section className="ing-card">
              <h3>Notas</h3>
              <ul className="ing-warn">
                {dataset.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </section>
          )}

          {cola.length > 0 && (
            <section className="ing-card">
              <h3>Cola de revisión ({cola.length})</h3>
              <ul className="ing-cola">
                {cola.map((it, i) => (
                  <li key={i}>
                    <span className={`ing-nivel ${nivelClase(it.confidence)}`}>
                      {nivelEtiqueta(it.confidence)}
                    </span>
                    <b>{it.field || "Dataset completo"}</b>
                    <span className="muted"> — {it.motivo}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <p className="ing-disclaimer">
            Extracción best-effort: todos los datos deben verificarse contra el documento
            original. Lo enumerado por IA (obligaciones, partes, cláusulas) debe ser validado
            por el auditor responsable antes de cualquier decisión.
          </p>
        </>
      )}
    </div>
  );
}
