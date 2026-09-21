import { useEffect, useMemo, useState } from "react";

import { herramientaDePrueba, tramosDeTexto } from "./cicloLogic";

/*
 * E8 · Ejecución y análisis de una prueba del encargo.
 *
 * Parámetros → metodología → ejecución → análisis, como en el sitio. Al
 * ejecutar, el navegador corre domain.mjs (copia intacta del sitio) y manda su
 * resultado; el servidor calcula con el motor Python, que es la autoridad, y
 * rechaza la ejecución si no coinciden. Las cédulas se arman aquí con el
 * exportador del sitio a partir de lo que guardó el servidor.
 */

const cargarSitio = () =>
  Promise.all([import("./sitio/tools/domain.mjs"), import("./sitio/tools/exports.mjs"), import("./sitio/tools/explanations.mjs")]);

const mostrar = (v) => (v && typeof v === "object" ? String(v.v ?? v.n ?? "") : String(v ?? ""));

function descargar(nombre, contenido, tipo) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Parametros({ prueba, onAccion, ocupado }) {
  const reg = prueba.registro;
  const esPce = prueba.definicion.id === "pce";
  const [basis, setBasis] = useState(reg.parameters?.basis || "");
  const [tramos, setTramos] = useState(
    (reg.parameters?.buckets?.length ? reg.parameters.buckets : [{ min: 0, max: 30, rate: "" }, { min: 31, max: null, rate: "" }])
      .map((b) => ({ min: String(b.min), max: b.max === null ? "" : String(b.max), rate: String(b.rate) }))
  );
  const set = (i, k, v) => setTramos(tramos.map((t, j) => (j === i ? { ...t, [k]: v } : t)));

  return (
    <>
      <p className="muted">
        Fecha de corte del encargo: <strong>{reg.engagement.cutoff}</strong>. Documente de dónde salen los parámetros
        (precios, tasas, supuestos) y la metodología aplicada.
      </p>
      <label className="nf-ctx-field">
        Sustento de parámetros y metodología
        <textarea rows={3} value={basis} onChange={(e) => setBasis(e.target.value)} />
      </label>
      {esPce && (
        <>
          <h6>Tramos de mora aprobados</h6>
          <div className="nf-estudio-scroll nf-estudio-tabla">
            <table>
              <thead><tr><th>Mora desde (días)</th><th>Hasta (vacío en el último)</th><th>Tasa (0 a 1)</th><th /></tr></thead>
              <tbody>
                {tramos.map((t, i) => (
                  <tr key={i}>
                    <td><input value={t.min} onChange={(e) => set(i, "min", e.target.value)} /></td>
                    <td><input value={t.max} onChange={(e) => set(i, "max", e.target.value)} /></td>
                    <td><input value={t.rate} onChange={(e) => set(i, "rate", e.target.value)} /></td>
                    <td>{tramos.length > 1 && <button type="button" className="link" onClick={() => setTramos(tramos.filter((_, j) => j !== i))}>Quitar</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button type="button" className="link" onClick={() => setTramos([...tramos, { min: "", max: "", rate: "" }])}>Añadir tramo</button>
        </>
      )}
      <div className="nf-estudio-botones">
        <button
          type="button"
          className="btn sm primary"
          disabled={ocupado}
          onClick={() => onAccion("configure", { basis, buckets: esPce ? tramosDeTexto(tramos) : [] })}
        >
          Configurar parámetros
        </button>
      </div>
    </>
  );
}

function Resultados({ run }) {
  return (
    <>
      <p className="nf-ok">
        Motor {run.engine} · {run.rows.length} registros · el cálculo del navegador y el de Python coinciden.
      </p>
      <div className="nf-estudio-scroll nf-estudio-tabla">
        <table>
          <thead><tr><th>Total</th><th>Importe</th></tr></thead>
          <tbody>
            {Object.entries(run.totals).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v}</td></tr>)}
          </tbody>
        </table>
      </div>
      <h6>Excepciones ({run.exceptions.length})</h6>
      {run.exceptions.length ? (
        <ul>
          {run.exceptions.map((e, i) => (
            <li key={i}>Fila {e.row} · {e.id} · {e.code} · {e.message} · {e.amount}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">Sin excepciones.</p>
      )}
    </>
  );
}

function Analisis({ prueba, onAccion, ocupado }) {
  const reg = prueba.registro;
  const [analysis, setAnalysis] = useState(reg.analysis || "");
  const [conclusion, setConclusion] = useState(reg.conclusion || "");
  useEffect(() => {
    setAnalysis(reg.analysis || "");
    setConclusion(reg.conclusion || "");
  }, [prueba.revision]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <p className="muted">
        El texto propuesto es la conclusión preliminar del sitio: reemplácelo con su análisis. La conclusión
        preliminar se exige para enviar a revisión.
      </p>
      <label className="nf-ctx-field">
        Análisis de resultados
        <textarea rows={6} value={analysis} onChange={(e) => setAnalysis(e.target.value)} />
      </label>
      <label className="nf-ctx-field">
        Conclusión preliminar
        <textarea rows={3} value={conclusion} onChange={(e) => setConclusion(e.target.value)} />
      </label>
      <div className="nf-estudio-botones">
        <button type="button" className="btn sm" disabled={ocupado} onClick={() => onAccion("save_analysis", { analysis, conclusion })}>
          Guardar análisis
        </button>
        <button type="button" className="btn sm primary" disabled={ocupado} onClick={() => onAccion("submit", { analysis, conclusion })}>
          Enviar a revisión
        </button>
      </div>
    </>
  );
}

function Cedulas({ prueba }) {
  const [sitio, setSitio] = useState(null);
  const [activa, setActiva] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    cargarSitio().then(setSitio).catch((e) => setError(e.message || String(e)));
  }, []);
  const t = useMemo(() => herramientaDePrueba(prueba), [prueba]);
  const armado = useMemo(() => {
    if (!sitio) return null;
    const [, exp, expl] = sitio;
    try {
      return { hojas: exp.workbookSheets(t), etiquetas: exp.sheetLabels(t.definition), nombres: exp.sheetNames(t.definition), notas: expl.calculationNotes(t) };
    } catch (e) {
      return { error: e.message || String(e) };
    }
  }, [sitio, t]);

  if (error || armado?.error) return <p className="nf-error">{error || armado.error}</p>;
  if (!armado) return <p className="muted">Preparando cédulas…</p>;
  const base = `${(prueba.definicion.name || "prueba").replace(/[^\w-]+/g, "_").slice(0, 60)}_v${prueba.version}_${t.draft ? "BORRADOR" : "APROBADO"}`;
  const hoja = armado.hojas[activa] || [];
  return (
    <>
      <div className="nf-estudio-botones">
        <button type="button" className="btn sm" onClick={() => descargar(`${base}.xlsx`, sitio[1].buildWorkbook(t), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}>
          Descargar Excel
        </button>
        <button type="button" className="btn sm" onClick={() => descargar(`${base}.html`, sitio[1].buildHtml(t), "text/html;charset=utf-8")}>
          Descargar HTML
        </button>
      </div>
      <div className="nf-rec-cedulas">
        {armado.etiquetas.map((label, i) => (
          <button key={label} type="button" className={activa === i ? "selected" : ""} onClick={() => setActiva(i)}>
            <span>{String(i + 1).padStart(2, "0")}</span>
            <strong>{label}</strong>
            <small>{t.draft ? "Borrador" : "Aprobado"}</small>
          </button>
        ))}
      </div>
      <article>
        <h5>{armado.etiquetas[activa]} · {armado.nombres[activa]}</h5>
        <div className="nf-estudio-scroll nf-estudio-tabla">
          <table>
            <tbody>
              {hoja.map((r, i) => (
                <tr key={i}>
                  {r.map((v, j) => (
                    <td key={j}>
                      {mostrar(v)}
                      {v?.f && (
                        <details>
                          <summary>Fórmula auditable</summary>
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
        <p className="nf-nota"><strong>Cómo se prepara y calcula:</strong> {armado.notas[activa]}</p>
      </article>
    </>
  );
}

export function Ejecucion({ prueba, onAccion, ocupado, soloAnalisis = false }) {
  const reg = prueba.registro;
  // En la vista de trabajo (E10) los resultados y las cédulas ya se ven arriba:
  // aquí solo queda el análisis, que abre el cierre del papel.
  if (soloAnalisis)
    return (
      <>
        {prueba.estado === "PRUEBA_EJECUTADA" && (
          <div className="nf-estudio-botones">
            <button type="button" className="btn sm primary" disabled={ocupado} onClick={() => onAccion("analyze")}>
              Generar análisis preliminar
            </button>
          </div>
        )}
        {prueba.estado === "RESULTADOS_ANALIZADOS" && <Analisis prueba={prueba} onAccion={onAccion} ocupado={ocupado} />}
      </>
    );
  const [error, setError] = useState("");
  const [corriendo, setCorriendo] = useState(false);

  async function ejecutar() {
    setError("");
    setCorriendo(true);
    try {
      const [dominio] = await cargarSitio();
      const navegador = dominio.calculate(prueba.definicion, reg.rows, reg.parameters, reg.flows || []);
      await onAccion("execute", { navegador });
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setCorriendo(false);
    }
  }

  return (
    <>
      <h5>Ejecución</h5>
      {prueba.estado === "DOCUMENTACION_VALIDADA" && <Parametros prueba={prueba} onAccion={onAccion} ocupado={ocupado} />}
      {prueba.estado !== "DOCUMENTACION_VALIDADA" && reg.parameters?.basis && (
        <p className="muted">
          Parámetros: corte {reg.parameters.cutoff}
          {reg.parameters.buckets?.length ? ` · ${reg.parameters.buckets.length} tramos de mora` : ""} · {reg.parameters.basis}
        </p>
      )}
      {prueba.estado === "PRUEBA_CONFIGURADA" && (
        <div className="nf-estudio-botones">
          <button type="button" className="btn sm primary" disabled={ocupado} onClick={() => onAccion("approve_methodology")}>
            Aprobar metodología
          </button>
        </div>
      )}
      {prueba.estado === "METODOLOGIA_APROBADA" && (
        <div className="nf-estudio-botones">
          <button type="button" className="btn sm primary" disabled={ocupado || corriendo} onClick={ejecutar}>
            {corriendo ? "Ejecutando…" : "Ejecutar prueba"}
          </button>
        </div>
      )}
      {error && <p role="alert" className="nf-error">{error}</p>}
      {reg.run && <Resultados run={reg.run} />}
      {prueba.estado === "PRUEBA_EJECUTADA" && (
        <div className="nf-estudio-botones">
          <button type="button" className="btn sm primary" disabled={ocupado} onClick={() => onAccion("analyze")}>
            Generar análisis preliminar
          </button>
        </div>
      )}
      {prueba.estado === "RESULTADOS_ANALIZADOS" && (
        <>
          <h5>Análisis de resultados</h5>
          <Analisis prueba={prueba} onAccion={onAccion} ocupado={ocupado} />
        </>
      )}
      {reg.run && (
        <>
          <h5>Cédulas</h5>
          <Cedulas prueba={prueba} />
        </>
      )}
    </>
  );
}
