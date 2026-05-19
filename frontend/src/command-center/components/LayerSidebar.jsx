import { motion } from "framer-motion";
import { LAYERS, GOV_LAYER, STATUS_TONE } from "../data/mock.js";
import { StatusDot } from "./ui.jsx";

function SkillBadge({ skills }) {
  if (skills.total == null)
    return <span className="ab-font-mono ab-text-[10px] ab-text-ab-faint">autónoma</span>;
  const full = skills.done === skills.total;
  return (
    <span
      className={`ab-font-mono ab-text-[10px] ab-tabular-nums ${
        full ? "ab-text-ab-low" : "ab-text-ab-med"
      }`}
    >
      {skills.done}/{skills.total}
    </span>
  );
}

function LayerRow({ l, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`ab-group ab-relative ab-flex ab-w-full ab-items-center ab-gap-2.5 ab-rounded-lg ab-px-2.5 ab-py-2 ab-text-left ab-transition-colors ${
        active ? "ab-bg-white/[0.06]" : "hover:ab-bg-white/[0.035]"
      }`}
    >
      {active && (
        <motion.span
          layoutId="ab-nav-active"
          className="ab-absolute ab-left-0 ab-top-1/2 ab-h-5 ab--translate-y-1/2 ab-w-[3px] ab-rounded-r ab-bg-ab-gold"
          transition={{ type: "spring", stiffness: 400, damping: 32 }}
        />
      )}
      <span
        className={`ab-grid ab-h-7 ab-w-9 ab-shrink-0 ab-place-items-center ab-rounded-md ab-border ab-font-mono ab-text-[10px] ab-font-bold ${
          active
            ? "ab-border-ab-gold/40 ab-bg-ab-goldsoft ab-text-ab-gold"
            : "ab-border-ab-line ab-bg-ab-surface ab-text-ab-mute group-hover:ab-text-ab-ink"
        }`}
      >
        {l.code === "ROUTER" ? "RTR" : l.code}
      </span>
      <span className="ab-min-w-0 ab-flex-1">
        <span
          className={`ab-block ab-truncate ab-text-[12.5px] ab-font-semibold ${
            active ? "ab-text-ab-ink" : "ab-text-ab-mute group-hover:ab-text-ab-ink"
          }`}
        >
          {l.name}
        </span>
        <span className="ab-block ab-truncate ab-text-[10.5px] ab-text-ab-faint">{l.short}</span>
      </span>
      <span className="ab-flex ab-shrink-0 ab-flex-col ab-items-end ab-gap-1">
        <StatusDot tone={STATUS_TONE[l.status]} pulse={l.agent === "awaiting"} />
        <SkillBadge skills={l.skills} />
      </span>
    </button>
  );
}

export default function LayerSidebar({ section, onSelect, open, onClose }) {
  return (
    <>
      {open && (
        <div
          className="ab-fixed ab-inset-0 ab-z-30 ab-bg-black/60 ab-backdrop-blur-sm lg:ab-hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`ab-fixed ab-z-40 ab-flex ab-h-[calc(100vh-3.5rem)] ab-w-[264px] ab-flex-col ab-border-r ab-border-ab-line ab-bg-ab-bg/95 ab-transition-transform lg:ab-static lg:ab-z-0 lg:ab-translate-x-0 ${
          open ? "ab-translate-x-0" : "ab--translate-x-full"
        }`}
      >
        <div className="ab-flex ab-min-h-0 ab-flex-1 ab-flex-col ab-overflow-y-auto ab-px-3 ab-py-4">
          <button
            onClick={() => onSelect("overview")}
            className={`ab-mb-3 ab-flex ab-items-center ab-gap-2.5 ab-rounded-lg ab-border ab-px-3 ab-py-2.5 ab-text-left ${
              section === "overview"
                ? "ab-border-ab-gold/40 ab-bg-ab-goldsoft"
                : "ab-border-ab-line ab-bg-ab-surface hover:ab-border-ab-line2"
            }`}
          >
            <span className="ab-text-base">◆</span>
            <span>
              <span className="ab-block ab-text-[12.5px] ab-font-bold ab-text-ab-ink">
                Executive Overview
              </span>
              <span className="ab-block ab-text-[10.5px] ab-text-ab-faint">
                Centro de operaciones IA
              </span>
            </span>
          </button>

          <div className="ab-mb-1.5 ab-px-1 ab-font-mono ab-text-[10px] ab-uppercase ab-tracking-[0.16em] ab-text-ab-faint">
            11 capas operativas
          </div>
          <nav className="ab-flex ab-flex-col ab-gap-0.5">
            {LAYERS.map((l) => (
              <LayerRow
                key={l.code}
                l={l}
                active={section === l.code}
                onClick={() => onSelect(l.code)}
              />
            ))}
          </nav>

          <div className="ab-mt-4 ab-mb-1.5 ab-px-1 ab-font-mono ab-text-[10px] ab-uppercase ab-tracking-[0.16em] ab-text-ab-faint">
            Gobernanza · inviolable
          </div>
          <button
            onClick={() => onSelect("GOV")}
            className={`ab-relative ab-flex ab-w-full ab-items-center ab-gap-2.5 ab-rounded-lg ab-border ab-px-2.5 ab-py-2.5 ab-text-left ${
              section === "GOV"
                ? "ab-border-ab-high/40 ab-bg-ab-highsoft"
                : "ab-border-ab-line ab-bg-ab-surface hover:ab-border-ab-line2"
            }`}
          >
            <span className="ab-grid ab-h-7 ab-w-9 ab-shrink-0 ab-place-items-center ab-rounded-md ab-border ab-border-ab-high/30 ab-bg-ab-highsoft ab-text-ab-high">
              ⛉
            </span>
            <span className="ab-min-w-0 ab-flex-1">
              <span className="ab-block ab-text-[12.5px] ab-font-bold ab-text-ab-ink">
                Governance Layer
              </span>
              <span className="ab-block ab-truncate ab-text-[10.5px] ab-text-ab-faint">
                {GOV_LAYER.rulesActive} reglas · {GOV_LAYER.pillars} pilares
              </span>
            </span>
            <StatusDot tone="high" pulse />
          </button>

          <div className="ab-mt-auto ab-pt-4">
            <div className="ab-rounded-lg ab-border ab-border-ab-line ab-bg-ab-surface ab-p-3">
              <div className="ab-font-mono ab-text-[10px] ab-uppercase ab-tracking-wider ab-text-ab-faint">
                Audit Trail
              </div>
              <div className="ab-mt-1 ab-text-[11px] ab-leading-snug ab-text-ab-mute">
                Cada acción del sistema queda registrada — inviolable (Regla #5).
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
