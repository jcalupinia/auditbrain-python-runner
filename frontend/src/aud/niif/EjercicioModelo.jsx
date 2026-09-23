import { useEffect, useState } from "react";

import * as api from "../../api";
import { ejemploDe, formatosTexto } from "./ejemplosRequerimientos";

/*
 * Ejercicio modelo (SOLO LECTURA) de una prueba NIIF.
 *
 * Muestra, en un panel modal, TODO el recorrido de la prueba con datos de
 * ejemplo, paso por paso (1 Datos del encargo → 9 Descarga). El cálculo lo hace
 * un endpoint de solo lectura que corre el procesador sobre sus ejemplos
 * (manifiesto para pérdidas incurridas; EJEMPLO/ESCENARIOS para las demás). No
 * crea ni modifica encargos ni pruebas y no consume el estado del ciclo.
 *
 * Todo el panel va marcado «EJERCICIO MODELO · datos ficticios».
 */

const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const TIPOS = {
  xlsx: XLSX,
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  html: "text/html;charset=utf-8",
};
const ETIQUETA_FMT = { xlsx: "Excel", docx: "Word", pptx: "PowerPoint", html: "HTML" };
const mostrar = (v) => (v && typeof v === "object" ? String(v.v ?? v.n ?? "") : String(v ?? ""));

