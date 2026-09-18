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

/**
 * Filas de la matriz que dicen algo.
 *
 * El servicio inicializa todas las bandas para los dos segmentos, así que la
 * mayoría de las combinaciones sale con exposición 0,00 y sin tasa. Esa fila no
 * es una pérdida cero medida (no hay tasa) ni una banda sin medir con cartera
 * (no hay exposición): es una combinación que no existe, y pintarla «sin medir»
 * diluye la señal de las bandas que sí tienen saldo sin medir.
 * @param {Array} tramos - Tramos de `matriz.tramos`
 * @returns {Array} Solo los tramos con exposición o con tasa
 */
export function tramosVisibles(tramos) {
  return (tramos || []).filter(
    (t) => Math.abs(Number(t.exposicion) || 0) > 0.005 || t.tasa_perdida != null
  );
}

/**
 * Parámetros que viajan con los tres cortes y quedan guardados con la corrida.
 *
 * `mayor_provision` es una declaración del auditor, no un archivo: el endpoint
 * `/analizar` exige exactamente tres archivos (los tres análisis de antigüedad)
 * y el servicio solo comprueba que el dato esté presente. Vacío, el pendiente
 * «Mayores de la provisión de los tres ejercicios» se dispara, que es lo
 * correcto mientras la evidencia no exista.
 * @param {object} datos - Campos del formulario
 * @param {string[]} fechas - Las tres fechas de corte, en el orden de los archivos
 * @param {number|null} projectId - Proyecto al que se imputa la corrida
 * @param {Date} [ahora] - Momento de la emisión
 * @returns {object} Parámetros para `pceCxcAnalizar`
 */
export function parametrosDeLaCorrida(datos, fechas, projectId, ahora = new Date()) {
  return {
    project_id: projectId ?? null,
    entidad: datos.entidad,
    fechas,
    // Se guarda con la corrida para que el Excel imprima la fecha de emisión
    // y no la del día en que se descargue el papel.
    fecha_emision: fechaEmision(ahora),
    umbral_dias_incumplimiento: Number(datos.umbral_dias) || 730,
    umbral_individual: Number(datos.umbral_individual) || 0,
    materialidad: Number(datos.materialidad) || 0,
    mayor_provision: String(datos.mayor_provision || "").trim(),
    eeff: {
      no_relacionados: Number(datos.eeff_nr) || 0,
      relacionados: Number(datos.eeff_r) || 0,
    },
  };
}

/**
 * Cartera efectivamente medida, tal como la calculó el motor.
 *
 * `exposicion.medida` es `exposicion_medida` de `motor.resumen_deterioro`: la
 * cartera estratificada menos lo que no se pudo medir (bandas sin tasa y
 * saldos individuales sin tasa). Se prefiere esa cifra a recalcularla aquí
 * para que la pantalla, el papel y la base digan lo mismo. Las corridas
 * anteriores a ese campo se reconstruyen desde la exposición.
 * @param {object|null} resultado - Resultado de `analizar`
 * @returns {number|null} Cartera medida, o null si todavía no hay resultado
 */
export function carteraMedidaDe(resultado) {
  const exposicion = resultado?.exposicion;
  if (!exposicion) return null;
  if (exposicion.medida != null) return exposicion.medida;
  return carteraMedida(
    exposicion.total,
    exposicion.sin_medir ?? 0,
    exposicion.sin_estratificar ?? 0
  );
}

/**
 * Cobertura de la pérdida esperada SOBRE LO MEDIDO.
 *
 * Es `porcentaje_sobre_cartera` del motor: dividir entre la cartera total
 * diluiría el porcentaje justo cuando hay algo sin medir.
 * @param {object|null} resultado - Resultado de `analizar`
 * @returns {number|null} Cobertura, o null si no se puede calcular
 */
export function coberturaDe(resultado) {
  if (resultado?.porcentaje_sobre_cartera != null) return resultado.porcentaje_sobre_cartera;
  const medida = carteraMedidaDe(resultado);
  if (medida == null || medida <= 0.005) return null;
  return (resultado?.ecl_total ?? 0) / medida;
}
