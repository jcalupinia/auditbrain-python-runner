import { useMemo, useState } from "react";
import { compareScenarios, bestScenario, applyScenario } from "./engine.js";
import { fmt } from "./format.js";
import { PROJ } from "./seed.js";
import { generarRecomendacionAgente } from "../api.js";

const ESC = [
  { key: "sin", label: "1 · Sin estrategia" },
  { key: "div", label: "2 · Distribución" },
  { key: "mix", label: "3 · Capitalización + Distribución" },
  { key: "cap", label: "4 · Solo capitalización" },
];
const RUBROS = [
  ["impuesto", "Impuesto (pago a cuenta)"],
  ["repartido", "Dividendos repartidos"],
  ["capitalizado", "Capitalizado"],
  ["sobrante", "Sobrante (no distribuido)"],
  ["devolucion", "Devolución"],
  ["costoMuerto", "Costo muerto (gasto no deducible)"],
];

export default function SecEscenarios({ D, params, recomendacion, setRecomendacion }) {
  // overrides editables para escenarios 2 (div) y 3 (mix); default = applyScenario
  const [ov, setOv] = useState(() => ({
    div: applyScenario("div", D, _ctrl0(), params),
    mix: applyScenario("mix", D, _ctrl0(), params),
  }));
  const [iaLoading, setIaLoading] = useState(false);
  const [iaError, setIaError] = useState("");

  const cmp = useMemo(() => compareScenarios(D, params, ov), [D, params, ov]);
  const best = useMemo(() => bestScenario(cmp), [cmp]);

  const setMonto = (scn, anioIdx, campo, val) =>
    setOv((p) => ({
      ...p,
      [scn]: p[scn].map((r, i) =>
        i === anioIdx ? { ...r, [campo]: parseFloat(val) || 0 } : r,
      ),
    }));

  async function generar() {
    setIaLoading(true);
    setIaError("");
    try {
      const payload = {
        empresa: params.empresa || "",
        comparacion: cmp,
        recomendado: best.key,
      };
      const res = await generarRecomendacionAgente(payload);
      setRecomendacion({
        escenario: best.key,
        narrativa: res.narrativa,
        confianza: res.confianza_modelo,
        requiereRevision: res.requiere_revision_humana,
        totales: cmp[best.key].totales,
        aprobado: false,
      });
    } catch (e) {
      setIaError(e.message || "No se pudo generar la recomendación.");
    } finally {
      setIaLoading(false);
    }
  }

  return (
    <section>
      <div className="tx-h1">Escenarios + Recomendación del agente</div>
      <p className="tx-lead">
        Comparación del pago a cuenta sobre utilidades no distribuidas bajo 4
        escenarios (2026–2028). Edita los montos a repartir/capitalizar en los
        escenarios 2 y 3; el impuesto, el sobrante y el costo muerto recalculan
        en vivo. El agente recomienda el óptimo citando la base legal.
      </p>

      {ESC.map((e) => (
        <div className="tx-card" key={e.key}>
          <h3>
            {e.label}{" "}
            {best.key === e.key && <span className="tx-best">★ Recomendado</span>}
          </h3>
          {(e.key === "div" || e.key === "mix") && (
            <div className="tx-scroll">
              <table className="tx-tbl">
                <thead>
                  <tr>
                    <th>Monto por año</th>
                    {PROJ.map((y) => (
                      <th key={y}>{y}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Dividendos a repartir</td>
                    {[0, 1, 2].map((i) => (
                      <td key={i}>
                        <input
                          className="tx-cin"
                          type="number"
                          value={ov[e.key][i].div}
                          onChange={(ev) => setMonto(e.key, i, "div", ev.target.value)}
                        />
                      </td>
                    ))}
                  </tr>
                  {e.key === "mix" && (
                    <tr>
                      <td>Valor a capitalizar</td>
                      {[0, 1, 2].map((i) => (
                        <td key={i}>
                          <input
                            className="tx-cin"
                            type="number"
                            value={ov[e.key][i].cap}
                            onChange={(ev) =>
                              setMonto(e.key, i, "cap", ev.target.value)
                            }
                          />
                        </td>
                      ))}
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
          <div className="tx-scroll">
            <table className="tx-tbl">
              <thead>
                <tr>
                  <th>Concepto (USD)</th>
                  {PROJ.map((y) => (
                    <th key={y}>{y}</th>
                  ))}
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {RUBROS.map(([k, l]) => (
                  <tr key={k} className={k === "costoMuerto" ? "chkrow" : ""}>
                    <td>{l}</td>
                    {cmp[e.key].rows.map((r, i) => (
                      <td
                        key={i}
                        className={k === "costoMuerto" && r[k] > 0 ? "cuadre-bad" : ""}
                      >
                        {fmt(r[k])}
                      </td>
                    ))}
                    <td>{fmt(cmp[e.key].totales[k] || 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      <div className="tx-card">
        <h3>Recomendación del agente</h3>
        <button className="tx-btn" onClick={generar} disabled={iaLoading}>
          {iaLoading ? "Generando…" : "Generar recomendación (IA)"}
        </button>
        {iaError && <span className="tx-warn-line">{iaError}</span>}
        {recomendacion && (
          <RecPanel rec={recomendacion} setRec={setRecomendacion} />
        )}
      </div>
    </section>
  );
}

function RecPanel({ rec, setRec }) {
  return (
    <div className={`tx-rec ${rec.confianza === "baja" ? "rec-baja" : ""}`}>
      <p className="tx-rec-narr">{rec.narrativa}</p>
      <p className="tx-disclaimer">
        Análisis generado por IA. La interpretación debe ser validada por el
        profesional responsable antes de cualquier decisión.
        {rec.requiereRevision && " ⚠ Requiere revisión humana."}
      </p>
      {!rec.aprobado ? (
        <button
          className="tx-btn primary"
          onClick={() => setRec({ ...rec, aprobado: true })}
        >
          Aprobar escenario → Informe y Presentación
        </button>
      ) : (
        <span className="tx-ok-line">
          ✓ Escenario aprobado. Disponible en Informe gerencial y Presentación.
        </span>
      )}
    </div>
  );
}

function _ctrl0() {
  return [
    { g: 0, div: 0, cap: 0 },
    { g: 0, div: 0, cap: 0 },
    { g: 0, div: 0, cap: 0 },
  ];
}
