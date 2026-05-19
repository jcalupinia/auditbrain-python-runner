/** AuditBrain Command Center — Tailwind aislado.
 *  prefix "ab-" + preflight OFF => no toca el frontend legacy. */
export default {
  prefix: "ab-",
  important: "#ab-os",
  corePlugins: { preflight: false },
  content: ["./src/command-center/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ab: {
          bg: "#0A0B0D",
          surface: "#121418",
          surface2: "#1A1D23",
          surface3: "#22262E",
          line: "rgba(255,255,255,0.06)",
          line2: "rgba(255,255,255,0.10)",
          ink: "#EAECEF",
          mute: "#9AA1AD",
          faint: "#5C6470",
          gold: "#C8A24B",
          goldsoft: "rgba(200,162,75,0.14)",
          cyan: "#3FB6C9",
          cyansoft: "rgba(63,182,201,0.14)",
          high: "#E5484D",
          highsoft: "rgba(229,72,77,0.14)",
          med: "#E5A23D",
          medsoft: "rgba(229,162,61,0.14)",
          low: "#3DD68C",
          lowsoft: "rgba(61,214,140,0.14)",
        },
      },
      fontFamily: {
        sans: ['"Inter"', '"Segoe UI"', "system-ui", "sans-serif"],
        display: ['"Inter"', '"Segoe UI"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', '"SFMono-Regular"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        "ab-card": "0 1px 0 rgba(255,255,255,0.03) inset, 0 8px 30px rgba(0,0,0,0.45)",
        "ab-glow": "0 0 0 1px rgba(200,162,75,0.35), 0 0 24px rgba(200,162,75,0.10)",
      },
      keyframes: {
        abpulse: {
          "0%,100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.45", transform: "scale(0.82)" },
        },
        abscan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
      },
      animation: {
        abpulse: "abpulse 1.8s ease-in-out infinite",
        abscan: "abscan 3.4s linear infinite",
      },
    },
  },
  plugins: [],
};
