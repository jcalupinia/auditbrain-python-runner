import { useCallback, useEffect, useState } from "react";

import { niifCobertura, niifEjecutarMotor } from "../../api";
import {
  EJEMPLO_NIIF16,
  RECHAZADO,
  RECIBIDO,
  claveMarca,
  columnas,
  documentosDesdeMarcas,
  parsearJson,
  siguienteMarca,
} from "./estudioLogic";

/*
 * Estudio de la prueba — la parte del sitio que verifica que una ficha
 * funciona antes de marcarla «probada».
 *
 * 1. Requerimiento y cobertura: el auditor marca qué entregaría el cliente y
 *    ve, con la misma regla del sitio, qué queda sin cubrir.
 * 2. Motor: corre la definición de la prueba (la que Claude escribe desde el
 *    código generado) y muestra el cuadro, las filas y los totales.
 */

function Tabla({ filas, titulo }) {
  const cols = columnas(filas);
  if (!filas?.length) return null;
  return (
    <div className="nf-estudio-tabla">
      <h5>{titulo}</h5>
      <div className="nf-estudio-scroll">
        <table>
          <thead>
            <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {filas.map((f, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c} className={/^-?\d+(\.\d+)?$/.test(String(f[c] ?? "")) ? "num" : ""}>
                    {f[c] ?? ""}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function EstudioPrueba({ ficha }) {
  const [marcas, setMarcas] = useState({});
  const [cobertura, setCobertura] = useState(null);
  const [errorCobertura, setErrorCobertura] = useState("");

  const [definicion, setDefinicion] = useState("");
  const [filas, setFilas] = useState("");
  const [resultado, setResultado] = useState(null);
  const [errorMotor, setErrorMotor] = useState("");
  const [corriendo, setCorriendo] = useState(false);

  // Cada cambio de marcas vuelve a preguntar al backend. La regla vive allí;
  // aquí solo se pinta lo que responde.
  const medir = useCallback(async (m) => {
    try {
      setErrorCobertura("");
      setCobertura(await niifCobertura(ficha.id, documentosDesdeMarcas(m)));
    } catch (e) {
      setErrorCobertura(e.message || String(e));
    }
  }, [ficha.id]);

  useEffect(() => { medir({}); }, [medir]);

  function alternar(itemId, componente) {
    const clave = claveMarca(itemId, componente);
    const siguientes = { ...marcas, [clave]: siguienteMarca(marcas[clave]) };
    setMarcas(siguientes);
    medir(siguientes);
  }

  function cargarEjemplo() {
    setDefinicion(JSON.stringify(EJEMPLO_NIIF16.definicion, null, 2));
    setFilas(JSON.stringify(EJEMPLO_NIIF16.filas, null, 2));
    setResultado(null);
    setErrorMotor("");
  }

  async function correr() {
    setErrorMotor("");
    setResultado(null);
    let payload;
    try {
      payload = { definicion: parsearJson(definicion, "Definición"), filas: parsearJson(filas, "Filas") };
    } catch (e) {
      setErrorMotor(e.message);
      return;
    }
    setCorriendo(true);
    try {
      setResultado(await niifEjecutarMotor(payload));
    } catch (e) {
      setErrorMotor(e.message || String(e));
    } finally {
      setCorriendo(false);
    }
  }

  return (
    <div className="nf-estudio">
      <h4>Estudio de la prueba · {ficha.nombre}</h4>

      {/* ---------- 1. Requerimiento y cobertura ---------- */}
      <section>
        <h5>1 · Requerimiento y cobertura</h5>
        <p className="muted">
          Pulse cada entrega para simularla: recibido → rechazado → sin recibir. Un
          componente rechazado no tapa el hueco.
        </p>
        {errorCobertura && <p className="nf-error">{errorCobertura}</p>}
        {cobertura && (
          <>
            <ul className="nf-estudio-items">
              {cobertura.items.map((it, i) => {
                const estado = cobertura.cobertura[i];
                const partes = it.components.length ? it.components : [""];
                return (
                  <li key={it.id}>
                    <div className="nf-estudio-item">
                      <strong>{it.text}</strong>
                      <span className="muted">
                        {" "}· {it.formats.join(", ").toUpperCase()}
                        {it.required ? "" : " · opcional"}
                        {it.group ? ` · alternativa de «${it.group}»` : ""}
                        {" "}· {estado.received} de {estado.expected}
                      </span>
                    </div>
                    <div className="nf-estudio-marcas">
                      {partes.map((comp) => {
                        const m = marcas[claveMarca(it.id, comp)];
                        return (
                          <button
                            key={comp || "unico"}
                            type="button"
                            className={`nf-marca ${m || "vacia"}`}
                            onClick={() => alternar(it.id, comp)}
                            title={m === RECHAZADO ? "Rechazado" : m === RECIBIDO ? "Recibido" : "Sin recibir"}
                          >
                            {comp ? comp.replace("Componente ", "") : "Entrega"}
                          </button>
                        );
                      })}
                    </div>
                  </li>
                );
              })}
            </ul>
            {cobertura.huecos.length === 0 ? (
              <p className="nf-ok">Sin huecos: el requerimiento está cubierto.</p>
            ) : (
              <div className="nf-huecos">
                <strong>Impide avanzar ({cobertura.huecos.length}):</strong>
                <ul>{cobertura.huecos.map((h) => <li key={h}>{h}</li>)}</ul>
              </div>
            )}
          </>
        )}
      </section>

      {/* ---------- 2. Motor de cálculo ---------- */}
      <section>
        <h5>2 · Motor de cálculo</h5>
        <p className="muted">
          Pegue la definición que escribió Claude y los datos de prueba. El motor es el
          mismo del sitio, sin tocar: si aquí da el número esperado, allá también.
        </p>
        <div className="nf-estudio-botones">
          <button type="button" className="link" onClick={cargarEjemplo}>
            Cargar ejemplo NIIF 16
          </button>
        </div>
        <div className="nf-estudio-json">
          <label>
            Definición (JSON)
            <textarea rows={10} value={definicion} onChange={(e) => setDefinicion(e.target.value)} spellCheck={false} />
          </label>
          <label>
            Filas (JSON)
            <textarea rows={10} value={filas} onChange={(e) => setFilas(e.target.value)} spellCheck={false} />
          </label>
        </div>
        <button type="button" className="btn sm primary" disabled={corriendo} onClick={correr}>
          {corriendo ? "Corriendo…" : "Correr motor"}
        </button>
        {errorMotor && <p className="nf-error">{errorMotor}</p>}
        {resultado && (
          <div className="nf-estudio-resultado">
            <p className="muted">Motor {resultado.engine}</p>
            <Tabla titulo="Resultado por fila" filas={resultado.rows} />
            <Tabla titulo={`Cuadro (${resultado.schedule.length} períodos)`} filas={resultado.schedule} />
            <Tabla titulo="Totales" filas={Object.keys(resultado.totals).length ? [resultado.totals] : []} />
          </div>
        )}
      </section>
    </div>
  );
}
