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

/** Los dos segmentos del papel, en el mismo orden que `service.SEGMENTOS`. */
export const SEGMENTOS = ["NO-RELACIONADOS", "RELACIONADOS"];

/** Número escrito por el usuario (admite coma decimal), o `null` si no lo es. */
function numeroEscrito(valor) {
  const texto = String(valor ?? "").trim().replace(",", ".");
  if (texto === "") return null;
  const numero = Number(texto);
  return isFinite(numero) ? numero : null;
}

/** Mensaje único del factor prospectivo fuera de rango (pantalla y backend dicen lo mismo). */
export const ERROR_FACTOR_PROSPECTIVO =
  "El factor prospectivo debe ser mayor que 0,000: un factor de 0,000 anularía la pérdida " +
  "esperada de todas las bandas y uno negativo invertiría su signo (1,000 = sin ajuste; " +
  "1,100 = 10 % más de pérdida esperada).";

/**
 * Factor prospectivo por segmento (1,000 = sin ajuste).
 *
 * Lo que no se declara vale 1,000 -«sin ajuste»-, nunca 0. Un factor de 0,000
 * NO es un ajuste: anula la pérdida esperada entera (toda banda en 0,00,
 * cualquiera que sea su tasa observada) y archiva un papel que afirma que no
 * hay pérdida. NIIF 9 B5.5.51-52 pide ajustar la tasa histórica por las
 * previsiones, no sustituirla por cero, así que aquí se rechaza -igual que en
 * el backend, con el mismo mensaje- en vez de enviarse y medir cero.
 *
 * El backend además exige justificación escrita para aplicar cualquier factor
 * distinto de 1,000; sin ella lo deja en 1,000 y emite el hallazgo «Ausencia
 * del componente prospectivo».
 * @param {object} datos - Campos del formulario
 * @returns {object} `{segmento: factor}`
 * @throws {Error} Si algún factor declarado es cero o negativo
 */
export function factorProspectivoDeclarado(datos) {
  const leer = (valor) => {
    const numero = numeroEscrito(valor);
    if (numero === null) return 1;
    if (numero <= 0) throw new Error(ERROR_FACTOR_PROSPECTIVO);
    return numero;
  };
  return {
    "NO-RELACIONADOS": leer(datos?.factor_nr),
    RELACIONADOS: leer(datos?.factor_r),
  };
}

/** ¿La tasa sustituta está completa? Sin justificación escrita el backend la ignora. */
export function tasaSustitutaCompleta(fila) {
  return Boolean(
    String(fila?.segmento || "").trim() &&
      String(fila?.banda || "").trim() &&
      numeroEscrito(fila?.tasa) !== null &&
      String(fila?.justificacion || "").trim()
  );
}

/** ¿La evaluación individual está completa? */
export function evaluacionIndividualCompleta(fila) {
  return Boolean(
    String(fila?.segmento || "").trim() &&
      String(fila?.cliente || "").trim() &&
      numeroEscrito(fila?.ecl) !== null &&
      String(fila?.justificacion || "").trim()
  );
}

/**
 * Cuántas filas quedaron a medio llenar.
 *
 * Una fila incompleta no se envía -el backend la ignoraría igual-, pero
 * tampoco se descarta en silencio: la pantalla dice cuántas hay para que el
 * auditor las complete o las borre.
 * @param {Array} filas - Filas del formulario
 * @param {function} completa - Predicado de completitud
 * @returns {number} Filas con algo escrito pero incompletas
 */
export function filasIncompletas(filas, completa) {
  return (filas || []).filter(
    (f) =>
      !completa(f) &&
      Object.values(f || {}).some((v) => String(v ?? "").trim() !== "")
  ).length;
}

/**
 * Tasas sustitutas listas para el backend: `{ "SEGMENTO|banda": {tasa, justificacion} }`.
 *
 * El formulario recoge PORCENTAJES ("42" = 42 %) y el servicio espera
 * fracciones, igual que con la política del cliente.
 * @param {Array} filas - Filas `{segmento, banda, tasa, justificacion}`
 * @returns {object} Solo las filas completas
 */
