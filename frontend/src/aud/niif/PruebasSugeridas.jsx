import { useState } from "react";

import { cicloPruebasSugeridas } from "../../api.js";
import { resumen, hayContenido, formatoMonto } from "./pruebasSugeridasLogic.js";

// Panel «Pruebas sugeridas»: puente planificación → pruebas del piloto. De una prueba
// de planificación deriva, por fórmula (backend), la lista ordenada de pruebas del
// piloto a ejecutar (una por herramienta, con sus cuentas, riesgos y saldo). Es
// referencia para el socio; el auditor las corre en «Piloto guiado».
export default function PruebasSugeridas({ pruebaId }) {
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  async function cargar() {
    setCargando(true);
    setError("");
    try {
      setData(await cicloPruebasSugeridas(pruebaId));
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setCargando(false);
    }
  }

  const r = data ? resumen(data) : null;

  return (
    <details className="nf-sug">
      <summary>Pruebas sugeridas (desde esta planificación)</summary>
      <p className="muted">
        Deriva de las cuentas a revisar de esta planificación la lista de pruebas del piloto a
        ejecutar y en qué orden (riesgo primero, luego saldo). Es una guía; corré cada prueba en
        «Piloto guiado».
      </p>

      {!data && (
        <button type="button" className="btn sm primary" onClick={cargar} disabled={cargando}>
          {cargando ? "Calculando…" : "Calcular pruebas sugeridas"}
        </button>
      )}
      {error && <p className="nf-error">{error}</p>}

      {data && (
        <>
          <p className="muted">
            {r.cuentas} cuenta(s) a revisar · {r.nPruebas} prueba(s) sugerida(s) ({r.nConRiesgo} con riesgo)
            {r.nSinPrueba > 0 && ` · ${r.nSinPrueba} área(s) sin prueba del catálogo`}
            {" · "}
            <button type="button" className="link" onClick={cargar} disabled={cargando}>
              {cargando ? "…" : "recalcular"}
            </button>
          </p>

          {!hayContenido(data) ? (
            <p className="muted">La planificación no marcó cuentas a revisar.</p>
          ) : (
            <ol className="nf-sug-lista">
              {data.pruebas.map((p) => (
                <li key={p.prueba_id} className={p.con_riesgo ? "riesgo" : ""}>
                  <div className="nf-sug-cab">
                    {p.con_riesgo && <span className="nf-badge riesgo" title="Tiene riesgo asociado">riesgo</span>}
                    <strong>{p.prueba}</strong>
                    <code className="nf-sug-id">{p.prueba_id}</code>
                    <span className="muted">{p.rubro}</span>
                    <span className="nf-sug-saldo">{formatoMonto(p.saldo)}</span>
                  </div>
                  <ul className="nf-sug-cuentas">
                    {(p.cuentas || []).map((c, i) => (
                      <li key={i}>
                        <span className="muted">{c.codigo}</span> {c.cuenta}
                        {c.riesgos?.length > 0 && <em className="nf-sug-riesgos"> · {c.riesgos.join(", ")}</em>}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          )}

          {data.sin_prueba?.length > 0 && (
            <details className="nf-sug-otras">
              <summary>Áreas a revisar sin prueba del catálogo del piloto ({data.sin_prueba.length})</summary>
              <ul>
                {data.sin_prueba.map((g, i) => (
                  <li key={i}>{g.herramienta} · {g.n_cuentas} cuenta(s)</li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </details>
  );
}
