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

// Estado de carga de un requerimiento según la cobertura: "Cargado" | "Pendiente".
export function estadoRequerimiento(reqId, coberturaMap) {
  return coberturaMap && coberturaMap[reqId] && coberturaMap[reqId].complete ? "Cargado" : "Pendiente";
}

// Avance de la carga: cuántos requerimientos obligatorios están completos.
export function avanceCarga(requests, coberturaArray) {
  const cob = Object.fromEntries((coberturaArray || []).map((c) => [c.id, c]));
  const obligatorios = (requests || []).filter((r) => r.required !== false);
  const completos = obligatorios.filter((r) => cob[r.id] && cob[r.id].complete).length;
  const total = obligatorios.length;
  return { completos, total, pct: total ? Math.round((completos / total) * 100) : 0 };
}
