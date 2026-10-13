// Puente postMessage entre el panel de nómina (pestaña nueva, servido por el backend) y
// VistaProceso (su `window.opener`). El panel postea estas acciones y el Command Center las
// despacha a sus handlers reales (descargar una cédula, procesar con el motor, encerar con
// confirmación humana). Se mantiene PURO para poder probarlo sin DOM (vitest, entorno node).

export const MENSAJES_NOMINA = {
  DESCARGAR: "auditbrain:nomina-descargar",
  PROCESAR: "auditbrain:nomina-procesar",
  ENCERAR: "auditbrain:nomina-encerar",
  GUARDAR_DO1: "auditbrain:nomina-do1-guardar",
  SUBIR: "auditbrain:nomina-subir",
  BORRAR: "auditbrain:nomina-borrar",
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
    // Carga de archivos desde los casilleros del panel: sube de verdad a la prueba. Requiere el
    // requerimiento y al menos un archivo (File); el componente (sub-casillero) es opcional.
    case MENSAJES_NOMINA.SUBIR:
      if (!msg.req || !Array.isArray(msg.files) || !msg.files.length) return null;
      handlers.subir?.({ req: String(msg.req), comp: String(msg.comp || ""), files: msg.files });
      return "subir";
    // Borrado de un archivo ya cargado (botón ✕ sobre un archivo real de la prueba).
    case MENSAJES_NOMINA.BORRAR:
      if (msg.fileId == null) return null;
      handlers.borrar?.(msg.fileId);
      return "borrar";
    default:
      return null;
  }
}
