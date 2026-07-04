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

// Construye las filas de comparación de un estado.
//   data:   { key: [valores por período] }
//   labels: [etiqueta por período]  (labels_esf o labels_er)
//   pares:  [[actual, anterior], ...]  (comparaciones.esf o .eri del backend)
//   rubros: [[key, etiquetaVisible], ...]  (rubros del esquema a mostrar)
// Devuelve solo los rubros con algún valor no nulo, cada uno con una celda por par.
export function comparacionFilas(data, labels, pares, rubros) {
  const idx = (l) => labels.indexOf(l);
  const arrOf = (k) => (Array.isArray(data[k]) ? data[k] : []);
  return rubros
    .filter(([k]) => arrOf(k).some((v) => v))
    .map(([k, etiqueta]) => ({
      key: k,
      etiqueta,
      celdas: pares.map(([a, b]) => {
        const ia = idx(a);
        const ib = idx(b);
        const va = ia >= 0 ? arrOf(k)[ia] : null;
        const vb = ib >= 0 ? arrOf(k)[ib] : null;
        if (va == null || vb == null) return { par: [a, b], delta: null, pct: null };
        return { par: [a, b], delta: va - vb, pct: pctVar(va, vb) };
      }),
    }));
}
