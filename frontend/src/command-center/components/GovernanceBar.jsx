import { GOV_LAYER, APPROVAL_QUEUE } from "../data/mock.js";
import { StatusDot } from "./ui.jsx";

export default function GovernanceBar({ onOpen }) {
  return (
    <button
      onClick={onOpen}
      className="ab-z-20 ab-flex ab-h-9 ab-w-full ab-items-center ab-gap-4 ab-overflow-x-auto ab-border-t ab-border-ab-line ab-bg-ab-bg/90 ab-px-3 ab-text-left ab-backdrop-blur-md sm:ab-px-5"
    >
      <span className="ab-flex ab-shrink-0 ab-items-center ab-gap-2">
        <span className="ab-text-ab-high">⛉</span>
        <span className="ab-text-[11px] ab-font-bold ab-text-ab-ink">Governance Layer</span>
      </span>
      <span className="ab-flex ab-shrink-0 ab-items-center ab-gap-1.5 ab-font-mono ab-text-[11px] ab-text-ab-mute">
        <StatusDot tone="low" /> {GOV_LAYER.rulesActive} reglas activas
      </span>
      <span className="ab-shrink-0 ab-font-mono ab-text-[11px] ab-text-ab-mute">
        {GOV_LAYER.pillars} pilares
      </span>
      <span className="ab-flex ab-shrink-0 ab-items-center ab-gap-1.5 ab-font-mono ab-text-[11px] ab-text-ab-high">
        <StatusDot tone="high" pulse /> Cola aprobación: {APPROVAL_QUEUE.length}
      </span>
      <span className="ab-shrink-0 ab-font-mono ab-text-[11px] ab-text-ab-med">
        Escalamiento: {GOV_LAYER.currentEscalation}/N{GOV_LAYER.escalationLevels}
      </span>
      <span className="ab-ml-auto ab-hidden ab-shrink-0 ab-font-mono ab-text-[10px] ab-text-ab-faint md:ab-block">
        defensible · directorio · regulador · auditor · ética →
      </span>
    </button>
  );
}
