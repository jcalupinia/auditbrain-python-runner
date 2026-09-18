import { useState } from "react";
import { pceCxcAnalizar, pceCxcDescargarExcel } from "../api.js";
import {
  bandasDeLaPolitica,
  carteraMedidaDe,
  coberturaDe,
  controlDeLaCohorte,
  parametrosDeLaCorrida,
  tramosVisibles,
} from "./pceCxc.js";
import "./pceCxc.css";

const CORTES = [
  { k: "a1", t: "Corte más antiguo (t-2)" },
  { k: "a2", t: "Corte intermedio (t-1)" },
  { k: "a3", t: "Corte actual" },
];

const money = (v) =>
  v == null || isNaN(v)
    ? "—"
    : Number(v).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (v) => (v == null || !isFinite(v) ? "—" : `${(v * 100).toFixed(2)} %`);

export default function PceCxcTool({ projectId }) {
  const [archivos, setArchivos] = useState({});
  const [fechas, setFechas] = useState({ a1: "", a2: "", a3: "" });
  const [datos, setDatos] = useState({
    entidad: "",
    materialidad: "",
    umbral_individual: "",
    eeff_nr: "",
    eeff_r: "",
    umbral_dias: 730,
    mayor_provision: "",
    // Política de deterioro del cliente, en % por banda. Lo que quede en
    // blanco NO se envía: el papel lo declara «sin comparar» en vez de
    // suponer un 0 % que el cliente nunca afirmó.
    politica: {},
  });
  const [procesando, setProcesando] = useState(false);
  const [error, setError] = useState("");
  const [res, setRes] = useState(null);
  const [descargando, setDescargando] = useState(false);

  const listo = CORTES.every((c) => archivos[c.k] && fechas[c.k]);

  async function calcular() {
    setProcesando(true);
    setError("");
    setRes(null);
    try {
      const salida = await pceCxcAnalizar(
        CORTES.map((c) => archivos[c.k]),
        parametrosDeLaCorrida(
          datos,
          CORTES.map((c) => fechas[c.k]),
          projectId
        )
      );
      setRes(salida);
    } catch (e) {
      setError(`No se pudo calcular la matriz: ${e.message}`);
    } finally {
      setProcesando(false);
    }
  }

  async function descargar() {
    setDescargando(true);
    setError("");
    try {
      await pceCxcDescargarExcel(res.corrida_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setDescargando(false);
    }
  }

  const exposicion = res?.exposicion;
  const matriz = res?.matriz;
  const individual = res?.individual;
  const conciliacion = res?.conciliacion;
  const sinMedirTotal = exposicion?.sin_medir ?? 0;
  const sinEstratificar = exposicion?.sin_estratificar ?? 0;
  const cartera = exposicion?.total ?? null;
  // La cartera medida y la cobertura las calcula el motor
  // (`motor.resumen_deterioro`): la pantalla las muestra, no las vuelve a deducir.
  const carteraMedida = carteraMedidaDe(res);
  const cobertura = coberturaDe(res);
  const controlCohorte = controlDeLaCohorte(res);
  const filasMatriz = tramosVisibles(matriz?.tramos);
  const filasOmitidas = (matriz?.tramos?.length ?? 0) - filasMatriz.length;

  return (
    <div className="pce">
      <h2>Matriz de pérdidas crediticias esperadas · NIIF 9</h2>
      <p className="pce-sub">
        Enfoque simplificado. Las tasas se derivan del comportamiento observado de la cartera; el
        sistema no asume ninguna. Lo que falte para medir se reporta como pendiente, nunca como
        cero.
      </p>

      <div className="pce-grid">
        {CORTES.map((c) => (
          <div key={c.k} className="pce-slot">
            <div className="pce-tag">{c.t}</div>
            <input
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={(e) =>
                setArchivos({ ...archivos, [c.k]: e.target.files[0] || null })
              }
            />
            {archivos[c.k] && <span className="pce-filename">{archivos[c.k].name}</span>}
            <label>Fecha de corte</label>
            <input
              type="date"
              value={fechas[c.k]}
              onChange={(e) => setFechas({ ...fechas, [c.k]: e.target.value })}
            />
          </div>
        ))}
      </div>

      <div className="pce-grid">
        <label>
          Entidad auditada
          <input
            value={datos.entidad}
            onChange={(e) => setDatos({ ...datos, entidad: e.target.value })}
          />
        </label>
        <label>
          Materialidad de desempeño
          <input
            type="number"
            value={datos.materialidad}
            onChange={(e) => setDatos({ ...datos, materialidad: e.target.value })}
          />
        </label>
        <label>
          Umbral de evaluación individual
          <input
            type="number"
            value={datos.umbral_individual}
            onChange={(e) => setDatos({ ...datos, umbral_individual: e.target.value })}
          />
        </label>
        <label>
          Cartera según EEFF · no relacionados
          <input
            type="number"
            value={datos.eeff_nr}
            onChange={(e) => setDatos({ ...datos, eeff_nr: e.target.value })}
          />
        </label>
        <label>
          Cartera según EEFF · relacionados
          <input
            type="number"
            value={datos.eeff_r}
            onChange={(e) => setDatos({ ...datos, eeff_r: e.target.value })}
          />
        </label>
        <label>
          Incumplimiento (días sin cobro)
          <input
            type="number"
            value={datos.umbral_dias}
            onChange={(e) => setDatos({ ...datos, umbral_dias: e.target.value })}
          />
        </label>
      </div>

      <label className="pce-declaracion">
        Mayores de la provisión de los tres ejercicios — referencia y conclusión sobre los castigos
        <textarea
          rows={2}
          placeholder="P. ej.: mayor 2.1.3.01 de 2022, 2023 y 2024 (PT B-2); castigos por USD 340, inmateriales frente a la cartera."
          value={datos.mayor_provision}
          onChange={(e) => setDatos({ ...datos, mayor_provision: e.target.value })}
        />
        <span>
          El método de permanencia supone que lo que desapareció de la cartera se cobró. Eso solo
          vale si los castigos del período fueron inmateriales, y eso se demuestra con los mayores
          de la provisión. Si se deja vacío, queda declarado como pendiente.
        </span>
      </label>

      <fieldset className="pce-politica">
        <legend>Política de deterioro del cliente (% por banda)</legend>
        <p className="pce-hint">
          Es el porcentaje que la entidad provisiona hoy en cada banda, según su política escrita.
          La banda que se deje en blanco queda <b>sin comparar</b> en el papel de trabajo y se
          declara como pendiente: el sistema no la supone en 0 %, porque eso acusaría al cliente de
          no provisionar una banda que nadie le preguntó.
        </p>
        <div className="pce-grid">
          {bandasDeLaPolitica(datos.umbral_dias).map((banda) => (
            <label key={banda}>
              {banda}
              <input
                type="number"
                step="0.01"
                min="0"
                max="100"
                placeholder="sin declarar"
                value={datos.politica[banda] ?? ""}
                onChange={(e) =>
                  setDatos({
                    ...datos,
                    politica: { ...datos.politica, [banda]: e.target.value },
                  })
                }
              />
            </label>
          ))}
        </div>
      </fieldset>

      <button className="pce-btn" disabled={!listo || procesando} onClick={calcular}>
        Calcular la matriz
      </button>
      {!listo && !procesando && (
        <div className="pce-hint">Suba los tres cortes con su fecha para habilitar el cálculo.</div>
      )}
      {procesando && <div className="pce-msg pce-info">Procesando los tres cortes…</div>}
      {error && <div className="pce-msg pce-bad">{error}</div>}

      {res && (
        <div className="pce-res">
          <div className="pce-preliminar">
            Papel de trabajo PRELIMINAR — pendiente de revisión y aprobación del Socio responsable.
          </div>

          <div className="pce-kpis">
            <div>
              <span>Cartera total</span>
              <b>{money(cartera)}</b>
            </div>
            <div>
              {/* Misma cifra y misma etiqueta que 08-Conciliacion del Excel. */}
              <span>Cartera medida</span>
              <b>{money(carteraMedida)}</b>
            </div>
            <div className={sinMedirTotal > 0.005 ? "pce-kpi-bad" : ""}>
              <span>Sin medir</span>
              <b>{money(sinMedirTotal)}</b>
            </div>
            <div>
              <span>Pérdida esperada (ECL)</span>
              <b>{money(res.ecl_total)}</b>
            </div>
            <div>
              <span>Cobertura sobre lo medido</span>
              <b>{pct(cobertura)}</b>
            </div>
            <div>
              <span>Trazabilidad de la cohorte</span>
              <b>{pct(res.trazabilidad)}</b>
            </div>
          </div>

          {sinMedirTotal > 0.005 && (
            <div className="pce-msg pce-bad">
              Quedan {money(sinMedirTotal)} sin medir por falta de tasa histórica en su banda. Una
              tasa cero por ausencia de historia no es evidencia de ausencia de pérdida.
            </div>
          )}
          {sinEstratificar > 0.005 && (
            <div className="pce-msg pce-warn">
              {money(sinEstratificar)} de los estados financieros no se pudo ubicar en ningún
              segmento del análisis de antigüedad cargado: revise si falta cartera por cargar.
            </div>
          )}
          {controlCohorte && !controlCohorte.consistente && (
            <div className="pce-msg pce-bad">
              <b>Control del corte intermedio:</b> {controlCohorte.total} documento(s) de la cohorte
              siguen una trayectoria imposible entre los tres cortes ({controlCohorte.ejemplos}):
              desaparecen en el corte intermedio y reaparecen en el actual, o su saldo crece sin
              facturación nueva. {money(controlCohorte.importe)} del remanente que alimenta las
              tasas provienen de esos documentos.
            </div>
          )}
          {controlCohorte && controlCohorte.consistente && (
            <div className="pce-msg pce-info">
              <b>Control del corte intermedio:</b> los {controlCohorte.documentos} documentos de la
              cohorte son coherentes entre los tres cortes; {controlCohorte.vivos} seguían vivos en
              t-1 ({pct(controlCohorte.permanencia)}).
            </div>
          )}
          {conciliacion && conciliacion.cuadra != null && !conciliacion.cuadra && (
            <div className="pce-msg pce-warn">
              La cartera analizada no concilia con el saldo contable: diferencia de{" "}
              {money(conciliacion.diferencia)}.
            </div>
          )}

          <h3>Matriz por banda</h3>
          <table className="pce-tabla">
            <thead>
              <tr>
                <th>Segmento</th>
                <th>Banda</th>
                <th>Exposición</th>
                <th>Tasa</th>
                <th>Pérdida esperada</th>
              </tr>
            </thead>
            <tbody>
              {filasMatriz.map((t, i) => (
                <tr key={`${t.segmento}-${t.tramo}-${i}`} className={t.ecl == null ? "pce-sinmedir" : ""}>
                  <td>{t.segmento}</td>
                  <td>{t.tramo}</td>
                  <td>{money(t.exposicion)}</td>
                  <td>{t.tasa_perdida == null ? "sin medir" : pct(t.tasa_perdida)}</td>
                  <td>{t.ecl == null ? "sin medir" : money(t.ecl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {filasOmitidas > 0 && (
            <div className="pce-nota-tabla">
              No se listan {filasOmitidas} combinaciones de segmento × banda por estar sin
              exposición ni tasa observada: no son una pérdida cero medida, son combinaciones que
              no existen en la cartera del corte.
            </div>
          )}

          {individual && individual.casos.length > 0 && (
            <>
              <h3>Evaluación individual</h3>
              <table className="pce-tabla">
                <thead>
                  <tr>
                    <th>Cliente</th>
                    <th>Saldo</th>
                    <th>Pérdida esperada</th>
                    <th>Sustento</th>
                  </tr>
                </thead>
                <tbody>
                  {individual.casos.map((c, i) => (
                    <tr key={i} className={c.saldo_sin_tasa > 0.005 ? "pce-sinmedir" : ""}>
                      <td>{c.identificacion}</td>
                      <td>{money(c.saldo)}</td>
                      <td>{money(c.ecl)}</td>
                      <td>{c.sustento}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {res.hallazgos && res.hallazgos.length > 0 && (
            <>
              <h3>Hallazgos</h3>
              <ul className="pce-hallazgos">
                {res.hallazgos.map((h, i) => (
                  <li key={i}>
                    <b>
                      [{h.riesgo}] {h.titulo}
                    </b>
                    <span>{h.condicion}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {res.pendientes.length > 0 && (
            <div className="pce-msg pce-warn">
              <b>Pendientes que impiden concluir:</b>
              <ul>
                {res.pendientes.map((p, i) => (
                  <li key={i}>
                    {p.variable} — {p.efecto} ({p.responsable})
                  </li>
                ))}
              </ul>
            </div>
          )}

          {res.corrida_id != null && (
            <button className="pce-btn" disabled={descargando} onClick={descargar}>
              {descargando ? "Descargando…" : "Descargar el papel de trabajo"}
            </button>
          )}
          <div className="pce-nota">
            Papel de trabajo preliminar. Requiere revisión y aprobación del Socio responsable antes
            de usarse como conclusión de auditoría.
          </div>
        </div>
      )}
    </div>
  );
}
