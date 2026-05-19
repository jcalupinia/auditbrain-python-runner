import { motion } from "framer-motion";
import { LAYERS, AGENT_STATE, STATUS_TONE, GRUPO_002, FLOWS } from "../data/mock.js";
import { Card, SectionTitle, Tag, StatusDot, Sparkline, RiskTag } from "./ui.jsx";

export default function LayerWorkspace({ code, onBack }) {
  const l = LAYERS.find((x) => x.code === code);
  if (!l) return null;
  const st = AGENT_STATE[l.agent];
  const relatedFlows = FLOWS.filter(
    (f) => f.a === code || f.b === code || f.b === "ALL"
  );
  const findings = GRUPO_002.findings.filter((f) => f.m.includes(code));

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

      <Card className="ab-relative ab-overflow-hidden ab-p-6">
        <span className="ab-pointer-events-none ab-absolute ab--right-16 ab--top-20 ab-h-56 ab-w-56 ab-rounded-full ab-bg-ab-cyan/10 ab-blur-3xl" />
        <div className="ab-relative ab-flex ab-flex-wrap ab-items-start ab-justify-between ab-gap-4">
          <div className="ab-flex ab-items-center ab-gap-4">
            <span className="ab-grid ab-h-14 ab-w-16 ab-place-items-center ab-rounded-xl ab-border ab-border-ab-gold/30 ab-bg-ab-goldsoft ab-font-mono ab-text-lg ab-font-extrabold ab-text-ab-gold">
              {l.code === "ROUTER" ? "RTR" : l.code}
            </span>
            <div>
              <div className="ab-font-mono ab-text-[11px] ab-text-ab-faint">
                Capa {l.num} · {l.code}
              </div>
              <h1 className="ab-text-[24px] ab-font-extrabold ab-tracking-tight ab-text-ab-ink">
                {l.name}
              </h1>
              <div className="ab-mt-1.5 ab-flex ab-flex-wrap ab-items-center ab-gap-2">
                <Tag tone={STATUS_TONE[l.status]}>{l.status}</Tag>
                <Tag tone={st.tone}>
                  <StatusDot tone={st.tone} pulse={l.agent !== "idle"} /> {st.label}
                </Tag>
              </div>
            </div>
          </div>
          <Sparkline points={l.spark} tone={l.agent === "awaiting" ? "high" : "cyan"} w={140} h={44} />
        </div>
        <p className="ab-relative ab-mt-4 ab-max-w-2xl ab-text-[13px] ab-leading-relaxed ab-text-ab-mute">
          {l.desc}
        </p>
      </Card>

      <div className="ab-grid ab-gap-5 lg:ab-grid-cols-3">
        <Card className="ab-p-4">
          <SectionTitle kicker="Skill Registry" title="Skills de la capa" />
          {l.skills.total == null ? (
            <div className="ab-py-6 ab-text-center ab-text-[12px] ab-text-ab-faint">
              Capa autónoma — sin skills físicas (§3.1)
            </div>
          ) : (
            <>
              <div className="ab-flex ab-items-baseline ab-gap-2">
                <span className="ab-text-[34px] ab-font-extrabold ab-tabular-nums ab-text-ab-ink">
                  {l.skills.done}
                </span>
                <span className="ab-font-mono ab-text-[13px] ab-text-ab-faint">
                  / {l.skills.total}
                </span>
              </div>
              <div className="ab-mt-2 ab-h-2 ab-w-full ab-overflow-hidden ab-rounded-full ab-bg-white/5">
                <div
                  className={`ab-h-full ab-rounded-full ${
                    l.skills.done === l.skills.total ? "ab-bg-ab-low" : "ab-bg-ab-med"
                  }`}
                  style={{ width: `${(l.skills.done / l.skills.total) * 100}%` }}
                />
              </div>
              <div className="ab-mt-2 ab-font-mono ab-text-[11px] ab-text-ab-faint">
                IDs {l.skills.ids}
              </div>
              <p className="ab-mt-3 ab-text-[11px] ab-leading-snug ab-text-ab-mute">
                Skills de Alto Riesgo requieren revisión humana obligatoria
                antes de cualquier entrega (Regla #3).
              </p>
            </>
          )}
        </Card>

        <Card className="ab-p-4">
          <SectionTitle kicker="§2.1" title="Flujos relacionados" />
          <div className="ab-flex ab-flex-col ab-gap-2">
            {relatedFlows.length === 0 && (
              <div className="ab-py-4 ab-text-[12px] ab-text-ab-faint">
                Sin flujos críticos directos documentados.
              </div>
            )}
            {relatedFlows.map((f) => (
              <div
                key={f.id}
                className="ab-rounded-lg ab-border ab-border-ab-line ab-bg-ab-surface ab-px-3 ab-py-2"
              >
                <div className="ab-flex ab-items-center ab-justify-between">
                  <span className="ab-font-mono ab-text-[11px] ab-font-bold ab-text-ab-cyan">
                    {f.id}
                  </span>
                  {f.crit && <Tag tone="high">crítico</Tag>}
                </div>
                <div className="ab-mt-1 ab-text-[11.5px] ab-text-ab-mute">{f.t}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="ab-p-4">
          <SectionTitle kicker="GRUPO_002 · §7.2" title="Hallazgos de la capa" />
          {findings.length === 0 ? (
            <div className="ab-py-6 ab-text-center ab-text-[12px] ab-text-ab-faint">
              Sin hallazgos asignados en el caso de referencia.
            </div>
          ) : (
            <div className="ab-flex ab-flex-col ab-gap-2">
              {findings.map((f) => (
                <div
                  key={f.n}
                  className="ab-rounded-lg ab-border ab-border-ab-high/20 ab-bg-ab-highsoft ab-px-3 ab-py-2"
                >
                  <div className="ab-flex ab-items-center ab-justify-between ab-gap-2">
                    <span className="ab-font-mono ab-text-[10px] ab-text-ab-faint">
                      #{f.n} · {f.m}
                    </span>
                    <RiskTag level={f.r} />
                  </div>
                  <div className="ab-mt-1 ab-text-[11.5px] ab-leading-snug ab-text-ab-ink">
                    {f.t}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card className="ab-p-4">
        <SectionTitle kicker="Entregable" title="Último output de la capa" />
        <div className="ab-flex ab-items-center ab-justify-between ab-gap-3 ab-rounded-lg ab-border ab-border-ab-line ab-bg-ab-surface ab-px-4 ab-py-3">
          <div className="ab-flex ab-items-center ab-gap-3">
            <span className="ab-text-ab-gold">▤</span>
            <span className="ab-text-[13px] ab-text-ab-ink">{l.deliverable}</span>
          </div>
          <Tag tone="med">Pendiente aprobación Socio</Tag>
        </div>
      </Card>
    </motion.div>
  );
}