function descargar(nombre, contenido, tipo) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export default function EjercicioModelo({ prueba, onCerrar }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [paso, setPaso] = useState(0);
  const [cedula, setCedula] = useState(0);
  const [bajando, setBajando] = useState("");
  const processor = prueba.definicion?.processor;
  const base = import.meta.env.BASE_URL || "/";

  useEffect(() => {
    let vivo = true;
    api.cicloEjercicioModelo(prueba.id)
      .then((r) => vivo && setData(r))
      .catch((e) => vivo && setError(e.message || String(e)));
    return () => { vivo = false; };
  }, [prueba.id]);

  async function bajar(formato) {
    setBajando(formato);
    setError("");
    try {
      const bytes = await api.cicloEjercicioModeloLibro(prueba.id, formato);
      descargar(`Ejercicio_modelo_${processor || "prueba"}.${formato}`, bytes, TIPOS[formato]);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setBajando("");
    }
  }

  const pasos = data?.pasos || [];
  const actual = pasos[paso];

  return (
    <div className="nf-em-overlay" role="dialog" aria-label="Ejercicio modelo" aria-modal="true">
      <div className="nf-em-panel">
        <header className="nf-em-head">
          <div>
            <span className="nf-em-marca">EJERCICIO MODELO · datos ficticios</span>
            <h3>{data?.herramienta?.nombre || prueba.definicion?.name || "Ejercicio modelo"}</h3>
            <p className="muted">
              Recorrido completo con datos de ejemplo. No crea ni modifica encargos ni pruebas reales.
            </p>
          </div>
          <button type="button" className="pc-chip" onClick={onCerrar} aria-label="Cerrar">✕</button>
        </header>

        {error && <p role="alert" className="nf-error">{error}</p>}
        {!data && !error && <p className="muted">Preparando el ejercicio modelo…</p>}
        {data && !data.disponible && (
          <p className="nf-nota"><strong>Ejercicio modelo pendiente.</strong> Esta herramienta aún no trae datos de ejemplo.</p>
        )}

        {data?.disponible && actual && (
          <>
            <ol className="nf-em-pasos">
              {pasos.map((p, i) => (
                <li key={p.n}>
                  <button type="button" className={i === paso ? "on" : ""} onClick={() => setPaso(i)}>
                    <span>{p.n}</span> {p.titulo}
                  </button>
                </li>
              ))}
            </ol>

            <section className="nf-em-cuerpo">
              <div className="nf-em-norma">
                <span className="nf-em-badge">{actual.norma}</span>
              </div>
              <h4>{actual.n}. {actual.titulo}</h4>
              <p className="nf-em-expl">{actual.explicacion}</p>

              {actual.n === 1 && actual.encargo && (
                <ul className="nf-em-datos">
                  <li><strong>Cliente:</strong> {actual.encargo.client} · {actual.encargo.ruc}</li>
                  <li><strong>Ejercicio:</strong> {actual.encargo.year} · corte {actual.encargo.cutoff}</li>
                  <li><strong>Marco:</strong> {actual.encargo.framework}</li>
                  <li><strong>Firma:</strong> {actual.encargo.firm}</li>
                </ul>
              )}

              {actual.n === 2 && actual.herramienta && (
                <ul className="nf-em-datos">
                  <li><strong>Rubro:</strong> {actual.herramienta.rubro}</li>
                  <li><strong>Marcos:</strong> {(actual.herramienta.marcos || []).join(", ")}</li>
                  <li>{actual.herramienta.resumen}</li>
                </ul>
              )}

              {actual.n === 3 && (
                <>
                  <p><strong>Base técnica:</strong> {actual.base_tecnica?.norma || "—"}</p>
                  <ul className="nf-em-datos">
                    {(actual.base_tecnica?.nia || []).map((s, i) => (
                      <li key={i}>{s.document} · {s.section} — {s.requirement}</li>
                    ))}
                  </ul>
                  {(actual.tratamiento_tributario || []).length > 0 && (
                    <>
                      <p><strong>Tratamiento tributario:</strong></p>
                      <ul className="nf-em-datos">
                        {actual.tratamiento_tributario.map((t, i) => <li key={i}>{t}</li>)}
                      </ul>
                    </>
                  )}
                  <details>
                    <summary>Programa de trabajo ({(actual.programa || []).length})</summary>
                    <ul className="nf-em-datos">
                      {(actual.programa || []).map((x, i) => (
                        <li key={i}><strong>{x.code}</strong> · {x.objective} <em>({x.assertion})</em></li>
                      ))}
                    </ul>
                  </details>
                </>
              )}

              {actual.n === 4 && (
                <ul className="nf-em-req">
                  {(actual.requerimientos || []).map((r) => {
                    const ej = ejemploDe(processor, r, undefined, base);
                    return (
                      <li key={r.id}>
                        <strong>{r.id}</strong> · {r.document}
                        <span className="nf-em-formatos">
                          {formatosTexto(r)}{r.required === false ? " · opcional" : ""}
                          {ej?.tipo === "ejemplo" && (
                            <a className="link" href={ej.url} download={ej.archivo} title="Formato válido con datos de ejemplo (ficticios)"> ↓ Ejemplo</a>
                          )}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}

              {actual.n === 5 && (
                <ul className="nf-em-datos">
                  {(actual.documentacion || []).map((x) => (
                    <li key={x.dataset}><strong>{x.dataset}</strong>: {x.registros} registros «cargados» (ejemplo)</li>
                  ))}
                </ul>
              )}

              {actual.n === 6 && actual.resultado && (
                <>
                  <div className="nf-em-metricas">
                    {Object.entries(actual.resultado.etiquetas || {}).map(([k, etq]) => (
                      <div key={k}><small>{etq}</small><strong>{mostrar(actual.resultado.totales?.[k])}</strong></div>
                    ))}
                  </div>
                  {(actual.problemas || []).length > 0 && (
                    <details open>
                      <summary>Problemas encontrados ({actual.problemas.length})</summary>
                      <ul className="nf-em-datos">
                        {actual.problemas.map((p, i) => (
                          <li key={i}><strong>{p.code}</strong> · {p.message} {p.amount ? `(${p.amount})` : ""}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                  <div className="nf-em-cedtabs">
                    {(actual.cedulas || []).map((c, i) => (
                      <button key={c.name} type="button" className={cedula === i ? "on" : ""} onClick={() => setCedula(i)}>
                        <span>{String(i + 1).padStart(2, "0")}</span> {c.label}
                      </button>
                    ))}
                  </div>
                  {actual.cedulas?.[cedula] && (
                    <div className="nf-em-tabla">
                      <table>
                        <tbody>
                          {(actual.cedulas[cedula].rows || []).slice(0, 60).map((r, i) => (
                            <tr key={i}>
                              {(Array.isArray(r) ? r : [r]).map((v, j) => (
                                <td key={j}>
                                  {mostrar(v)}
                                  {v?.f && (
                                    <details>
                                      <summary>fórmula</summary>
                                      <code>={v.f}</code>
                                    </details>
                                  )}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}

              {actual.n === 7 && actual.analisis && (
                <ul className="nf-em-datos">
                  <li><strong>{actual.analisis.etiqueta}:</strong> {mostrar(actual.analisis.valor)}</li>
                  <li>{actual.analisis.problemas} problema(s) para evaluar antes de concluir.</li>
                </ul>
              )}

              {actual.n === 8 && <p className="nf-em-expl">{actual.conclusion}</p>}

              {actual.n === 9 && (
                <div className="nf-em-descargas">
                  {(actual.formatos || []).map((f) => (
                    <button key={f} type="button" className="pc-chip accent" disabled={!!bajando} onClick={() => bajar(f)}>
                      {bajando === f ? "Bajando…" : `↓ ${ETIQUETA_FMT[f] || f}`}
                    </button>
                  ))}
                  <p className="muted">El PDF se obtiene con «Guardar como PDF» del navegador desde el HTML.</p>
                </div>
              )}
            </section>

            <footer className="nf-em-nav">
              <button type="button" className="pc-chip" disabled={paso === 0} onClick={() => setPaso(paso - 1)}>← Anterior</button>
              <span className="muted">Paso {actual.n} de {pasos.length}</span>
              <button type="button" className="pc-chip" disabled={paso === pasos.length - 1} onClick={() => setPaso(paso + 1)}>Siguiente →</button>
            </footer>
          </>
        )}
      </div>
    </div>
  );
}
