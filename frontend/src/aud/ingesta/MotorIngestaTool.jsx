import { useEffect, useRef, useState } from "react";
import * as api from "./api.js";
import {
  evidenciaTexto,
  formatValor,
  metodoEtiqueta,
  nivelClase,
  nivelEtiqueta,
  qualityPct,
  resumenCampos,
  tipoEtiqueta,
} from "./logic.js";
import "./ingesta.css";

// Vista del Motor de Ingesta y Normalización. Sube un documento y lo clasifica
// (barato) o lo ingiere (clasifica → extrae determinista → normaliza → confía),
// mostrando el dataset normalizado con su trazabilidad al origen, el método de
// extracción por campo, el nivel de confianza y la cola de revisión.
//
// Principio rector (igual que el backend): determinístico primero, la IA es el
// último recurso — y NO se dispara en «Ingerir». La resolución semántica por IA
// es un paso aparte y opcional del motor.
export default function MotorIngestaTool() {
  const [tipos, setTipos] = useState([]); // tipos del /tipos
  const [tipo, setTipo] = useState(""); // tipo_declarado (vacío = automático)
  const [file, setFile] = useState(null);
  const [ocr, setOcr] = useState(true);
  const [busy, setBusy] = useState(""); // "" | "clasificar" | "ingerir"
  const [error, setError] = useState("");
  const [clasif, setClasif] = useState(null); // ResultadoClasificacion
  const [dataset, setDataset] = useState(null); // DatasetNormalizado
  const [cola, setCola] = useState([]); // ItemRevision[]
  const inputRef = useRef(null);

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

  const limpiarResultados = () => {
    setClasif(null);
    setDataset(null);
    setCola([]);
    setError("");
  };

  const onFile = (e) => {
    const f = e.target.files?.[0] || null;
    setFile(f);
    limpiarResultados();
  };

  const correr = async (accion) => {
    if (!file || busy) return;
    setBusy(accion);
    setError("");
    try {
      if (accion === "clasificar") {
        const r = await api.clasificar(file, tipo || undefined);
        setClasif(r);
        setDataset(null);
        setCola([]);
      } else {
        const r = await api.ingerir(file, tipo || undefined, { ocr });
        setDataset(r?.dataset || null);
        setCola(Array.isArray(r?.cola_revision) ? r.cola_revision : []);
        setClasif(null);
      }
    } catch (e) {
      setError(e?.message || "No se pudo completar la operación.");
    } finally {
      setBusy("");
    }
  };

  const resumen = dataset ? resumenCampos(dataset.campos) : null;

  return (
    <div className="ing-tool">
      <header className="ing-head">
        <h2>Motor de Ingesta y Normalización</h2>
        <p className="muted">
          Capa transversal: ingiere, normaliza y valida un documento <b>una sola vez</b> y
          entrega un dataset con trazabilidad al origen (archivo · página · fila · celda),
          método de extracción y nivel de confianza por campo. Lo consumen después las
          pruebas de auditoría, NIIF y tributarias.
        </p>
        <p className="ing-nota">
          Determinístico primero: «Ingerir» <b>no</b> usa IA. El OCR solo se intenta si el PDF
          viene escaneado (sin texto). La resolución semántica por IA es un paso aparte y
          opcional.
        </p>
      </header>

      <section className="ing-form">
        <div className="ing-row">
          <label className="ing-file">
            <span>Documento</span>
            <input
              ref={inputRef}
              type="file"
              onChange={onFile}
              accept=".pdf,.xlsx,.xls,.xml,.csv,.txt"
            />
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
        </div>
        <div className="ing-row ing-controls">
          <label className="ing-check">
            <input type="checkbox" checked={ocr} onChange={(e) => setOcr(e.target.checked)} />
            <span>Recuperar por OCR si el PDF viene escaneado</span>
          </label>
          <div className="ing-actions">
            <button
              type="button"
              className="btn secondary"
              disabled={!file || !!busy}
              onClick={() => correr("clasificar")}
            >
              {busy === "clasificar" ? "Clasificando…" : "Clasificar"}
            </button>
            <button
              type="button"
              className="btn"
              disabled={!file || !!busy}
              onClick={() => correr("ingerir")}
            >
              {busy === "ingerir" ? "Ingiriendo…" : "Ingerir"}
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

      {clasif && (
        <section className="ing-card ing-clasif">
          <h3>Clasificación</h3>
          <div className="ing-chips">
            <span className="ing-chip">{tipoEtiqueta(clasif.tipo)}</span>
            <span className={`ing-nivel ${nivelClase(clasif.confidence)}`}>
              Confianza {nivelEtiqueta(clasif.confidence)}
            </span>
            <span className="ing-chip">{metodoEtiqueta(clasif.metodo)}</span>
            {typeof clasif.confidence_score === "number" && (
              <span className="ing-chip">{Math.round(clasif.confidence_score * 100)}%</span>
            )}
          </div>
          {Array.isArray(clasif.razones) && clasif.razones.length > 0 && (
            <ul className="ing-razones">
              {clasif.razones.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {dataset && (
        <>
          <section className="ing-card ing-resumen">
            <div className="ing-resumen-head">
              <h3>{dataset.source_file}</h3>
              <span className="ing-chip">{tipoEtiqueta(dataset.document_type)}</span>
              {dataset.review_required && (
                <span className="ing-nivel ing-nivel-revisar">Requiere revisión</span>
              )}
            </div>
            <div className="ing-metricas">
              <Metrica
                label="Calidad"
                valor={`${qualityPct(dataset.quality_score)}%`}
                barra={qualityPct(dataset.quality_score)}
              />
              <Metrica label="Filas" valor={dataset.row_count ?? 0} />
              <Metrica label="Campos" valor={resumen.total} />
              <Metrica label="Dudosos" valor={resumen.dudosos} alerta={resumen.dudosos > 0} />
              <Metrica
                label="Método"
                valor={metodoEtiqueta(dataset.extraction_method)}
              />
            </div>
            {resumen.total > 0 && (
              <div className="ing-chips ing-dist">
                <span className={`ing-nivel ${nivelClase("HIGH")}`}>
                  Alta {resumen.por.HIGH}
                </span>
                <span className={`ing-nivel ${nivelClase("MEDIUM")}`}>
                  Media {resumen.por.MEDIUM}
                </span>
                <span className={`ing-nivel ${nivelClase("LOW")}`}>
                  Baja {resumen.por.LOW}
                </span>
                <span className={`ing-nivel ${nivelClase("REVIEW_REQUIRED")}`}>
                  Revisar {resumen.por.REVIEW_REQUIRED}
                </span>
              </div>
            )}
          </section>

          {(dataset.schema_detected?.length > 0 ||
            dataset.schema_normalized?.length > 0) && (
            <section className="ing-card">
              <h3>Esquema</h3>
              <div className="ing-esquema">
                <div>
                  <h4>Detectado</h4>
                  <p className="ing-cols">
                    {(dataset.schema_detected || []).join(" · ") || "—"}
                  </p>
                </div>
                <div>
                  <h4>Normalizado</h4>
                  <p className="ing-cols">
                    {(dataset.schema_normalized || []).join(" · ") || "—"}
                  </p>
                </div>
              </div>
              {dataset.mapping && Object.keys(dataset.mapping).length > 0 && (
                <table className="ing-table ing-map">
                  <thead>
                    <tr>
                      <th>Columna de origen</th>
                      <th>Campo normalizado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(dataset.mapping).map(([de, a]) => (
                      <tr key={de}>
                        <td>{de}</td>
                        <td>{a}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          )}

          {Array.isArray(dataset.campos) && dataset.campos.length > 0 && (
            <section className="ing-card">
              <h3>Campos extraídos</h3>
              <div className="ing-table-wrap">
                <table className="ing-table">
                  <thead>
                    <tr>
                      <th>Campo</th>
                      <th>Valor</th>
                      <th>Tipo</th>
                      <th>Confianza</th>
                      <th>Método</th>
                      <th>Origen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataset.campos.map((c, i) => (
                      <tr key={`${c.field}-${i}`} className={c.review_required ? "ing-row-rev" : ""}>
                        <td>{c.field}</td>
                        <td className="ing-valor">{formatValor(c)}</td>
                        <td>{c.data_type}</td>
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
          )}

          {Array.isArray(dataset.validation_results) &&
            dataset.validation_results.length > 0 && (
              <section className="ing-card">
                <h3>Validaciones</h3>
                <ul className="ing-valid">
                  {dataset.validation_results.map((v, i) => (
                    <li key={i} className={v.ok ? "ok" : "fail"}>
                      <span className="ing-valid-mark">{v.ok ? "✓" : "✗"}</span>
                      <b>{v.regla}</b>
                      {v.detalle ? <span className="muted"> — {v.detalle}</span> : null}
                    </li>
                  ))}
                </ul>
              </section>
            )}

          {(dataset.exceptions?.length > 0 || dataset.warnings?.length > 0) && (
            <section className="ing-card">
              <h3>Excepciones y advertencias</h3>
              {dataset.exceptions?.length > 0 && (
                <ul className="ing-exc">
                  {dataset.exceptions.map((x, i) => (
                    <li key={`e${i}`}>{x}</li>
                  ))}
                </ul>
              )}
              {dataset.warnings?.length > 0 && (
                <ul className="ing-warn">
                  {dataset.warnings.map((w, i) => (
                    <li key={`w${i}`}>{w}</li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {cola.length > 0 && (
            <section className="ing-card">
              <h3>Cola de revisión ({cola.length})</h3>
              <p className="muted">
                Campos o datasets cuya confianza exige que el auditor los valide antes de
                usarlos.
              </p>
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

          {dataset.sello?.sha256 && (
            <p className="ing-sello muted">
              Sello de trazabilidad SHA-256:{" "}
              <code>{dataset.sello.sha256.slice(0, 16)}…</code> · contrato{" "}
              {dataset.sello.contrato_version}
            </p>
          )}

          <p className="ing-disclaimer">
            La extracción transporta datos con su confianza; no emite conclusiones de auditoría
            ni NIIF. Todo dato con confianza baja o marcado «Revisar» debe ser validado por el
            auditor responsable antes de cualquier decisión.
          </p>
        </>
      )}
    </div>
  );
}

function Metrica({ label, valor, barra, alerta }) {
  return (
    <div className={`ing-metrica ${alerta ? "alerta" : ""}`}>
      <span className="ing-metrica-l">{label}</span>
      <span className="ing-metrica-v">{valor}</span>
      {typeof barra === "number" && (
        <span className="ing-barra" aria-hidden="true">
          <span className="ing-barra-fill" style={{ width: `${barra}%` }} />
        </span>
      )}
    </div>
  );
}
