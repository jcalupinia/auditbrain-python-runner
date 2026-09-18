// Bandas de mora por defecto, en el mismo orden que `bandas.BANDAS_POR_DEFECTO`
// del backend. La última es abierta y se desdobla en el umbral de incumplimiento.
const BANDAS_BASE = [
  "Por vencer",
  "0 a 30 días",
  "31 a 60 días",
  "61 a 90 días",
  "91 a 180 días",
  "181 a 360 días",
  "Más de 360 días",
];
const ULTIMA_BANDA = BANDAS_BASE[BANDAS_BASE.length - 1];
const INICIO_BANDA_ABIERTA = 361;
const UMBRAL_DIAS_POR_DEFECTO = 730;

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
    // Política de deterioro del cliente por banda. Lo que no se declaró no
    // viaja: el backend lo deja «sin comparar», nunca en 0 %.
    politica: politicaDeclarada(datos.politica),
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

/**
 * Bandas de mora sobre las que se pide la política de deterioro del cliente.
 *
 * Es el mismo universo que arma el backend (`bandas.desdoblar`): las siete
 * bandas por defecto, con la última abierta partida en el umbral de
 * incumplimiento. Con el umbral del plan (730 días) son ocho. Si aquí faltara
 * una banda, esa fila quedaría SIN COMPARAR en `07-Politica`.
 * @param {number|string} umbralDias - Días de mora a partir de los cuales se presume incumplimiento
 * @returns {string[]} Nombres de banda, en el orden del papel
 */
export function bandasDeLaPolitica(umbralDias) {
  const umbral = Number(umbralDias) || UMBRAL_DIAS_POR_DEFECTO;
  const previas = BANDAS_BASE.slice(0, -1);
  if (umbral <= INICIO_BANDA_ABIERTA) return [...previas, ULTIMA_BANDA];
  return [...previas, `${INICIO_BANDA_ABIERTA} a ${umbral} días`, `Más de ${umbral} días`];
}

/**
 * Política de deterioro declarada por el auditor, lista para el backend.
 *
 * El formulario recoge PORCENTAJES ("2" = 2 %) y el servicio espera fracciones.
 * Una banda en blanco NO se envía: el backend la deja «sin comparar» y levanta
 * el pendiente correspondiente. Rellenarla con 0 % acusaría al cliente de no
 * provisionar una banda que nunca se le preguntó.
 * @param {object} politica - Porcentajes por banda, tal como se escribieron
 * @returns {object} `{banda: fracción}` solo con las bandas declaradas
 */
export function politicaDeclarada(politica) {
  const salida = {};
  for (const [banda, valor] of Object.entries(politica || {})) {
    const texto = String(valor ?? "").trim().replace(",", ".");
    if (texto === "") continue;
    const numero = Number(texto);
    if (!isFinite(numero)) continue;
    salida[banda] = numero / 100;
  }
  return salida;
}

/** Cuántos documentos inconsistentes se nombran en la pantalla. */
const MAX_EJEMPLOS_COHORTE = 5;

/**
 * Control de la cohorte contra el corte intermedio, listo para mostrar.
 *
 * El corte t-1 no entra en las tasas (la permanencia se mide entre t-2 y t),
 * pero sí dice si el camino entre los dos extremos es coherente: un documento
 * que desapareció y volvió, o un saldo que creció sin facturación nueva,
 * invalidan el remanente que alimenta todas las tasas.
 * @param {object|null} resultado - Resultado de `analizar`
 * @returns {object|null} Resumen del control, o null si la corrida no lo trae
 */
export function controlDeLaCohorte(resultado) {
  const control = resultado?.control_corte_intermedio;
  if (!control) return null;
  const inconsistencias = control.inconsistencias || [];
  return {
    consistente: control.consistente === true,
    total: control.inconsistencias_total ?? 0,
    importe: control.inconsistencias_importe ?? 0,
    documentos: control.documentos_cohorte ?? 0,
    vivos: control.vivos_en_intermedio ?? 0,
    permanencia: control.permanencia_intermedia ?? null,
    ejemplos: inconsistencias
      .slice(0, MAX_EJEMPLOS_COHORTE)
      .map((c) => c.documento)
      .join(", "),
  };
}
