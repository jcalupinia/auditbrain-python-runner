import { useCallback, useEffect, useState } from "react";

import { niifCobertura, niifEjecutarMotor, niifGuardarDefinicion } from "../../api";
import { herramientaDeEstudio, motivoDiscrepancia } from "./contraste";
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
 * 3. Cédulas: el Excel y el HTML autónomo, armados con el exportador del
 *    sitio sin tocar (carpeta sitio/).
 *
 * El cálculo corre dos veces, como en el sitio: domain.mjs (la autoridad) en
 * el navegador y el motor Python en el backend. Si difieren, no hay cédulas.
 */

// El exportador pesa ~200 KB (el logo va dentro): se carga al usarlo, no con
// el portal.
const cargarSitio = () =>
  Promise.all([import("./sitio/tools/domain.mjs"), import("./sitio/tools/exports.mjs")]);

function descargar(nombre, contenido, tipo) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

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

export default function EstudioPrueba({ ficha, onDefinicionGuardada }) {
  const [marcas, setMarcas] = useState({});
  const [cobertura, setCobertura] = useState(null);
  const [errorCobertura, setErrorCobertura] = useState("");

  const [definicion, setDefinicion] = useState("");
  const [filas, setFilas] = useState("");
  const [resultado, setResultado] = useState(null);
  const [errorMotor, setErrorMotor] = useState("");
  const [corriendo, setCorriendo] = useState(false);
  // Lo que se corrió y dio igual en los dos motores: base de las cédulas.
  const [corrida, setCorrida] = useState(null);
  const [guardada, setGuardada] = useState("");

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

  // La definición que corrió y coincidió en los dos motores queda en la ficha:
  // es lo que permite aplicarla a un cliente en «Pruebas del encargo». El
  // servidor la vuelve a ejecutar antes de guardarla.
  async function guardarDefinicion() {
    setGuardada("");
    try {
      await niifGuardarDefinicion(ficha.id, corrida.definicion, corrida.filas);
      setGuardada("Definición guardada en la ficha. Ya se puede aplicar a un cliente cuando la ficha esté probada.");
      onDefinicionGuardada?.();
    } catch (e) {
      setErrorMotor(e.message || String(e));
    }
  }

  async function bajarCedulas(formato) {
    try {
      const [, exp] = await cargarSitio();
      const t = herramientaDeEstudio({ ficha, ...corrida });
      const base = `${(ficha.nombre || "prueba").replace(/[^\w-]+/g, "_").slice(0, 60)}_BORRADOR`;
      if (formato === "excel")
        descargar(`${base}.xlsx`, exp.buildWorkbook(t),
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
      else descargar(`${base}.html`, exp.buildHtml(t), "text/html;charset=utf-8");
    } catch (e) {
      setErrorMotor(e.message || String(e));
    }
  }

  function cargarEjemplo() {
    setDefinicion(JSON.stringify(EJEMPLO_NIIF16.definicion, null, 2));
    setFilas(JSON.stringify(EJEMPLO_NIIF16.filas, null, 2));
    setResultado(null);
    setCorrida(null);
    setErrorMotor("");
  }

  async function correr() {
    setErrorMotor("");
    setResultado(null);
    setCorrida(null);
    let payload;
    try {
      payload = { definicion: parsearJson(definicion, "Definición"), filas: parsearJson(filas, "Filas") };
    } catch (e) {
      setErrorMotor(e.message);
      return;
    }
    setCorriendo(true);
    try {
      const [python, [dominio]] = await Promise.all([niifEjecutarMotor(payload), cargarSitio()]);
      const run = dominio.calculate(payload.definicion, payload.filas, {}, []);
      const motivo = motivoDiscrepancia(run, python);
      if (motivo) {
        setErrorMotor(
          `El motor Python no coincide con el verificador (${motivo}). No se generan cédulas.`
        );
        return;
      }
      setResultado(run);
      setCorrida({ ...payload, run });
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
            <p className="nf-ok">
              Motor {resultado.engine} · el cálculo del navegador y el de Python coinciden.
            </p>
            {resultado.exceptions?.length > 0 && (
              <div className="nf-huecos">
                <strong>Excepciones ({resultado.exceptions.length}):</strong>
                <ul>
                  {resultado.exceptions.map((x, i) => (
                    <li key={i}>{x.id} · {x.code} · {x.message}</li>
                  ))}
                </ul>
              </div>
            )}
            <Tabla titulo="Resultado por fila" filas={resultado.rows} />
            <Tabla titulo={`Cuadro (${resultado.schedule.length} períodos)`} filas={resultado.schedule} />
            <Tabla titulo="Totales" filas={Object.keys(resultado.totals).length ? [resultado.totals] : []} />
          </div>
        )}
      </section>

      {/* ---------- 3. Cédulas ---------- */}
      <section>
        <h5>3 · Cédulas</h5>
        {!corrida ? (
          <p className="muted">Corra el motor: las cédulas salen de una corrida que coincide en los dos motores.</p>
        ) : (
          <>
            <p className="muted">
              Mismo libro que arma el sitio, marcado como BORRADOR. El HTML abre sin internet y
              lleva el motor dentro.
            </p>
            <div className="nf-estudio-botones">
              <button type="button" className="btn sm primary" onClick={() => bajarCedulas("excel")}>
                Descargar Excel
              </button>
              <button type="button" className="btn sm" onClick={() => bajarCedulas("html")}>
                Descargar HTML autónomo
              </button>
              {ficha.estado !== "enviada" && (
                <button type="button" className="btn sm" onClick={guardarDefinicion}>
                  Guardar esta definición en la ficha
                </button>
              )}
            </div>
            {guardada && <p className="nf-ok">{guardada}</p>}
          </>
        )}
      </section>
    </div>
  );
}
