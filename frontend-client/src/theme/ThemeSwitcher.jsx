import { useState, useRef, useEffect } from "react";
import { THEMES, useTheme } from "./useTheme.js";
import "./theme-switcher.css";

/** Selector flotante de tema de fondo. Se monta una sola vez (global) y
 *  aparece en todas las pantallas del portal. Botón discreto que despliega
 *  los swatches de color; la elección persiste por dispositivo. */
export default function ThemeSwitcher() {
  const [theme, setTheme] = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onEsc = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  const current = THEMES.find((t) => t.id === theme) || THEMES[0];

  return (
    <div className="ab-theme" ref={ref}>
      {open && (
        <div className="ab-theme-pop" role="menu" aria-label="Color de fondo">
          <div className="ab-theme-title">Color de fondo</div>
          <div className="ab-theme-grid">
            {THEMES.map((t) => (
              <button
                key={t.id}
                type="button"
                role="menuitemradio"
                aria-checked={t.id === theme}
                className={`ab-theme-opt${t.id === theme ? " on" : ""}`}
                onClick={() => { setTheme(t.id); setOpen(false); }}
                title={t.label}
              >
                <span
                  className="ab-theme-dot"
                  style={{ background: t.swatch, borderColor: t.ring }}
                />
                <span className="ab-theme-name">{t.label}</span>
                {t.id === theme && <span className="ab-theme-check">✓</span>}
              </button>
            ))}
          </div>
        </div>
      )}
      <button
        type="button"
        className="ab-theme-fab"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="true"
        aria-expanded={open}
        title="Cambiar color de fondo"
      >
        <span
          className="ab-theme-fab-dot"
          style={{ background: current.swatch, borderColor: current.ring }}
        />
        <span className="ab-theme-fab-txt">Tema</span>
      </button>
    </div>
  );
}
