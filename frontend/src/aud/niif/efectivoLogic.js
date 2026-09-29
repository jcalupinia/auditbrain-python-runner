// Lógica pura de la vista de 3 pasos de «Efectivo y Equivalentes de Efectivo»
// (VistaEfectivo). Sin React, para poder probarla. Las reglas del ciclo viven en
// el servidor; aquí solo se decide cómo agrupar los requerimientos del mockup, si
// el paso 3 está habilitado y cuánto se ha avanzado en la carga de documentos.

// Los 4 requerimientos primarios del mockup (datasets estructurados), en el orden
// en que se muestran como tarjetas de carga. La etiqueta es la del mockup aprobado;
// el nombre canónico del requerimiento (req.document) se conserva aparte.
export const PRINCIPALES = [
  { id: "RQ-001", titulo: "Anexo de Caja y Bancos" },
  { id: "RQ-002", titulo: "Conciliaciones Bancarias" },
  { id: "RQ-010", titulo: "Estados de Cuenta Bancarios" },
  { id: "RQ-009", titulo: "Mayores Contables" },
];

const IDS_PRINCIPALES = PRINCIPALES.map((p) => p.id);

// Tarjetas de «Ejecución de auditoría» (paso 3), en el orden del mockup. Todas
// abren la vista de trabajo detallada existente; «reproceso» además puede consultar
// el endpoint de reproceso de la conciliación del último mes.
export const EJECUCIONES = [
  { clave: "procedimiento", titulo: "Procedimiento de Efectivo y Equivalentes de Efectivo" },
  { clave: "sumaria", titulo: "Sumaria" },
  { clave: "resumen_conciliaciones", titulo: "Resumen de Conciliaciones Bancarias" },
  { clave: "partidas", titulo: "Análisis de Partidas Conciliatorias" },
  { clave: "reproceso", titulo: "Reproceso de Conciliación Bancaria – Último Mes", reproceso: true },
  { clave: "corte", titulo: "Corte de Documentos" },
  { clave: "confirmaciones", titulo: "Confirmaciones Bancarias" },
  { clave: "restringido", titulo: "Efectivo Restringido" },
  { clave: "equivalentes", titulo: "Equivalentes de Efectivo" },
  { clave: "asientos", titulo: "Asientos de Ajuste y Reclasificación" },
  { clave: "arqueo", titulo: "Arqueo de Caja" },
];

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

// Separa la lista de requerimientos en las 4 tarjetas primarias (en el orden del
// mockup) y los documentos de soporte (todo lo demás, en su orden original).
export function separarRequerimientos(requests) {
  const porId = Object.fromEntries((requests || []).map((r) => [r.id, r]));
  const principales = PRINCIPALES
    .map((p) => ({ ...p, req: porId[p.id] }))
    .filter((p) => p.req);
  const soporte = (requests || []).filter((r) => !IDS_PRINCIPALES.includes(r.id));
  return { principales, soporte };
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
