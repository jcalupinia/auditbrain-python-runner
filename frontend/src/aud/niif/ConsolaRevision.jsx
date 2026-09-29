import { useState } from "react";

import * as api from "../../api";
import {
  bloqueaAprobacion, claseEstado, claseVeredicto, diferencias, resumenRecalculo, tituloVeredicto,
} from "./consolaRevisionVista";

/*
 * Consola de revisión del auditor (piloto de planificación).
 *
 * El auditor la corre en EN_REVISION, antes de aprobar: el servidor recalcula de
 * forma independiente la planificación (índices desde los estados resumidos,
 * agregados desde las cuentas, cuadre del balance), verifica materialidad,
 * indicios NIA 570, anomalías y cobertura, y devuelve el veredicto APTO /
 * OBSERVADO / NO APTO. No cambia la prueba: es la puerta de calidad previa a la
 * aprobación humana del socio (compuerta M23/M24).
 */

function Tarjeta({ titulo, children }) {
  return (
    <div className="nf-consola-tarjeta">
      <strong>{titulo}</strong>
      {children}
    </div>
  );
}

function Recalculo({ titulo, bloque }) {
  const difs = diferencias(bloque);
  return (
    <Tarjeta titulo={titulo}>
      <span className={bloque.conforme ? "nf-ok" : "nf-error"}>{resumenRecalculo(bloque)}</span>
      {difs.length > 0 && (
        <ul className="nf-consola-lista">
          {difs.slice(0, 6).map((f, i) => (
            <li key={i}>
              {(f.etiqueta || f.metrica || f.indice)}{f.periodo ? ` (${f.periodo})` : ""}: motor {String(f.declarado)} · recálculo {String(f.recalculado)}
            </li>
          ))}
        </ul>
      )}
    </Tarjeta>
  );
}

export function ConsolaRevision({ prueba }) {
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [reporte, setReporte] = useState(null);

  async function revisar() {
    setCargando(true);
    setError("");
    try {
      const r = await api.cicloConsolaRevision(prueba.id);
      setReporte(r.reporte);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setCargando(false);
    }
  }

  const mat = reporte?.materialidad;
  const claseCaja = reporte
    ? (reporte.veredicto === "NO APTO" ? "nf-consola-bloque" : reporte.veredicto.startsWith("APTO") ? "nf-consola-apto" : "")
    : "";

  return (
    <div className={`nf-consola ${claseCaja}`}>
      <h6>Consola de revisión del auditor</h6>
      <p className="muted">
        Recálculo independiente de la planificación (índices, agregados y cuadre), materialidad, indicios NIA 570,
        anomalías y cobertura de documentos. La aprobación final la da el socio.
      </p>
      {!reporte && (
        <button type="button" className="btn sm" disabled={cargando} onClick={revisar}>
          {cargando ? "Revisando…" : "Revisar la planificación"}
        </button>
      )}
      {error && <p role="alert" className="nf-error">{error}</p>}

      {reporte && (
        <>
          <p className="nf-consola-veredicto">
            <span className={claseVeredicto(reporte.veredicto)}>{tituloVeredicto(reporte.veredicto)}</span>
            <span className="nf-consola-etq muted">{reporte.etiqueta}</span>
          </p>

          {bloqueaAprobacion(reporte) && (
            <p className="nf-error">
              El recálculo no coincide con el motor o el balance no cuadra: revise las diferencias antes de aprobar.
            </p>
          )}

          <div className="nf-consola-grid">
            <Recalculo titulo="Índices (recálculo independiente)" bloque={reporte.recalculo_indices} />
            <Recalculo titulo="Agregados (desde las cuentas)" bloque={reporte.recalculo_agregados} />
            <Tarjeta titulo="Cuadre del balance">
              {reporte.cuadre.map((f) => (
                <div key={f.periodo}>
                  <span className={f.estado === "cuadra" ? "nf-ok" : "nf-error"}>
                    {f.nombre}: {f.estado} (dif {f.dif.toFixed(2)})
                  </span>
                </div>
              ))}
            </Tarjeta>
            <Tarjeta titulo="Materialidad (NIA 320)">
              {mat?.hay_materialidad ? (
                <span>Global {mat.global} · desempeño {mat.desempeno} · base {mat.base_nombre}</span>
              ) : (
                <span className="nf-warn">Base ≤ 0: sin materialidad hasta elegir otra base.</span>
              )}
            </Tarjeta>
            <Tarjeta titulo="Indicios NIA 570">
              {reporte.nia570.length === 0 ? (
                <span className="nf-ok">Sin indicios de empresa en funcionamiento.</span>
              ) : (
                <ul className="nf-consola-lista">{reporte.nia570.map((t, i) => <li key={i}>{t}</li>)}</ul>
              )}
            </Tarjeta>
            <Tarjeta titulo="Anomalías (NIA 240)">
              <span>{reporte.anomalias.total} detectadas · altas {reporte.anomalias.por_severidad.Alto}</span>
            </Tarjeta>
            <Tarjeta titulo="Cobertura de documentos">
              <span className={reporte.cobertura.veredicto === "CONFORME" ? "nf-ok" : "nf-warn"}>
                {reporte.cobertura.presentes} de {reporte.cobertura.total} · {reporte.cobertura.veredicto}
              </span>
            </Tarjeta>
          </div>

          {reporte.hallazgos.length > 0 && (
            <>
              <h6>Observaciones para el socio</h6>
              <ul className="nf-consola-lista">{reporte.hallazgos.map((t, i) => <li key={i}>{t}</li>)}</ul>
            </>
          )}

          <h6>Puerta de calidad</h6>
          <table className="nf-consola-puerta">
            <tbody>
              {reporte.puerta_calidad.map((c, i) => (
                <tr key={i}>
                  <td className={claseEstado(c.estado)}>{c.estado}</td>
                  <td>{c.criterio}<br /><small className="muted">{c.detalle}</small></td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="nf-estudio-botones">
            <button type="button" className="btn sm" disabled={cargando} onClick={revisar}>
              {cargando ? "Revisando…" : "Volver a revisar"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
