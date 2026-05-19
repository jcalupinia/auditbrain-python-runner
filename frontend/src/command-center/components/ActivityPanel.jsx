import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AUDIT_TRAIL, LAYERS, APPROVAL_QUEUE, GRUPO_002 } from "../data/mock.js";
import { RiskTag, StatusDot } from "./ui.jsx";

const ACTIVE = LAYERS.filter((l) => l.agent === "producing" || l.agent === "awaiting");

function useLiveTrail() {
  const [items, setItems] = useState(AUDIT_TRAIL);
  useEffect(() => {
    const id = setInterval(() => {
      setItems((prev) => {
        const head = prev[prev.length - 1];
        const now = new Date();
        const t = now.toLocaleTimeString("es", { hour12: false });
        return [{ ...head, t, _k: now.getTime() }, ...prev].slice(0, 9);
      });
    }, 6000);
    return () => clearInterval(id);
  }, []);
  return items;
}

function Block({ title, children }) {
  return (
    <div className="ab-border-b ab-border-ab-line ab-px-4 ab-py-3.5 last:ab-border-0">
      <div className="ab-mb-2.5 ab-flex ab-items-center ab-justify-between">
        <span className="ab-font-mono ab-text-[10px] ab-uppercase ab-tracking-[0.16em] ab-text-ab-faint">
          {title}
        </span>
      </div>
      {children}
    </div>
  );
}

export default function ActivityPanel({ open, onClose }) {
  const trail = useLiveTrail();
  return (
    <>
      {open && (
        <div
          className="ab-fixed ab-inset-0 ab-z-30 ab-bg-black/60 ab-backdrop-blur-sm xl:ab-hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`ab-fixed ab-right-0 ab-z-40 ab-flex ab-h-[calc(100vh-3.5rem)] ab-w-[320px] ab-flex-col ab-overflow-y-auto ab-border-l ab-border-ab-line ab-bg-ab-bg/95 ab-transition-transform xl:ab-static xl:ab-z-0 xl:ab-translate-x-0 ${
          open ? "ab-translate-x-0" : "ab-translate-x-full"
        }`}
      >
        <div className="ab-flex ab-items-center ab-justify-between ab-border-b ab-border-ab-line ab-px-4 ab-py-3">
          <div className="ab-flex ab-items-center ab-gap-2">
            <StatusDot tone="cyan" pulse />
            <span className="ab-text-[12px] ab-font-bold ab-text-ab-ink">Activity Stream</span>
          </div>
          <button
            onClick={onClose}
            className="ab-text-ab-faint hover:ab-text-ab-ink xl:ab-hidden"
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>

        <Block title={`Agentes activos · ${ACTIVE.length}`}>
          <div className="ab-flex ab-flex-col ab-gap-2">
            {ACTIVE.map((a) => (
              <div key={a.code} className="ab-flex ab-items-center ab-gap-2.5">
                <span className="ab-grid ab-h-6 ab-w-8 ab-place-items-center ab-rounded ab-border ab-border-ab-line ab-bg-ab-surface ab-font-mono ab-text-[10px] ab-font-bold ab-text-ab-mute">
                  {a.code === "ROUTER" ? "RTR" : a.code}
                </span>
                <span className="ab-flex-1 ab-truncate ab-text-[11.5px] ab-text-ab-mute">
                  {a.name}
                </span>
                <span
                  className={`ab-font-mono ab-text-[10px] ${
                    a.agent === "awaiting" ? "ab-text-ab-high" : "ab-text-ab-gold"
                  }`}
                >
                  {a.agent === "awaiting" ? "aprobación" : "generando"}
                </span>
              </div>
            ))}
          </div>
        </Block>

        <Block title={`Governance alerts · ${APPROVAL_QUEUE.length}`}>
          <div className="ab-flex ab-flex-col ab-gap-2">
            {APPROVAL_QUEUE.map((q) => (
              <div
                key={q.id}
                className="ab-rounded-lg ab-border ab-border-ab-high/20 ab-bg-ab-highsoft ab-px-2.5 ab-py-2"
              >
                <div className="ab-flex ab-items-center ab-justify-between ab-gap-2">
                  <span className="ab-font-mono ab-text-[10px] ab-text-ab-high">{q.id}</span>
                  <RiskTag level={q.risk} />
                </div>
                <div className="ab-mt-1 ab-text-[11.5px] ab-leading-snug ab-text-ab-ink">
                  {q.title}
                </div>
                <div className="ab-mt-1 ab-flex ab-items-center ab-justify-between ab-font-mono ab-text-[10px] ab-text-ab-faint">
                  <span>{q.owner}</span>
                  <span>SLA {q.sla}</span>
                </div>
              </div>
            ))}
          </div>
        </Block>

        <Block title="Audit Trail · preview">
          <div className="ab-relative ab-flex ab-flex-col">
            <span className="ab-absolute ab-left-[5px] ab-top-1 ab-bottom-1 ab-w-px ab-bg-ab-line" />
            <AnimatePresence initial={false}>
              {trail.map((e, i) => (
                <motion.div
                  key={e._k ? `${e._k}` : `${e.t}-${i}`}
                  layout
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.25 }}
                  className="ab-relative ab-mb-3 ab-pl-5 last:ab-mb-0"
                >
                  <span
                    className={`ab-absolute ab-left-0 ab-top-1 ab-h-[11px] ab-w-[11px] ab-rounded-full ab-border-2 ab-border-ab-bg ${
                      e.risk === "Alto"
                        ? "ab-bg-ab-high"
                        : e.risk === "Medio"
                        ? "ab-bg-ab-med"
                        : "ab-bg-ab-low"
                    }`}
                  />
                  <div className="ab-flex ab-items-center ab-gap-2 ab-font-mono ab-text-[10px] ab-text-ab-faint">
                    <span>{e.t}</span>
                    <span className="ab-rounded ab-bg-white/5 ab-px-1.5 ab-py-px ab-text-ab-mute">
                      {e.layer}
                    </span>
                  </div>
                  <div className="ab-mt-0.5 ab-text-[11.5px] ab-leading-snug ab-text-ab-mute">
                    {e.evt}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </Block>

        <Block title="Caso de referencia">
          <div className="ab-rounded-lg ab-border ab-border-ab-line ab-bg-ab-surface ab-p-3">
            <div className="ab-flex ab-items-center ab-justify-between">
              <span className="ab-text-[13px] ab-font-bold ab-text-ab-ink">{GRUPO_002.name}</span>
              <span className="ab-font-mono ab-text-[11px] ab-text-ab-gold">
                {GRUPO_002.exposure}
              </span>
            </div>
            <div className="ab-mt-1 ab-text-[11px] ab-leading-snug ab-text-ab-mute">
              {GRUPO_002.status}
            </div>
            <div className="ab-mt-2 ab-flex ab-flex-wrap ab-gap-1">
              {GRUPO_002.entities.map((x) => (
                <span
                  key={x.e}
                  className="ab-rounded ab-border ab-border-ab-line ab-bg-ab-surface2 ab-px-1.5 ab-py-0.5 ab-font-mono ab-text-[10px] ab-text-ab-mute"
                >
                  {x.e}
                </span>
              ))}
            </div>
          </div>
        </Block>
      </aside>
    </>
  );
}
