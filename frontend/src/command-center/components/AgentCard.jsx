import { motion } from "framer-motion";
import { AGENT_STATE, STATUS_TONE } from "../data/mock.js";
import { Card, Sparkline, StatusDot, Tag } from "./ui.jsx";

const STATE_RING = {
  idle: "ab-border-ab-line",
  thinking: "ab-border-ab-cyan/40",
  producing: "ab-border-ab-gold/40",
  awaiting: "ab-border-ab-high/45",
};

export default function AgentCard({ l, onOpen }) {
  const st = AGENT_STATE[l.agent];
  const pct =
    l.skills.total == null ? null : Math.round((l.skills.done / l.skills.total) * 100);

  return (
    <Card
      interactive
      onClick={onOpen}
      className={`ab-relative ab-overflow-hidden ab-border ${STATE_RING[l.agent]} ab-p-4`}
    >
      {l.agent === "producing" && (
        <span className="ab-pointer-events-none ab-absolute ab-inset-x-0 ab-top-0 ab-h-px ab-bg-gradient-to-r ab-from-transparent ab-via-ab-gold/50 ab-to-transparent ab-animate-abscan" />
      )}
      <div className="ab-flex ab-items-start ab-justify-between ab-gap-2">
        <div className="ab-flex ab-items-center ab-gap-2.5">
          <span className="ab-grid ab-h-9 ab-w-11 ab-place-items-center ab-rounded-lg ab-border ab-border-ab-line ab-bg-ab-surface2 ab-font-mono ab-text-[11px] ab-font-bold ab-text-ab-gold">
            {l.code === "ROUTER" ? "RTR" : l.code}
          </span>
          <div className="ab-min-w-0">
            <div className="ab-truncate ab-text-[13px] ab-font-bold ab-text-ab-ink">
              {l.name}
            </div>
            <div className="ab-font-mono ab-text-[10px] ab-text-ab-faint">
              Capa {l.num} · {l.code}
            </div>
          </div>
        </div>
        <StatusDot tone={STATUS_TONE[l.status]} pulse={l.agent === "awaiting"} />
      </div>

      <p className="ab-mt-3 ab-h-8 ab-text-[11.5px] ab-leading-snug ab-text-ab-mute">
        {l.desc}
      </p>

      <div className="ab-mt-3 ab-flex ab-items-center ab-justify-between">
        <Tag tone={st.tone}>
          <motion.span
            className={`ab-h-1.5 ab-w-1.5 ab-rounded-full ${
              { faint: "ab-bg-ab-faint", cyan: "ab-bg-ab-cyan", gold: "ab-bg-ab-gold", high: "ab-bg-ab-high" }[
                st.tone
              ]
            }`}
            animate={l.agent === "idle" ? {} : { opacity: [1, 0.3, 1] }}
            transition={{ duration: 1.6, repeat: Infinity }}
          />
          {st.label}
        </Tag>
        <Sparkline points={l.spark} tone={l.agent === "awaiting" ? "high" : "cyan"} />
      </div>

      <div className="ab-mt-3 ab-border-t ab-border-ab-line ab-pt-3">
        <div className="ab-flex ab-items-center ab-justify-between ab-text-[11px]">
          <span className="ab-text-ab-faint">Skills</span>
          <span className="ab-font-mono ab-text-ab-mute">
            {l.skills.total == null ? "autónoma" : `${l.skills.done}/${l.skills.total} · ${l.skills.ids}`}
          </span>
        </div>
        {pct != null && (
          <div className="ab-mt-1.5 ab-h-1 ab-w-full ab-overflow-hidden ab-rounded-full ab-bg-white/5">
            <div
              className={`ab-h-full ab-rounded-full ${
                pct === 100 ? "ab-bg-ab-low" : "ab-bg-ab-med"
              }`}
              style={{ width: `${pct}%` }}
            />
          </div>
        )}
        <div className="ab-mt-2.5 ab-flex ab-items-center ab-gap-1.5 ab-text-[11px] ab-text-ab-mute">
          <span className="ab-text-ab-faint">Último:</span>
          <span className="ab-truncate">{l.deliverable}</span>
        </div>
      </div>
    </Card>
  );
}