export function tasasSustitutasDeclaradas(filas) {
  const salida = {};
  for (const fila of filas || []) {
    if (!tasaSustitutaCompleta(fila)) continue;
    salida[`${String(fila.segmento).trim()}|${String(fila.banda).trim()}`] = {
      tasa: numeroEscrito(fila.tasa) / 100,
      justificacion: String(fila.justificacion).trim(),
    };
  }
  return salida;
}

/**
 * Evaluaciones individuales: `{ "SEGMENTO|cliente": {ecl, justificacion} }`.
 *
 * `ecl` es un IMPORTE en dólares (la pérdida esperada que el auditor midió
 * para ese cliente), no un porcentaje. Un 0,00 declarado sí viaja: «medí y no
 * hay pérdida» es una afirmación, distinta de «no se midió».
 * @param {Array} filas - Filas `{segmento, cliente, ecl, justificacion}`
 * @returns {object} Solo las filas completas
 */
export function evaluacionesIndividualesDeclaradas(filas) {
  const salida = {};
  for (const fila of filas || []) {
    if (!evaluacionIndividualCompleta(fila)) continue;
    salida[`${String(fila.segmento).trim()}|${String(fila.cliente).trim()}`] = {
      ecl: numeroEscrito(fila.ecl),
      justificacion: String(fila.justificacion).trim(),
    };
  }
  return salida;
}

/**
 * Parámetros que viajan con los tres cortes y quedan guardados con la corrida.
 *
 * `mayor_provision` es una declaración del auditor, no un archivo: el endpoint
 * `/analizar` exige exactamente tres archivos (los tres análisis de antigüedad)
 * y el servicio solo comprueba que el dato esté presente. Vacío, el pendiente
 * «Mayores de la provisión de los tres ejercicios» se dispara, que es lo
 * correcto mientras la evidencia no exista.
 *
 * El factor prospectivo con su justificación, las tasas sustitutas, las
 * evaluaciones individuales y el RUC SÍ se envían: el backend los aceptaba
 * desde siempre y la pantalla no los mandaba, así que el hallazgo «Ausencia
 * del componente prospectivo» se disparaba en el 100 % de las corridas y
 * `00-Caratula` B7 salía en blanco.
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
    ruc: String(datos.ruc || "").trim(),
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
    // Componente prospectivo (NIIF 9 5.5.17(c) y B5.5.51-52): el factor solo
    // se aplica si viaja con su justificación escrita.
    factor_prospectivo: factorProspectivoDeclarado(datos),
    justificacion_prospectivo: String(datos.justificacion_prospectivo || "").trim(),
    tasas_sustitutas: tasasSustitutasDeclaradas(datos.tasas_sustitutas),
    evaluaciones_individuales: evaluacionesIndividualesDeclaradas(
      datos.evaluaciones_individuales
    ),
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
 * Archivos ya elegidos que superan el límite por archivo del backend.
 *
 * El límite lo fija `MAX_BYTES_POR_ARCHIVO` en el router y llega por
 * `/limites`: aquí no se escribe ninguna cifra. Sirve para decirlo ANTES de
 * subir -el análisis de antigüedad real con el que se calibró la memoria son
 * unos 16 MB y se rechaza con un 413- en vez de después de esperar la subida
 * de tres archivos.
 *
 * Mientras los límites no se hayan podido consultar se devuelve la lista
 * vacía: no se acusa a un archivo con una cifra que la pantalla no conoce; el
 * backend sigue siendo quien decide.
 * @param {Array} archivos - Archivos elegidos (puede haber huecos)
 * @param {object|null} limites - Respuesta de `pceCxcLimites`
 * @returns {Array<{nombre: string, mb: string}>} Los que no entran
 */
export function archivosQueSuperanElLimite(archivos, limites) {
  const maximo = Number(limites?.max_bytes_por_archivo || 0);
  if (!maximo) return [];
  return (archivos || [])
    .filter((f) => f && Number(f.size) > maximo)
    .map((f) => ({
      nombre: f.name,
      mb: (Number(f.size) / (1024 * 1024)).toLocaleString("es-EC", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      }),
    }));
}

