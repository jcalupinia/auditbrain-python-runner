import { motion } from "framer-motion";
import {
  META,
  LAYERS,
  KPIS,
  STATUS_BOARD,
  WORKFLOWS,
  FLOWS,
  GOV_LAYER,
  GOV_RULES,
} from "../data/mock.js";
import { Card, SectionTitle, Tag, StatusDot, Progress, RiskTag } from "./ui.jsx";
import AgentCard from "./AgentCard.jsx";

const fade = {
  hidden: { opacity: 0, y: 14 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { delay: i * 0.04, duration: 0.4 } }),
};

function Hero() {
  return (
    <Card className="ab-relative ab-overflow-hidden ab-p-6">
      <span className="ab-pointer-events-none ab-absolute ab--right-20 ab--top-24 ab-h-64 ab-w-64 ab-rounded-full ab-bg-ab-gold/10 ab-blur-3xl" />
      <div className="ab-relative ab-flex ab-flex-wrap ab-items-start ab-justify-between ab-gap-4">
        <div className="ab-max-w-2xl">
          <div className="ab-mb-2 ab-flex ab-flex-wrap ab-items-center ab-gap-2">
            <Tag tone="gold">{META.classification}</Tag>
            <Tag tone="cyan">{META.version}</Tag>
            <Tag tone="med">{META.phase}</Tag>
          </div>
          <h1 className="ab-text-[26px] ab-font-extrabold ab-leading-tight ab-tracking-tight ab-text-ab-ink sm:ab-text-[30px]">
            Sistema operativo profesional <span className="ab-text-ab-gold">multicapa</span>
          </h1>
          <p className="ab-mt-2 ab-max-w-xl ab-text-[13px] ab-leading-relaxed ab-text-ab-mute">
            11 capas funcionales, agentes especializados y Governance Layer inviolable.
            Una firma Big Four operada por IA bajo criterio humano.
          </p>
          <p className="ab-mt-3 ab-border-l-2 ab-border-ab-gold ab-pl-3 ab-font-mono ab-text-[12px] ab-italic ab-text-ab-mute">
            “{META.tagline}”
          </p>
        </div>
        <div className="ab-flex ab-items-center ab-gap-2 ab-rounded-xl ab-border ab-border-ab-line ab-bg-ab-surface2 ab-px-4 ab-py-3">
          <StatusDot tone="low" pulse />
          <div>
            <div className="ab-font-mono ab-text-[11px] ab-text-ab-faint">Plataforma</div>
            <div className="ab-text-[13px] ab-font-bold ab-text-ab-ink">Operativa</div>
            <div className="ab-font-mono ab-text-[10px] ab-text-ab-faint">446 tests · 0 failed</div>
          </div>
        </div>
      </div>
    </Card>
  );
}

function KpiGrid() {
  return (
    <div className="ab-grid ab-grid-cols-2 ab-gap-3 md:ab-grid-cols-4">
      {KPIS.map((k, i) => (
        <motion.div key={k.label} custom={i} variants={fade} initial="hidden" animate="show">
          <Card className="ab-p-3.5">
            <div className="ab-flex ab-items-start ab-justify-between ab-gap-2">
              <span className="ab-text-[10.5px] ab-leading-tight ab-text-ab-faint">
                {k.label}
              </span>
              <StatusDot tone={k.tone} />
            </div>
            <div className="ab-mt-2 ab-flex ab-items-baseline ab-gap-1.5">
              <span className="ab-text-[24px] ab-font-extrabold ab-tabular-nums ab-text-ab-ink">
                {k.value}
              </span>
              <span className="ab-font-mono ab-text-[10px] ab-text-ab-faint">→ {k.target}</span>
            </div>
            <div className="ab-mt-2">
              <Progress pct={k.pct} tone={k.tone} />
            </div>
            <div className="ab-mt-1 ab-font-mono ab-text-[10px] ab-text-ab-faint">{k.unit}</div>
          </Card>
        </motion.div>
      ))}
    </div>
  );
}

