import { motion } from "framer-motion";

export const RISK_TONE = { Alto: "high", Medio: "med", Bajo: "low" };

const TONE_CLASS = {
  high: "ab-text-ab-high ab-bg-ab-highsoft ab-border-ab-high/30",
  med: "ab-text-ab-med ab-bg-ab-medsoft ab-border-ab-med/30",
  low: "ab-text-ab-low ab-bg-ab-lowsoft ab-border-ab-low/30",
  cyan: "ab-text-ab-cyan ab-bg-ab-cyansoft ab-border-ab-cyan/30",
  gold: "ab-text-ab-gold ab-bg-ab-goldsoft ab-border-ab-gold/30",
  faint: "ab-text-ab-faint ab-bg-white/5 ab-border-ab-line2",
};

const DOT = {
  high: "ab-bg-ab-high",
  med: "ab-bg-ab-med",
  low: "ab-bg-ab-low",
  cyan: "ab-bg-ab-cyan",
  gold: "ab-bg-ab-gold",
  faint: "ab-bg-ab-faint",
};

export function StatusDot({ tone = "low", pulse = false }) {
  return (
    <span className="ab-relative ab-inline-flex ab-h-2 ab-w-2">
      {pulse && (
        <span
          className={`ab-absolute ab-inline-flex ab-h-full ab-w-full ab-rounded-full ${DOT[tone]} ab-opacity-60 ab-animate-abpulse`}
        />
      )}
      <span className={`ab-relative ab-inline-flex ab-h-2 ab-w-2 ab-rounded-full ${DOT[tone]}`} />
    </span>
  );
}

export function Tag({ tone = "faint", children, className = "" }) {
  return (
    <span
      className={`ab-inline-flex ab-items-center ab-gap-1.5 ab-rounded-full ab-border ab-px-2 ab-py-0.5 ab-text-[10px] ab-font-semibold ab-uppercase ab-tracking-wider ${TONE_CLASS[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function RiskTag({ level }) {
  const tone = RISK_TONE[level] || "faint";
  return (
    <Tag tone={tone}>
      <span className={`ab-h-1.5 ab-w-1.5 ab-rounded-full ${DOT[tone]}`} />
      {level}
    </Tag>
  );
}

export function Card({ children, className = "", interactive = false, ...rest }) {
  return (
    <motion.div
      initial={false}
      whileHover={interactive ? { y: -2 } : undefined}
      transition={{ type: "spring", stiffness: 320, damping: 26 }}
      className={`ab-rounded-xl ab-border ab-border-ab-line ab-bg-ab-surface ab-shadow-ab-card ${
        interactive ? "ab-cursor-pointer hover:ab-border-ab-line2" : ""
      } ${className}`}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

export function SectionTitle({ kicker, title, right }) {
  return (
    <div className="ab-mb-3 ab-flex ab-items-end ab-justify-between ab-gap-4">
      <div>
        {kicker && (
          <div className="ab-mb-1 ab-font-mono ab-text-[10px] ab-uppercase ab-tracking-[0.18em] ab-text-ab-faint">
            {kicker}
          </div>
        )}
        <h2 className="ab-text-[15px] ab-font-bold ab-tracking-tight ab-text-ab-ink">{title}</h2>
      </div>
      {right}
    </div>
  );
}

export function Sparkline({ points, tone = "cyan", w = 96, h = 28 }) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const span = max - min || 1;
  const step = w / (points.length - 1);
  const d = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${i * step} ${h - ((p - min) / span) * (h - 4) - 2}`)
    .join(" ");
  const stroke = { cyan: "#3FB6C9", gold: "#C8A24B", low: "#3DD68C", high: "#E5484D" }[tone];
  return (
    <svg width={w} height={h} className="ab-overflow-visible">
      <motion.path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.9, ease: "easeOut" }}
      />
    </svg>
  );
}

export function Progress({ pct, tone = "gold" }) {
  const c = { gold: "ab-bg-ab-gold", cyan: "ab-bg-ab-cyan", low: "ab-bg-ab-low", med: "ab-bg-ab-med", high: "ab-bg-ab-high" }[tone];
  return (
    <div className="ab-h-1.5 ab-w-full ab-overflow-hidden ab-rounded-full ab-bg-white/5">
      <motion.div
        className={`ab-h-full ab-rounded-full ${c}`}
        initial={{ width: 0 }}
        animate={{ width: `${Math.round(pct * 100)}%` }}
        transition={{ duration: 0.8, ease: "easeOut" }}
      />
    </div>
  );
}
