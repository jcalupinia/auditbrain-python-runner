import { useEffect, useState } from "react";
import * as api from "./api.js";
import {
  evidenciaTexto,
  formatValor,
  nivelClase,
  nivelEtiqueta,
  tipoEtiqueta,
} from "./logic.js";
import "./ingesta.css";

// Resolución semántica por IA (Fase 6) como herramienta del Command Center.
// Ingiere un documento por el Motor de Ingesta y luego pide que la IA
// desambigüe SOLO los campos de TEXTO que quedaron en la cola de revisión.
// Último recurso de la escalera determinístico-primero: el LLM no calcula
// cifras ni fechas, tope de confianza MEDIUM, disclaimer y degradación
// graciosa (si no hay proveedor, no rompe). No toca ninguna herramienta
// existente: consume el motor.
export default function ResolutorSemanticoTool() {
  const [tipos, setTipos] = useState([]);
  const [tipo, setTipo] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [res, setRes] = useState(null); // {dataset, cola_revision, resolubles, resueltos}

  useEffect(() => {
    let vivo = true;
    api
      .tiposDocumento()
      .then((r) => vivo && setTipos(Array.isArray(r?.tipos) ? r.tipos : []))
      .catch(() => vivo && setTipos([]));
    return () => {
      vivo = false;
    };
  }, []);

  const onFile = (e) => {
    setFile(e.target.files?.[0] || null);
    setRes(null);
    setError("");
  };

  const resolver = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError("");
    try {
      setRes(await api.resolver(file, tipo || undefined));
    } catch (e) {
      setError(e?.message || "No se pudo completar la operación.");
    } finally {
      setBusy(false);
    }
  };

  const ds = res?.dataset;
  const campos = ds?.campos || [];
  const porIa = campos.filter((c) => c.extraction_method === "ia");

  return (
    <div className="ing-tool">
      <header className="ing-head">
        <h2>Resolución semántica por IA</h2>
        <p className="muted">
          Último paso de la escalera determinístico-primero. Ingiere un documento y pide a la
          IA que <b>desambigüe solo los campos de texto</b> que el motor dejó en la cola de
          revisión (una sigla, un concepto ambiguo). El resto ya lo resolvieron los parsers.
        </p>
        <p className="ing-nota">
          El LLM <b>no calcula</b>: nunca toca cifras ni fechas. Tope de confianza «media»
          (nunca «alta» automática) y todo dato resuelto queda marcado para validación del
          auditor. Si no hay proveedor de IA configurado, no se resuelve nada y se avisa (no
          rompe).
        </p>
      </header>

      <section className="ing-form">
        <div className="ing-row">
          <label className="ing-file">
            <span>Documento</span>
            <input type="file" onChange={onFile} accept=".pdf,.xlsx,.xls,.xml,.csv,.txt" />
          </label>
          <label className="ing-tipo">
            <span>Tipo declarado (opcional)</span>
            <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="">Detección automática</option>
              {tipos.map((t) => (
                <option key={t} value={t}>
                  {tipoEtiqueta(t)}
                </option>
              ))}
            </select>
          </label>
          <div className="ing-actions">
            <button type="button" className="btn" disabled={!file || busy} onClick={resolver}>
              {busy ? "Resolviendo con IA…" : "Ingerir y resolver con IA"}
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

      {res && (
        <>
          <section className="ing-card ing-resumen">
            <div className="ing-resumen-head">
              <h3>{ds.source_file}</h3>
              <span className="ing-chip">{tipoEtiqueta(ds.document_type)}</span>
              <span className="ing-chip">{res.resolubles} dudoso(s) de texto</span>
              <span className={`ing-nivel ${porIa.length ? "ing-nivel-media" : "ing-nivel-revisar"}`}>
                {res.resueltos} resuelto(s) por IA
              </span>
            </div>
            {res.resolubles === 0 && (
              <p className="muted">
                No había campos de texto dudosos para resolver (los numéricos no los toca la
                IA). El documento ya estaba resuelto de forma determinista.
              </p>
            )}
          </section>

          {porIa.length > 0 && (
            <section className="ing-card">
              <h3>Resueltos por IA ({porIa.length})</h3>
              <div className="ing-table-wrap">
                <table className="ing-table">
                  <thead>
                    <tr>
                      <th>Campo</th>
                      <th>Valor (IA)</th>
                      <th>Confianza</th>
                      <th>Origen / nota</th>
                    </tr>
                  </thead>
                  <tbody>
                    {porIa.map((c, i) => (
                      <tr key={i} className={c.review_required ? "ing-row-rev" : ""}>
                        <td>{c.field}</td>
                        <td className="ing-valor">{formatValor(c)}</td>
                        <td>
                          <span className={`ing-nivel ${nivelClase(c.confidence)}`}>
                            {nivelEtiqueta(c.confidence)}
                          </span>
                        </td>
                        <td className="ing-origen">
                          {evidenciaTexto(c.evidence) || "—"}
                          {c.warnings?.length > 0 && (
                            <div className="muted">{c.warnings[c.warnings.length - 1]}</div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {res.cola_revision?.length > 0 && (
            <section className="ing-card">
              <h3>Cola de revisión ({res.cola_revision.length})</h3>
              <p className="muted">
                Lo que la IA no pudo resolver con confianza sigue aquí para el auditor.
              </p>
              <ul className="ing-cola">
                {res.cola_revision.map((it, i) => (
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
            Dato desambiguado por IA. Debe ser validado por el auditor responsable antes de
            cualquier decisión. La IA no produce cifras ni fechas.
          </p>
        </>
      )}
    </div>
  );
}