function StatusBoard() {
  return (
    <Card className="ab-p-4">
      <SectionTitle kicker="Informe v1.7 · §10" title="Indicadores de estado" />
      <div className="ab-grid ab-grid-cols-1 ab-gap-x-6 ab-gap-y-0 sm:ab-grid-cols-2">
        {STATUS_BOARD.map((r) => (
          <div
            key={r.k}
            className="ab-flex ab-items-center ab-justify-between ab-border-b ab-border-ab-line ab-py-2.5 last:ab-border-0"
          >
            <span className="ab-flex ab-items-center ab-gap-2 ab-text-[12px] ab-text-ab-mute">
              <StatusDot tone={r.s} /> {r.k}
            </span>
            <span className="ab-font-mono ab-text-[11.5px] ab-text-ab-ink">{r.v}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function AgentGrid({ onOpen }) {
  return (
    <div>
      <SectionTitle
        kicker="Capas funcionales como agentes IA"
        title="Agent Grid · 11 capas"
        right={
          <div className="ab-flex ab-items-center ab-gap-3 ab-font-mono ab-text-[10px] ab-text-ab-faint">
            <span className="ab-flex ab-items-center ab-gap-1">
              <span className="ab-h-1.5 ab-w-1.5 ab-rounded-full ab-bg-ab-gold" /> generando
            </span>
            <span className="ab-flex ab-items-center ab-gap-1">
              <span className="ab-h-1.5 ab-w-1.5 ab-rounded-full ab-bg-ab-high" /> aprobación
            </span>
          </div>
        }
      />
      <div className="ab-grid ab-grid-cols-1 ab-gap-3 sm:ab-grid-cols-2 2xl:ab-grid-cols-3">
        {LAYERS.map((l, i) => (
          <motion.div key={l.code} custom={i} variants={fade} initial="hidden" animate="show">
            <AgentCard l={l} onOpen={() => onOpen(l.code)} />
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function WorkflowStatus() {
  return (
    <Card className="ab-p-4">
      <SectionTitle
        kicker="Orquestación n8n · §5.1"
        title="Workflow status · W001–W015"
        right={
          <Tag tone="med">15 diseñados · 0 en producción</Tag>
        }
      />
      <div className="ab-flex ab-flex-col ab-gap-1.5">
        {WORKFLOWS.map((w) => (
          <div
            key={w.id}
            className={`ab-flex ab-items-center ab-gap-3 ab-rounded-lg ab-border ab-px-3 ab-py-2 ${
              w.highlight
                ? "ab-border-ab-gold/30 ab-bg-ab-goldsoft"
                : "ab-border-ab-line ab-bg-ab-surface"
            }`}
          >
            <span className="ab-font-mono ab-text-[11px] ab-font-bold ab-text-ab-mute">
              {w.id}
            </span>
            <span className="ab-hidden ab-w-48 ab-truncate ab-text-[12px] ab-text-ab-ink sm:ab-block">
              {w.name}
            </span>
            <div className="ab-flex ab-flex-1 ab-items-center ab-gap-1">
              {Array.from({ length: w.phases }).map((_, i) => (
                <span
                  key={i}
                  className={`ab-h-1.5 ab-flex-1 ab-rounded-full ${
                    i < w.phase
                      ? w.highlight
                        ? "ab-bg-ab-gold"
                        : "ab-bg-ab-cyan/60"
                      : "ab-bg-white/5"
                  }`}
                />
              ))}
            </div>
            {w.days ? (
              <span className="ab-shrink-0 ab-font-mono ab-text-[11px] ab-text-ab-gold">
                {w.daysBaseline}→{w.days} d
              </span>
            ) : (
              <span className="ab-hidden ab-shrink-0 ab-font-mono ab-text-[10px] ab-text-ab-faint md:ab-block">
                {w.state}
              </span>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function FlowsCard() {
  return (
    <Card className="ab-p-4">
      <SectionTitle kicker="§2.1 · 21 flujos intermodulares" title="Flujos críticos" />
      <div className="ab-flex ab-flex-col ab-gap-2">
        {FLOWS.map((f) => (
          <div
            key={f.id}
            className="ab-flex ab-items-center ab-gap-3 ab-rounded-lg ab-border ab-border-ab-line ab-bg-ab-surface ab-px-3 ab-py-2"
          >
            <span className="ab-font-mono ab-text-[11px] ab-font-bold ab-text-ab-cyan">
              {f.id}
            </span>
            <span className="ab-flex ab-items-center ab-gap-1.5 ab-font-mono ab-text-[11px] ab-text-ab-mute">
              <span className="ab-rounded ab-bg-white/5 ab-px-1.5 ab-py-px">{f.a}</span>
              <span className="ab-text-ab-faint">↔</span>
              <span className="ab-rounded ab-bg-white/5 ab-px-1.5 ab-py-px">{f.b}</span>
            </span>
            <span className="ab-flex-1 ab-truncate ab-text-[11.5px] ab-text-ab-mute">{f.t}</span>
            {f.crit && <Tag tone="high">crítico</Tag>}
          </div>
        ))}
      </div>
    </Card>
  );
}

function GovSummary({ onOpen }) {
  return (
    <Card interactive onClick={onOpen} className="ab-border-ab-high/20 ab-p-4">
      <SectionTitle
        kicker="Capa inviolable"
        title="Governance Layer"
        right={<StatusDot tone="high" pulse />}
      />
      <p className="ab-text-[12px] ab-leading-relaxed ab-text-ab-mute">
        {GOV_LAYER.foundational}
      </p>
      <div className="ab-mt-3 ab-grid ab-grid-cols-3 ab-gap-2">
        {[
          ["Reglas activas", GOV_LAYER.rulesActive],
          ["Pilares", GOV_LAYER.pillars],
          ["Skills Alto Riesgo", GOV_LAYER.highRiskSkills],
        ].map(([k, v]) => (
          <div key={k} className="ab-rounded-lg ab-border ab-border-ab-line ab-bg-ab-surface ab-p-2.5">
            <div className="ab-text-[20px] ab-font-extrabold ab-text-ab-ink">{v}</div>
            <div className="ab-text-[10px] ab-text-ab-faint">{k}</div>
          </div>
        ))}
      </div>
      <div className="ab-mt-3 ab-flex ab-flex-wrap ab-gap-1.5">
        {GOV_RULES.slice(0, 4).map((r) => (
          <span
            key={r.n}
            className="ab-rounded ab-border ab-border-ab-line ab-bg-ab-surface ab-px-2 ab-py-1 ab-text-[10.5px] ab-text-ab-mute"
          >
            #{r.n} {r.text.split(" ").slice(0, 4).join(" ")}…
          </span>
        ))}
      </div>
    </Card>
  );
}

export default function Workspace({ onOpenLayer, onOpenGov }) {
  return (
    <div className="ab-flex ab-flex-col ab-gap-5">
      <Hero />
      <KpiGrid />
      <div className="ab-grid ab-gap-5 xl:ab-grid-cols-2">
        <StatusBoard />
        <GovSummary onOpen={onOpenGov} />
      </div>
      <AgentGrid onOpen={onOpenLayer} />
      <div className="ab-grid ab-gap-5 xl:ab-grid-cols-2">
        <WorkflowStatus />
        <FlowsCard />
      </div>
    </div>
  );
}

export { RiskTag };
