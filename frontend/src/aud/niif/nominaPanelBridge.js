// Puente postMessage entre el panel de nómina (pestaña nueva, servido por el backend) y
// VistaProceso (su `window.opener`). El panel postea estas acciones y el Command Center las
// despacha a sus handlers reales (descargar una cédula, procesar con el motor, encerar con
// confirmación humana). Se mantiene PURO para poder probarlo sin DOM (vitest, entorno node).

export const MENSAJES_NOMINA = {
  DESCARGAR: "auditbrain:nomina-descargar",
  PROCESAR: "auditbrain:nomina-procesar",
  ENCERAR: "auditbrain:nomina-encerar",
  GUARDAR_DO1: "auditbrain:nomina-do1-guardar",
};

// Despacha un mensaje del panel a los handlers dados. Valida SIEMPRE `msg.type`. Devuelve la
// acción ejecutada ("descargar" | "procesar" | "encerar" | "guardar-do1") o null si el mensaje no
// es del panel (sin type, type desconocido, descargar sin cédula, o guardar-do1 sin estado).
// Cada handler es opcional.
//
// Importante: "encerar" solo invoca `handlers.encerar` (en la app = disparar la confirmación);
// nunca borra por su cuenta. Así el borrado real pasa por el flujo de confirmación humana.
export function despacharMensajeNomina(msg, handlers = {}) {
  if (!msg || typeof msg.type !== "string") return null;
  switch (msg.type) {
    case MENSAJES_NOMINA.DESCARGAR:
      if (!msg.cedula) return null;
      handlers.descargar?.(String(msg.cedula));
      return "descargar";
    case MENSAJES_NOMINA.PROCESAR:
      handlers.procesar?.();
      return "procesar";
    case MENSAJES_NOMINA.ENCERAR:
      handlers.encerar?.();
      return "encerar";
    // Autosave del cuestionario DO-1: persiste su estado dentro de la prueba. Requiere un
    // objeto `estado`; sin él no es un mensaje válido del panel.
    case MENSAJES_NOMINA.GUARDAR_DO1:
      if (!msg.estado || typeof msg.estado !== "object") return null;
      handlers.guardarDo1?.(msg.estado);
      return "guardar-do1";
    default:
      return null;
  }
}
