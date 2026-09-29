// Lógica de presentación de la consola de revisión del auditor (sin JSX, para poder probarla).
//
// La consola muestra el veredicto de la puerta de calidad de la planificación
// (APTO / OBSERVADO / NO APTO) con el recálculo independiente que hace el
// servidor. Aquí viven las funciones puras que deciden el color del veredicto,
// el resumen de cada bloque y el texto de los estados, para que el componente
// solo pinte y las reglas se prueben aparte.

// ¿Esta prueba tiene consola de revisión del auditor? (toda prueba con procesador:
// la planificación NIA con su revisor rico, las 20 herramientas con el genérico).
export function tieneConsola(prueba) {
  return !!(prueba && prueba.definicion && prueba.definicion.processor);
}

// Clase de color para el veredicto (usa las clases nf-* del CSS).
export function claseVeredicto(veredicto) {
  if (veredicto === "APTO PARA REVISIÓN DEL SOCIO") return "nf-ok";
  if (veredicto === "OBSERVADO") return "nf-warn";
  if (veredicto === "NO APTO") return "nf-error";
  return "muted";
}

// Etiqueta corta del veredicto para el encabezado del panel.
export function tituloVeredicto(veredicto) {
  return {
    "APTO PARA REVISIÓN DEL SOCIO": "Apto para revisión del socio",
    OBSERVADO: "Observado",
    "NO APTO": "No apto",
  }[veredicto] || "Sin veredicto";
}

// Clase de color de un estado de la puerta de calidad.
export function claseEstado(estado) {
  return { PASA: "nf-ok", FALLA: "nf-error", REVISAR: "nf-warn", PENDIENTE: "muted" }[estado] || "muted";
}

// Resumen de una tanda de recálculo (índices o agregados) en una frase.
export function resumenRecalculo(bloque) {
  if (!bloque) return "";
  const oks = bloque.total - bloque.diferencias;
  return `${oks} de ${bloque.total} coinciden con el recálculo independiente` +
    (bloque.diferencias ? ` · ${bloque.diferencias} con diferencia` : "");
}

// Filas del recálculo que NO coinciden (las que el auditor debe mirar).
export function diferencias(bloque) {
  return ((bloque && bloque.detalle) || []).filter((f) => !f.ok);
}

// ¿La consola habilita continuar hacia la aprobación? (nunca bloquea al socio, pero
// avisa cuando el veredicto es NO APTO).
export function bloqueaAprobacion(reporte) {
  return !!(reporte && reporte.veredicto === "NO APTO");
}
