// Formateadores es-EC para la herramienta de planificación tributaria.

const fmtCur = new Intl.NumberFormat("es-EC", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const fmtNum = new Intl.NumberFormat("es-EC", { maximumFractionDigits: 0 });

export const fmt = (n) => fmtCur.format(n);
export const f0 = (n) => fmtNum.format(n);
export const fX = (n, d = 2) => (isFinite(n) ? n.toFixed(d) + "x" : "—");
export const fP = (n, d = 1) => (isFinite(n) ? (n * 100).toFixed(d) + "%" : "—");
export const fD = (n) => (isFinite(n) ? Math.round(n) + " d" : "—");

// Moneda con paréntesis para negativos cuando neg=true; "-" para cero.
export const m = (x, neg) =>
  !isFinite(x)
    ? "—"
    : x === 0
      ? "-"
      : neg && x > 0
        ? "(" + fmtNum.format(x) + ")"
        : fmtCur.format(x);
