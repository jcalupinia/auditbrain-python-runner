// Lógica pura de la vista de 3 pasos config-driven (VistaProceso). Sin React, para
// poder probarla. Las reglas del ciclo viven en el servidor; aquí solo se decide
// cómo agrupar los requerimientos según la config de cada herramienta, si el paso 3
// está habilitado y cuánto se ha avanzado en la carga de documentos.
//
// Los catálogos por procesador (tarjetas primarias «principales» y tarjetas de
// ejecución «ejecuciones», con sus requerimientos relacionados) viven en
// `procesoConfig.js`. `separarRequerimientos` se parametriza por la lista de
// principales de esa config, de modo que la MISMA lógica sirve para efectivo,
// planificación y cualquier herramienta futura.

// Estados del ciclo en los que la prueba ya está procesada: existen las cédulas y
// se habilita el paso 3.
export const ESTADOS_PROCESADA = ["PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS", "EN_REVISION", "APROBADO"];

// Estados en los que se pueden subir documentos (requerimiento aprobado).
export const ESTADOS_CON_SUBIDA = ["REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA"];

// Estados del ciclo en los que los documentos ya se validaron.
export const ESTADOS_VALIDADOS = [
  "DOCUMENTACION_VALIDADA", "PRUEBA_CONFIGURADA", "METODOLOGIA_APROBADA",
  "PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS", "EN_REVISION", "APROBADO",
];

// Estados del ciclo en los que ya se puede procesar (requerimiento listo, aún no ejecutada).
export const ESTADOS_DISPONIBLE = [...ESTADOS_CON_SUBIDA, ...["DOCUMENTACION_VALIDADA", "PRUEBA_CONFIGURADA", "METODOLOGIA_APROBADA"]];

// ¿La prueba ya se procesó? (paso 3 habilitado).
export const estaProcesada = (estado) => ESTADOS_PROCESADA.includes(estado);

// ¿Se pueden subir documentos en este estado?
export const puedeSubir = (estado) => ESTADOS_CON_SUBIDA.includes(estado);

// Una versión aprobada no se puede encerar (NIA 230); el servidor también lo bloquea.
export const puedeEncerar = (estado) => estado !== "APROBADO";

// Separa la lista de requerimientos en las tarjetas primarias (en el orden que fija
// la config de la herramienta) y los documentos de soporte (todo lo demás, en su
// orden original). `principales` es la lista `[{id, titulo}, …]` de `procesoConfig`.
export function separarRequerimientos(requests, principales = []) {
  const porId = Object.fromEntries((requests || []).map((r) => [r.id, r]));
  const idsPrincipales = principales.map((p) => p.id);
  const cards = principales
    .map((p) => ({ ...p, req: porId[p.id] }))
    .filter((p) => p.req);
  const soporte = (requests || []).filter((r) => !idsPrincipales.includes(r.id));
  return { principales: cards, soporte };
}

// Estado de un requerimiento (taxonomía del prompt): "Pendiente" | "Cargado" |
// "Validado" | "Error". Sin archivo → Pendiente; con archivo rechazado → Error;
// completo y ya validado el encargo → Validado; completo pero sin validar → Cargado.
export function estadoRequerimiento(reqId, coberturaMap, estado) {
  const c = coberturaMap && coberturaMap[reqId];
  if (c && c.rejected) return "Error";
  if (!c || !c.complete) return "Pendiente";
  return ESTADOS_VALIDADOS.includes(estado) ? "Validado" : "Cargado";
}

// Estado de la prueba (taxonomía del prompt): "BLOQUEADA" | "DISPONIBLE" |
// "EJECUTADA" | "CON EXCEPCIONES" | "REVISADA". Antes del requerimiento aprobado la
// ejecución está bloqueada; tras procesar, EJECUTADA (o CON EXCEPCIONES si hay
// excepciones); en revisión/aprobada, REVISADA.
export function estadoPrueba(estado, tieneExcepciones) {
  if (["EN_REVISION", "APROBADO"].includes(estado)) return "REVISADA";
  if (ESTADOS_PROCESADA.includes(estado)) return tieneExcepciones ? "CON EXCEPCIONES" : "EJECUTADA";
  if (ESTADOS_DISPONIBLE.includes(estado)) return "DISPONIBLE";
  return "BLOQUEADA";
}

// Avance de la carga: cuántos requerimientos obligatorios están completos.
export function avanceCarga(requests, coberturaArray) {
  const cob = Object.fromEntries((coberturaArray || []).map((c) => [c.id, c]));
  const obligatorios = (requests || []).filter((r) => r.required !== false);
  const completos = obligatorios.filter((r) => cob[r.id] && cob[r.id].complete).length;
  const total = obligatorios.length;
  return { completos, total, pct: total ? Math.round((completos / total) * 100) : 0 };
}
