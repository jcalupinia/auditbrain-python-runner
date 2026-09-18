/**
 * Calcula la cartera medida: total menos lo sin medir menos lo sin estratificar.
 * @param {number} total - Cartera total según los estados financieros
 * @param {number} sinMedir - Exposición sin medir (sin tasa histórica en su banda)
 * @param {number} sinEstratificar - Exposición sin estratificar (no aparece en el archivo de antigüedad)
 * @returns {number|null} Cartera medida, o null si total es null
 */
export function carteraMedida(total, sinMedir = 0, sinEstratificar = 0) {
  if (total == null) return null;
  return total - sinMedir - sinEstratificar;
}
