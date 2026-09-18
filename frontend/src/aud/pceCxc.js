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

/**
 * Fecha de emisión del papel de trabajo (AAAA-MM-DD, hora local del preparador).
 *
 * Viaja con los parámetros de la corrida y se guarda junto con ella, así que el
 * Excel la imprime desde ahí en vez de poner la fecha del día de la descarga:
 * dos descargas de la misma corrida dan el mismo papel.
 * @param {Date} [ahora] - Momento de la emisión; por defecto, ahora.
 * @returns {string} Fecha en formato AAAA-MM-DD
 */
export function fechaEmision(ahora = new Date()) {
  const anio = ahora.getFullYear();
  const mes = String(ahora.getMonth() + 1).padStart(2, "0");
  const dia = String(ahora.getDate()).padStart(2, "0");
  return `${anio}-${mes}-${dia}`;
}
