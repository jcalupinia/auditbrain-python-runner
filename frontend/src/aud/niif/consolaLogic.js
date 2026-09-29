// Lógica pura de la consola de comunicación por prueba (chat auditable), sin React
// ni red, para probarla en aislamiento (consolaLogic.test.js). El componente
// ConsolaPrueba.jsx solo orquesta estado y llamadas a la API con estos helpers.

// Etiqueta legible en español para un evento de sistema de la bitácora (los que no
// son comentarios). Alimenta la línea gris del hilo. Desconocidos → la acción cruda.
const ETIQUETAS_SISTEMA = {
  create: "Prueba creada",
  research: "Consulta de fuentes oficiales",
  generate_program: "Programa generado",
  approve_program: "Programa aprobado",
  approve_methodology: "Metodología aprobada",
  generate_request: "Requerimiento generado",
  approve_request: "Requerimiento aprobado",
  upload: "Documento cargado",
  execute: "Prueba ejecutada",
  submit: "Enviada a revisión",
  approve: "Aprobada",
  reject: "Devuelta con observaciones",
  workpaper: "Papel de trabajo guardado",
  new_version: "Nueva versión",
  erase: "Encerada",
  edit_context: "Contexto editado",
};

export function etiquetaSistema(ev) {
  const base = ETIQUETAS_SISTEMA[ev?.accion] || ev?.accion || "Evento";
  return ev?.estado_nuevo ? `${base} → ${ev.estado_nuevo}` : base;
}

// ¿El texto es un comentario válido para enviar? (no vacío, dentro del límite).
export function comentarioValido(texto) {
  const t = String(texto ?? "").trim();
  return t.length > 0 && t.length <= 8000;
}

// ¿Se puede pedir respuesta al asistente? Solo si hay proveedor y texto válido.
export function puedePreguntar(asistenteDisponible, texto) {
  return Boolean(asistenteDisponible) && comentarioValido(texto);
}

// Separa la conversación en la línea de tiempo para pintar: cada ítem trae su
// tipo ('comentario' | 'sistema'), quién y el texto/etiqueta ya resuelto.
export function lineasDeConversacion(conversacion) {
  return (conversacion || []).map((ev) => ({
    id: ev.id,
    tipo: ev.tipo === "comentario" ? "comentario" : "sistema",
    esAsistente: Boolean(ev.es_asistente),
    actor: ev.actor || "",
    texto: ev.tipo === "comentario" ? ev.texto || "" : etiquetaSistema(ev),
    fecha: ev.fecha || null,
  }));
}

// Solo los comentarios (para el contador «N mensajes» del encabezado).
export function cuentaComentarios(conversacion) {
  return (conversacion || []).filter((ev) => ev.tipo === "comentario").length;
}
