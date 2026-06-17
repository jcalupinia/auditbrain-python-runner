import { useState } from "react";
import DashboardEjecutivoTool from "./DashboardEjecutivoTool.jsx";
import "./fin.css";

// Análisis Financiero Empresarial — estructura por fases (CFO Intelligence).
// Fase 1 está operativa (el dashboard ejecutivo). Las fases 2..n son el
// roadmap propuesto (derivado de los módulos del sistema de prompts v3) y
// se muestran como "En preparación" hasta definir/implementar cada una.
const PHASES = [
  {
    id: 1,
    label: "Análisis de Estados Financieros",
    desc:
      "Dashboard ejecutivo a partir de la fuente de información (Formulario 101, balances internos o auditados): Resumen 3D, Estado de Resultados, Principales Gastos, Gastos Atípicos, Balance General (Activo / Pasivo / Patrimonio en formato ejecutivo), Indicadores y Variaciones.",
    ready: true,
  },
  {
    id: 2,
    label: "Calidad del crecimiento y creación de valor",
    desc:
      "¿El crecimiento generó valor o deterioró la posición financiera? Clasificación saludable / frágil / destructivo, análisis precio vs volumen y principales fugas de valor.",
    ready: false,
  },
  {
    id: 3,
    label: "Análisis de inversiones y proyectos",
    desc:
      "Factibilidad, VAN/TIR, flujo esperado vs real y ocupación. Requiere cargar la data de proyectos/inversiones.",
    ready: false,
  },
  {
    id: 4,
    label: "Rentabilidad por unidad de negocio",
    desc:
      "Resultados por línea de negocio / centro de costo. Requiere la segmentación de ingresos y costos.",
    ready: false,
  },
  {
    id: 5,
    label: "Riesgo del grupo e intercompany",
    desc:
      "Mapa de riesgo multi-empresa, partes relacionadas, garantías cruzadas y efecto dominó del grupo económico.",
    ready: false,
  },
  {
    id: 6,
    label: "Resumen ejecutivo para el Directorio",
    desc:
      "Semáforo integral consolidado, plan de acción priorizado y presentación ejecutiva para Gerencia y Accionistas.",
    ready: false,
  },
];

export default function AnalisisFinanciero({ projectId }) {
  const [fase, setFase] = useState(1);
  const cur = PHASES.find((p) => p.id === fase) || PHASES[0];

  return (
    <div className="fin-fases">
      <div className="fin-fases-head">
        <h2>Análisis Financiero Empresarial</h2>
        <p className="tx-muted">
          Centro de trabajo del gerente financiero — análisis por fases.
        </p>
      </div>

      <div className="fin-fase-rail">
        {PHASES.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`fin-fase-tab ${fase === p.id ? "active" : ""} ${
              p.ready ? "" : "soon"
            }`}
            onClick={() => setFase(p.id)}
            title={p.desc}
          >
            <span className="fin-fase-n">Fase {p.id}</span>
            <span className="fin-fase-l">{p.label}</span>
            {!p.ready && <span className="fin-fase-badge">En preparación</span>}
          </button>
        ))}
      </div>

      <div className="fin-fase-body">
        {cur.ready ? (
          <DashboardEjecutivoTool projectId={projectId} />
        ) : (
          <div className="fin-fase-soon">
            <h3>
              Fase {cur.id} · {cur.label}
            </h3>
            <p className="tx-muted">{cur.desc}</p>
            <div className="fin-fase-soon-badge">En preparación</div>
          </div>
        )}
      </div>
    </div>
  );
}
