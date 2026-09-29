// Lógica de presentación de la consola-chat del piloto de planificación (sin JSX, para poder probarla).
//
// El agente (determinista, en el servidor) devuelve un hilo de mensajes y la
// «siguiente» acción según el estado. Aquí van las funciones puras que el
// componente usa para pintar el chat y decidir qué control mostrar en cada paso.

// Solo la planificación NIA tiene consola-chat (es el piloto).
export function esPlanificacion(prueba) {
  return (prueba && prueba.definicion && prueba.definicion.processor) === "planificacion_nia";
}

// Clase de burbuja según quién habla.
export function claseMensaje(de) {
  return { agente: "nf-chat-agente", preparador: "nf-chat-prep", auditor: "nf-chat-aud", sistema: "nf-chat-sys" }[de]
    || "nf-chat-sys";
}

// Nombre visible del emisor.
export function nombreDe(de) {
  return { agente: "Asistente", preparador: "Preparador", auditor: "Auditor", sistema: "Sistema" }[de] || de;
}

// Estados del ciclo en los que ya se pueden subir documentos (hay requerimiento aprobado).
const CON_SUBIDA = ["REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA"];
export function puedeSubirInline(prueba) {
  return CON_SUBIDA.includes(prueba && prueba.estado) && Array.isArray(prueba.registro && prueba.registro.requests)
    && prueba.registro.requests.length > 0;
}

// Requerimientos obligatorios que faltan (para subir inline en el chat).
export function requerimientosPendientes(prueba, cobertura) {
  const cob = Object.fromEntries((cobertura || []).map((c) => [c.id, c]));
  return ((prueba.registro && prueba.registro.requests) || []).filter(
    (r) => r.required !== false && !(cob[r.id] && cob[r.id].complete));
}

// ¿La acción del agente se resuelve dentro del chat, o hay que abrir la vista detallada?
export function accionInline(accion) {
  return ["subir", "revisar", "aprobar", "devolver", "esperar", "descargar"].includes(accion);
}
