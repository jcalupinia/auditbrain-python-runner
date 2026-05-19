import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { META } from "../data/mock.js";
import { StatusDot } from "./ui.jsx";

const ROLES = ["Socio", "Manager", "Viewer"];

export default function Topbar({ onToggleNav, onToggleActivity }) {
  const [role, setRole] = useState("Socio");
  const [open, setOpen] = useState(false);

  return (
    <header className="ab-sticky ab-top-0 ab-z-30 ab-flex ab-h-14 ab-items-center ab-justify-between ab-gap-3 ab-border-b ab-border-ab-line ab-bg-ab-bg/85 ab-px-3 ab-backdrop-blur-md sm:ab-px-5">
      <div className="ab-flex ab-items-center ab-gap-3">
        <button
          onClick={onToggleNav}
          className="ab-grid ab-h-8 ab-w-8 ab-place-items-center ab-rounded-lg ab-border ab-border-ab-line ab-text-ab-mute hover:ab-text-ab-ink lg:ab-hidden"
          aria-label="Capas"
        >
          ☰
        </button>
        <div className="ab-flex ab-items-center ab-gap-2.5">
          <div className="ab-grid ab-h-8 ab-w-8 ab-place-items-center ab-rounded-lg ab-bg-gradient-to-br ab-from-ab-gold ab-to-[#8a6f2e] ab-text-[13px] ab-font-extrabold ab-text-black ab-shadow-ab-glow">
            AB
          </div>
          <div className="ab-leading-tight">
            <div className="ab-text-[13px] ab-font-bold ab-tracking-tight ab-text-ab-ink">
              AuditBrain <span className="ab-text-ab-gold">Executive&nbsp;OS</span>
            </div>
            <div className="ab-hidden ab-font-mono ab-text-[10px] ab-tracking-wide ab-text-ab-faint sm:ab-block">
              {META.org}
            </div>
          </div>
        </div>
      </div>

      <div className="ab-flex ab-items-center ab-gap-2 sm:ab-gap-3">
        <div className="ab-hidden ab-items-center ab-gap-2 ab-rounded-full ab-border ab-border-ab-line ab-bg-ab-surface ab-px-3 ab-py-1 md:ab-flex">
          <StatusDot tone="low" pulse />
          <span className="ab-font-mono ab-text-[11px] ab-text-ab-mute">
            Plataforma operativa · 446 tests · 0 failed
          </span>
        </div>
        <div className="ab-hidden ab-rounded-full ab-border ab-border-ab-line ab-bg-ab-surface ab-px-3 ab-py-1 ab-font-mono ab-text-[11px] ab-text-ab-mute lg:ab-block">
          {META.version} · {META.phase}
        </div>

        <div className="ab-relative">
          <button
            onClick={() => setOpen((o) => !o)}
            className="ab-flex ab-items-center ab-gap-2 ab-rounded-full ab-border ab-border-ab-line ab-bg-ab-surface ab-py-1 ab-pl-1 ab-pr-2.5"
          >
            <span className="ab-grid ab-h-6 ab-w-6 ab-place-items-center ab-rounded-full ab-bg-ab-surface3 ab-text-[11px] ab-font-bold ab-text-ab-gold">
              {role[0]}
            </span>
            <span className="ab-hidden ab-text-xs ab-font-semibold ab-text-ab-ink sm:ab-block">{role}</span>
            <span className="ab-text-[9px] ab-text-ab-faint">▾</span>
          </button>
          <AnimatePresence>
            {open && (
              <motion.div
                initial={{ opacity: 0, y: -6, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.97 }}
                transition={{ duration: 0.14 }}
                className="ab-absolute ab-right-0 ab-mt-2 ab-w-44 ab-overflow-hidden ab-rounded-xl ab-border ab-border-ab-line ab-bg-ab-surface2 ab-shadow-ab-card"
              >
                <div className="ab-border-b ab-border-ab-line ab-px-3 ab-py-2 ab-font-mono ab-text-[10px] ab-uppercase ab-tracking-wider ab-text-ab-faint">
                  Rol (RBAC)
                </div>
                {ROLES.map((r) => (
                  <button
                    key={r}
                    onClick={() => {
                      setRole(r);
                      setOpen(false);
                    }}
                    className={`ab-flex ab-w-full ab-items-center ab-justify-between ab-px-3 ab-py-2 ab-text-xs hover:ab-bg-white/5 ${
                      r === role ? "ab-text-ab-gold" : "ab-text-ab-mute"
                    }`}
                  >
                    {r}
                    {r === role && <span>✓</span>}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <button
          onClick={onToggleActivity}
          className="ab-grid ab-h-8 ab-w-8 ab-place-items-center ab-rounded-lg ab-border ab-border-ab-line ab-text-ab-mute hover:ab-text-ab-ink xl:ab-hidden"
          aria-label="Actividad"
        >
          ◰
        </button>
      </div>
    </header>
  );
}
