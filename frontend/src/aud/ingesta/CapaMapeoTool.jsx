import { useMemo, useRef, useState } from "react";
import * as api from "./api.js";
import {
  evidenciaTexto,
  formatValor,
  mapeoInicialDesdePropuesta,
  metodoEtiqueta,
  nivelClase,
  nivelEtiqueta,
  obligatoriosSinCubrir,
  qualityPct,
  resumenCampos,
  TIPOS_MAPEO,
  tipoEtiqueta,
} from "./logic.js";
import "./ingesta.css";

// Capa de Mapeo Universal (Fase A3/B). Acepta un mayor, asiento, balance,
// ventas o compras venga como venga el formato del cliente (otro nombre de
// columna, otro orden, encabezado en cualquier fila) y lo normaliza al esquema
// canónico del motor. Flujo en dos tiempos, SIN estado en el servidor:
//
//   1) «Proponer mapeo»  → el backend perfila y PROPONE (la máquina propone).
//   2) [el auditor revisa/corrige la tabla columna↔campo]
//   3) «Confirmar y normalizar» → reenvía el archivo y aplica el mapeo (M07).
//
// Sin IA: el mapeo es determinista. M22: un obligatorio vacío queda None,
// nunca cero.
export default function CapaMapeoTool() {
  const [tipo, setTipo] = useState("mayor");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(""); // "" | "preparar" | "aplicar"
  const [error, setError] = useState("");
  const [prep, setPrep] = useState(null); // { perfil, esquema, propuesta, cola_revision }
  const [mapeo, setMapeo] = useState({}); // { campo_canonico: indice_columna }
  const [dataset, setDataset] = useState(null); // DatasetNormalizado tras aplicar
  const [cola, setCola] = useState([]);
  const inputRef = useRef(null);

  const columnas = prep?.perfil?.columnas || [];
  const esquema = prep?.esquema || [];
  const sinCubrir = useMemo(() => obligatoriosSinCubrir(esquema, mapeo), [esquema, mapeo]);
  const resumen = dataset ? resumenCampos(dataset.campos) : null;

  const reset = () => {
    setPrep(null);
    setMapeo({});
    setDataset(null);
    setCola([]);
    setError("");
  };

  const onFile = (e) => {
    setFile(e.target.files?.[0] || null);
    reset();
  };

  const proponer = async () => {
    if (!file || busy) return;
    setBusy("preparar");
    setError("");
    setDataset(null);
    setCola([]);
    try {
      const r = await api.prepararMapeo(file, tipo);
      setPrep(r);
      setMapeo(mapeoInicialDesdePropuesta(r?.propuesta));
    } catch (e) {
      setError(e?.message || "No se pudo preparar el mapeo.");
      setPrep(null);
    } finally {
      setBusy("");
    }
  };

  const cambiarCampo = (campo, valor) => {
    setMapeo((m) => {
      const next = { ...m };
      if (valor === "") delete next[campo];
      else next[campo] = Number(valor);
      return next;
    });
  };

  const aplicar = async () => {
    if (!file || busy || sinCubrir.length > 0) return;
    setBusy("aplicar");
    setError("");
    try {
      const r = await api.aplicarMapeo(file, tipo, mapeo);
      setDataset(r?.dataset || null);
      setCola(Array.isArray(r?.cola_revision) ? r.cola_revision : []);
    } catch (e) {
      setError(e?.message || "No se pudo aplicar el mapeo.");
    } finally {
      setBusy("");
    }
  };

  // Para resaltar en la tabla, confianza propuesta por campo canónico.
  const confianzaPropuesta = useMemo(() => {
    const idx = {};
    for (const p of prep?.propuesta?.propuestas || []) idx[p.campo_canonico] = p;
    return idx;
  }, [prep]);

  return (
    <div className="ing-tool">
      <header className="ing-head">
        <h2>Capa de Mapeo Universal</h2>
        <p className="muted">
          Acepta un <b>mayor, asiento de diario, balance, ventas o compras</b> venga como
          venga el formato del cliente (otro nombre de columna, otro orden, encabezado en
          cualquier fila) y lo normaliza al esquema canónico del motor. La máquina{" "}
          <b>propone</b> el mapeo; el auditor lo <b>confirma</b> antes de normalizar.
        </p>
        <p className="ing-nota">
          Determinista, sin IA. Un campo obligatorio con celda vacía queda <b>vacío</b> y a
          revisión — <b>nunca se asume cero</b> (M22).
        </p>
      </header>

      <section className="ing-form">
        <div className="ing-row">
          <label className="ing-file">
            <span>Tabla contable</span>
            <input ref={inputRef} type="file" onChange={onFile} accept=".xlsx,.xls,.xlsm,.csv,.txt" />
          </label>
          <label className="ing-tipo">
            <span>Tipo de tabla</span>
            <select
              value={tipo}
              onChange={(e) => {
                setTipo(e.target.value);
                reset();
              }}
            >
              {TIPOS_MAPEO.map((t) => (
                <option key={t} value={t}>
                  {tipoEtiqueta(t)}
                </option>
              ))}
            </select>
          </label>
          <div className="ing-actions">
            <button type="button" className="btn" disabled={!file || !!busy} onClick={proponer}>
              {busy === "preparar" ? "Proponiendo…" : "Proponer mapeo"}
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

      {prep && (
        <section className="ing-card">
          <div className="ing-resumen-head">
            <h3>Mapeo propuesto</h3>
            <span className="ing-chip">{tipoEtiqueta(tipo)}</span>
            <span className="ing-chip">
              {prep.perfil?.fila_encabezado == null
                ? "Sin encabezado claro"
                : `Encabezado en fila ${prep.perfil.fila_encabezado + 1}`}
            </span>
            <span className="ing-chip">{prep.perfil?.n_filas ?? 0} filas de datos</span>
            {prep.propuesta?.review_required && (
              <span className="ing-nivel ing-nivel-revisar">Revisar antes de confirmar</span>
            )}
          </div>
          <p className="muted">
            Revise cada campo canónico y confirme (o corrija) la columna de origen. Los
            resaltados exigen su atención.
          </p>

          <div className="ing-table-wrap">
            <table className="ing-table ing-map">
              <thead>
                <tr>
                  <th>Campo canónico</th>
                  <th>Columna de origen</th>
                  <th>Confianza propuesta</th>
                  <th>Muestra</th>
                </tr>
              </thead>
              <tbody>
                {esquema.map((campo) => {
                  const p = confianzaPropuesta[campo.nombre];
                  const idxSel = mapeo[campo.nombre];
                  const colSel =
                    idxSel != null ? columnas.find((c) => c.indice === idxSel) : null;
                  const faltaOblig = campo.obligatorio && idxSel == null;
                  return (
                    <tr key={campo.nombre} className={faltaOblig ? "ing-row-rev" : ""}>
                      <td>
                        {campo.nombre}
                        {campo.obligatorio && <span className="ing-oblig"> *</span>}
                        <span className="muted"> · {campo.tipo}</span>
                      </td>
                      <td>
                        <select
                          value={idxSel != null ? String(idxSel) : ""}
                          onChange={(e) => cambiarCampo(campo.nombre, e.target.value)}
                          aria-label={`Columna para ${campo.nombre}`}
                        >
                          <option value="">— sin mapear —</option>
                          {columnas.map((c) => (
                            <option key={c.indice} value={String(c.indice)}>
                              {c.nombre_crudo || `col ${c.indice + 1}`} ({c.tipo_inferido})
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        {p ? (
                          <span className={`ing-nivel ${nivelClase(p.confianza)}`}>
                            {nivelEtiqueta(p.confianza)}
                          </span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td className="ing-origen">
                        {colSel && colSel.muestra?.length
                          ? colSel.muestra.slice(0, 3).join(" · ")
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {sinCubrir.length > 0 && (
            <p className="nf-error" role="alert">
              Faltan columnas para campos obligatorios: <b>{sinCubrir.join(", ")}</b>. Asigne una
              columna a cada uno para poder normalizar.
            </p>
          )}

          <div className="ing-actions">
            <button
              type="button"
              className="btn"
              disabled={!!busy || sinCubrir.length > 0}
              onClick={aplicar}
            >
              {busy === "aplicar" ? "Normalizando…" : "Confirmar y normalizar"}
            </button>
          </div>
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
            </div>
          </section>

          {Array.isArray(dataset.campos) && dataset.campos.length > 0 && (
            <section className="ing-card">
              <h3>Campos normalizados (primeras filas)</h3>
              <div className="ing-table-wrap">
                <table className="ing-table">
                  <thead>
                    <tr>
                      <th>Campo</th>
                      <th>Valor</th>
                      <th>Tipo</th>
                      <th>Confianza</th>
                      <th>Origen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataset.campos.slice(0, 60).map((c, i) => (
                      <tr key={`${c.field}-${i}`} className={c.review_required ? "ing-row-rev" : ""}>
                        <td>{c.field}</td>
                        <td className="ing-valor">{formatValor(c)}</td>
                        <td>{c.data_type}</td>
                        <td>
                          <span className={`ing-nivel ${nivelClase(c.confidence)}`}>
                            {nivelEtiqueta(c.confidence)}
                          </span>
                        </td>
                        <td className="ing-origen">{evidenciaTexto(c.evidence) || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {dataset.campos.length > 60 && (
                <p className="muted">… {dataset.campos.length - 60} campos más.</p>
              )}
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

          {dataset.sello?.sha256 && (
            <p className="ing-sello muted">
              Sello de trazabilidad SHA-256: <code>{dataset.sello.sha256.slice(0, 16)}…</code> ·
              contrato {dataset.sello.contrato_version}
            </p>
          )}

          <p className="ing-disclaimer">
            El mapeo transporta datos con su confianza; no emite conclusiones de auditoría ni
            NIIF. Todo dato con confianza baja o marcado «Revisar» debe ser validado por el
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
