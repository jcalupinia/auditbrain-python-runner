import { motion } from "framer-motion";
import { GOV_LAYER, GOV_RULES, APPROVAL_QUEUE } from "../data/mock.js";
import { Card, SectionTitle, Tag, StatusDot, RiskTag } from "./ui.jsx";

const PILLARS = [
  "Defensibilidad regulatoria",
  "Trazabilidad inviolable (Audit Trail)",
  "Revisión humana obligatoria",
  "Separación hechos / análisis / riesgo",
  "Escalamiento estructurado",
  "Criterio profesional sobre eficiencia",
];

const ESCALATION = ["N1", "N2", "N3", "N4", "N5"];

export default function GovernancePanel({ onBack }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="ab-flex ab-flex-col ab-gap-5"
    >
      <button
        onClick={onBack}
        className="ab-flex ab-w-fit ab-items-center ab-gap-1.5 ab-font-mono ab-text-[11px] ab-text-ab-faint hover:ab-text-ab-mute"
      >
        ← Executive Overview
      </button>

      <Card className="ab-relative ab-overflow-hidden ab-border-ab-high/25 ab-p-6">
        <span className="ab-pointer-events-none ab-absolute ab--right-16 ab--top-20 ab-h-56 ab-w-56 ab-rounded-full ab-bg-ab-high/10 ab-blur-3xl" />
        <div className="ab-relative ab-flex ab-flex-wrap ab-items-start ab-justify-between ab-gap-4">
          <div className="ab-flex ab-items-center ab-gap-4">
            <span className="ab-grid ab-h-14 ab-w-16 ab-place-items-center ab-rounded-xl ab-border ab-border-ab-high/30 ab-bg-ab-highsoft ab-text-2xl ab-text-ab-high">
              ⛉
            </span>
            <div>
              <div className="ab-font-mono ab-text-[11px] ab-text-ab-faint">
                Capa transversal · inviolable
              </div>
              <h1 className="ab-text-[24px] ab-font-extrabold ab-tracking-tight ab-text-ab-ink">
                Governance Layer
              </h1>
              <div className="ab-mt-1.5 ab-flex ab-flex-wrap ab-gap-2">
                <Tag tone="low">
                  <StatusDot tone="low" pulse /> {GOV_LAYER.rulesActive} reglas activas
                </Tag>
                <Tag tone="med">Escalamiento {GOV_LAYER.currentEscalation}</Tag>
              </div>
            </div>
          </div>
        </div>
        <p className="ab-relative ab-mt-4 ab-max-w-2xl ab-border-l-2 ab-border-ab-high ab-pl-3 ab-text-[13px] ab-leading-relaxed ab-text-ab-mute">
          {GOV_LAYER.foundational}
        </p>
      </Card>

      <Card className="ab-border-ab-high/20 ab-p-4">
        <SectionTitle
          kicker="Cola de aprobaciones · acción del Socio"
          title="Outputs de Alto Riesgo en espera"
          right={<Tag tone="high">{APPROVAL_QUEUE.length} pendientes</Tag>}
        />
        <div className="ab-flex ab-flex-col ab-gap-2">
          {APPROVAL_QUEUE.map((q) => (
            <div
              key={q.id}
              className="ab-flex ab-flex-wrap ab-items-center ab-gap-3 ab-rounded-lg ab-border ab-border-ab-high/20 ab-bg-ab-highsoft ab-px-3 ab-py-2.5"
            >
              <span className="ab-font-mono ab-text-[11px] ab-font-bold ab-text-ab-high">
                {q.id}
              </span>
              <span className="ab-rounded ab-bg-white/5 ab-px-1.5 ab-py-px ab-font-mono ab-text-[10px] ab-text-ab-mute">
                {q.layer}
              </span>
              <span className="ab-min-w-0 ab-flex-1 ab-truncate ab-text-[12.5px] ab-text-ab-ink">
                {q.title}
              </span>
              <RiskTag level={q.risk} />
              <span className="ab-font-mono ab-text-[10px] ab-text-ab-faint">SLA {q.sla}</span>
              <div className="ab-flex ab-gap-1.5">
                <span className="ab-rounded-md ab-border ab-border-ab-low/30 ab-bg-ab-lowsoft ab-px-2.5 ab-py-1 ab-text-[11px] ab-font-semibold ab-text-ab-low">
                  Aprobar
                </span>
                <span className="ab-rounded-md ab-border ab-border-ab-line ab-px-2.5 ab-py-1 ab-text-[11px] ab-text-ab-mute">
                  Revisar
                </span>
              </div>
            </div>
          ))}
        </div>
        <p className="ab-mt-3 ab-font-mono ab-text-[10px] ab-text-ab-faint">
          Acciones ilustrativas — sin backend conectado en esta fase.
        </p>
      </Card>

      <div className="ab-grid ab-gap-5 lg:ab-grid-cols-2">
        <Card className="ab-p-4">
          <SectionTitle kicker="§9.4" title="23 reglas inviolables" />
          <div className="ab-flex ab-flex-col ab-gap-1.5">
            {GOV_RULES.map((r) => (
              <div
                key={r.n}
                className="ab-flex ab-items-start ab-gap-2.5 ab-rounded-lg ab-border ab-border-ab-line ab-bg-ab-surface ab-px-3 ab-py-2"
              >
                <span className="ab-mt-px ab-font-mono ab-text-[11px] ab-font-bold ab-text-ab-gold">
                  #{r.n}
                </span>
                <span className="ab-flex-1 ab-text-[11.5px] ab-leading-snug ab-text-ab-mute">
                  {r.text}
                </span>
                <StatusDot tone="low" />
              </div>
            ))}
            <p className="ab-mt-1 ab-font-mono ab-text-[10px] ab-text-ab-faint">
              + {GOV_LAYER.rulesActive - GOV_RULES.length} reglas universales adicionales activas.
            </p>
          </div>
        </Card>

        <div className="ab-flex ab-flex-col ab-gap-5">
          <Card className="ab-p-4">
            <SectionTitle kicker="Gobernanza" title="6 pilares" />
            <div className="ab-grid ab-grid-cols-1 ab-gap-2 sm:ab-grid-cols-2">
              {PILLARS.map((p, i) => (
                <div
                  key={p}
                  className="ab-flex ab-items-center ab-gap-2 ab-rounded-lg ab-border ab-border-ab-line ab-bg-ab-surface ab-px-3 ab-py-2.5"
                >
                  <span className="ab-font-mono ab-text-[11px] ab-text-ab-gold">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="ab-text-[11.5px] ab-text-ab-mute">{p}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card className="ab-p-4">
            <SectionTitle kicker="5 niveles" title="Escalamiento" />
            <div className="ab-flex ab-items-center ab-gap-1.5">
              {ESCALATION.map((n) => {
                const active = n === GOV_LAYER.currentEscalation;
                return (
                  <div key={n} className="ab-flex ab-flex-1 ab-flex-col ab-items-center ab-gap-1.5">
                    <div
                      className={`ab-h-2 ab-w-full ab-rounded-full ${
                        active ? "ab-bg-ab-med" : "ab-bg-white/5"
                      }`}
                    />
                    <span
                      className={`ab-font-mono ab-text-[11px] ${
                        active ? "ab-text-ab-med ab-font-bold" : "ab-text-ab-faint"
                      }`}
                    >
                      {n}
                    </span>
                  </div>
                );
              })}
            </div>
            <p className="ab-mt-3 ab-text-[11px] ab-leading-snug ab-text-ab-mute">
              Defensible ante directorio, regulador, auditor externo y Comité de
              Ética. El Governance Layer no puede saltarse por eficiencia (Regla #6).
            </p>
          </Card>
        </div>
      </div>
    </motion.div>
  );
}
