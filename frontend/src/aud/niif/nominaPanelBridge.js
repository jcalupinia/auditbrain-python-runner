// Puente postMessage entre el panel de nómina (pestaña nueva, servido por el backend) y
// VistaProceso (su `window.opener`). El panel postea estas acciones y el Command Center las
// despacha a sus handlers reales (descargar una cédula, procesar con el motor, encerar con
// confirmación humana). Se mantiene PURO para poder probarlo sin DOM (vitest, entorno node).

export const MENSAJES_NOMINA = {
  DESCARGAR: "auditbrain:nomina-descargar",
  PROCESAR: "auditbrain:nomina-procesar",
  ENCERAR: "auditbrain:nomina-encerar",
};

// Despacha un mensaje del panel a los handlers dados. Valida SIEMPRE `msg.type`. Devuelve la
// acción ejecutada ("descargar" | "procesar" | "encerar") o null si el mensaje no es del panel
// (sin type, type desconocido, o descargar sin cédula). Cada handler es opcional.
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
    default:
      return null;
  }
}