/** Importe en el formato del papel (es-EC, dos decimales). */
function importe(valor) {
  return Number(valor || 0).toLocaleString("es-EC", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Aviso de que lo sin medir NO se netea, cuando hay algo que netear.
 *
 * `exposicion.sin_medir` es la MAGNITUD (deudora + |acreedora|) y
 * `exposicion.sin_medir_neto` la suma con signo. Cuando difieren, el KPI «Sin
 * medir» y la «Cartera medida» dejan de sumar la cartera total, y el auditor
 * tiene que saber por qué antes de concluir que una de las dos está mal: la
 * cartera medida sale de la NETA -porque la estratificada también es neta- y
 * la cifra que se declara es la MAGNITUD, porque una banda sin tasa no
 * compensa a otra. Es la misma explicación que imprime `08-Conciliacion`.
 *
 * Una corrida anterior a estos campos devuelve `null`: no se afirma que no
 * hubiera nada que netear, es que esa corrida no lo registró.
 * @param {object|null} resultado - Resultado de `analizar`
 * @returns {string|null} Texto para la pantalla, o `null` si no aplica
 */
export function sinMedirNoNeteado(resultado) {
  const exposicion = resultado?.exposicion;
  if (!exposicion || exposicion.sin_medir_neto == null) return null;
  const magnitud = Number(exposicion.sin_medir || 0);
  const neto = Number(exposicion.sin_medir_neto || 0);
  if (Math.abs(magnitud - neto) <= 0.005) return null;
  return (
    `De la exposición sin medir, ${importe(exposicion.sin_medir_deudora)} es saldo deudor y ` +
    `${importe(Math.abs(Number(exposicion.sin_medir_acreedora || 0)))} saldo acreedor en bandas ` +
    `sin tasa. No se netean entre sí -ninguna de las dos se midió-, así que «Sin medir» declara ` +
    `la magnitud (${importe(magnitud)}). La «Cartera medida» sí sale del NETO ` +
    `(${importe(neto)}), porque la cartera estratificada también es neta: por eso «Cartera ` +
    `medida» más «Sin medir» no da la cartera total. Apruebe una tasa sustituta para esas bandas, ` +
    `o reclasifique los saldos acreedores a pasivo (anticipos de clientes).`
  );
}

/**
 * Cotas que ACTUARON en esta corrida, listas para pintar.
 *
 * Ninguna cota de este módulo puede actuar en silencio: si un número se
 * recortó, el motor lo declara (`exposicion.medida_acotada`,
 * `exposicion.sin_medir_recortado`), el papel lo imprime en su celda y la
 * pantalla tiene que decirlo también. Sin esta función el auditor veía una
 * «Cartera medida» de 0,00 sin saber que salía de recortar una resta negativa.
 *
 * Una corrida anterior a estos campos devuelve la lista vacía: no se afirma
 * que ninguna cota actuara, es que esa corrida no lo registró (y su papel lo
 * rotula «NO REGISTRADO EN ESTA CORRIDA»).
 * @param {object|null} resultado - Resultado de `analizar`
 * @returns {Array<{clave: string, texto: string}>} Cotas que mordieron
 */
export function cotasDeLaCorrida(resultado) {
  const exposicion = resultado?.exposicion;
  if (!exposicion) return [];
  const cotas = [];
  if (exposicion.medida_acotada) {
    cotas.push({
      clave: "cartera_medida",
      texto:
        `La cartera medida se acotó: la cartera estratificada menos lo que no se pudo medir ` +
        `daba ${importe(exposicion.medida_sin_acotar)} y se registró ` +
        `${importe(exposicion.medida)}. Lo que no se pudo medir supera a la cartera ` +
        `estratificada, así que la cobertura sobre lo medido pierde denominador.`,
    });
  }
  if (Number(exposicion.sin_medir_recortado || 0) > 0.005) {
    cotas.push({
      clave: "saldo_sin_medir",
      texto:
        `${importe(exposicion.sin_medir_recortado)} de saldo sin medir excedían la exposición ` +
        `de su propio cliente evaluado individualmente y se acotaron: ese importe carece de ` +
        `tasa, pero ya no cabe dentro de la exposición del caso (06-Individual, columna ` +
        `«Saldo sin medir SIN ACOTAR»).`,
    });
  }
  return cotas;
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
