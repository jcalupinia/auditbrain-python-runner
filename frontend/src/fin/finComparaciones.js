// Cálculo de comparaciones período-a-período para el dashboard FIN.
//
// Usa el resultado CRUDO del backend (data por período + labels + pares de
// comparación), NO el dataset fusionado por año — la fusión anual colapsa los
// cortes parciales (p.ej. may-25 y el cierre 2025 comparten año) y perdería la
// comparación parcial-vs-parcial. Aquí cada rubro se indexa por su propia lista
// de etiquetas (labels_esf para el balance, labels_er para resultados).

// Variación porcentual a/b. Devuelve null si la base es 0 o falta un valor
// (evita Infinity/NaN en pantalla).
export function pctVar(a, b) {
  if (a == null || b == null || b === 0) return null;
  return ((a - b) / Math.abs(b)) * 100;
}

// Construye los pares de comparación del ESTADO DE RESULTADOS (flujo), aplicando
// la ANUALIZACIÓN DE RESPALDO: se compara parcial-vs-parcial (may-26 vs may-25),
// pero si hay un único corte parcial sin su comparable del año anterior, se
// compara contra el anual inmediato previo PRORRATEADO ×(meses/12). Luego los
// anuales encadenados (2025 vs 2024, 2024 vs 2023). Nunca cruza 5m con 12m sin prorratear.
// Cada par: [actual, anterior, factorAnterior?, etiqueta?].
export function construirParesEri(periodosEri) {
  const per = periodosEri || [];
  const parciales = per.filter((p) => p.tipo === "parcial");
  const anuales = per.filter((p) => p.tipo === "anual").slice().sort((a, b) => b.anio - a.anio);
  const pares = [];
  if (parciales.length >= 2) {
    for (let i = 0; i < parciales.length - 1; i++) pares.push([parciales[i].label, parciales[i + 1].label]);
  } else if (parciales.length === 1) {
    const p = parciales[0];
    const prev = anuales.filter((a) => a.anio < p.anio)[0]; // anual del año anterior
    if (prev) {
      const f = (p.meses || 12) / 12;
      pares.push([p.label, prev.label, f, `Δ ${p.label} vs ${prev.label} (anualizado ×${p.meses}/12)`]);
    }
  }
  for (let i = 0; i < anuales.length - 1; i++) pares.push([anuales[i].label, anuales[i + 1].label]);
  return pares;
}

// Construye las filas de comparación de un estado.
//   data:   { key: [valores por período] }
//   labels: [etiqueta por período]  (labels_esf o labels_er)
//   pares:  [[actual, anterior, factorAnterior?, etiqueta?], ...]
//   rubros: [[key, etiquetaVisible], ...]  (rubros del esquema a mostrar)
// factorAnterior escala el valor del período anterior (anualización de respaldo).
// Devuelve solo los rubros con algún valor no nulo, cada uno con una celda por par.
export function comparacionFilas(data, labels, pares, rubros) {
  const idx = (l) => labels.indexOf(l);
  const arrOf = (k) => (Array.isArray(data[k]) ? data[k] : []);
  return rubros
    .filter(([k]) => arrOf(k).some((v) => v))
    .map(([k, etiqueta]) => ({
      key: k,
      etiqueta,
      celdas: pares.map((par) => {
        const [a, b, factorB] = par;
        const f = factorB || 1;
        const ia = idx(a);
        const ib = idx(b);
        const va = ia >= 0 ? arrOf(k)[ia] : null;
        const vb = ib >= 0 ? arrOf(k)[ib] * f : null;
        if (va == null || vb == null) return { par, delta: null, pct: null };
        return { par, delta: va - vb, pct: pctVar(va, vb) };
      }),
    }));
}
