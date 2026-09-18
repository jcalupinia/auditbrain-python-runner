import { useState } from "react";
import { pceCxcAnalizar, pceCxcDescargarExcel } from "../api.js";
import { carteraMedida as calcularCarteraMedida, fechaEmision } from "./pceCxc.js";
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
        {
          project_id: projectId ?? null,
          entidad: datos.entidad,
          fechas: CORTES.map((c) => fechas[c.k]),
          // Se guarda con la corrida para que el Excel imprima la fecha de
          // emisión y no la del día en que se descargue el papel.
          fecha_emision: fechaEmision(),
          umbral_dias_incumplimiento: Number(datos.umbral_dias) || 730,
          umbral_individual: Number(datos.umbral_individual) || 0,
          materialidad: Number(datos.materialidad) || 0,
          eeff: {
            no_relacionados: Number(datos.eeff_nr) || 0,
            relacionados: Number(datos.eeff_r) || 0,
          },
        }
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
  const carteraMedida = calcularCarteraMedida(cartera, sinMedirTotal, sinEstratificar);
  const cobertura =
    carteraMedida && carteraMedida > 0.005 ? (res?.ecl_total ?? 0) / carteraMedida : null;

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
              {matriz.tramos.map((t, i) => (
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
