// Lógica de presentación del Ejercicio modelo (sin JSX, para poder probarla).
//
// El panel del ejercicio modelo puede verse de dos formas:
//  - "pasos": una sección a la vez, con Anterior/Siguiente (comportamiento clásico).
//  - "todo": todas las secciones abiertas a la vez, en un solo desplazamiento.
//
// En Planificación (NIA 300/315/320/330) el auditor quiere ver TODA la
// planificación de una sola vez, así que al cargar el ejercicio modelo se abren
// todas las secciones por defecto. En las demás herramientas arranca por pasos y
// el botón «Abrir todas las secciones» permite expandirlas.

export const PROCESADORES_ABRIR_TODO = ["planificacion_nia"];

// ¿El ejercicio modelo de esta herramienta debe abrir todas las secciones al cargar?
export function abrirTodoPorDefecto(processor) {
  return PROCESADORES_ABRIR_TODO.includes(String(processor || ""));
}

// id de ancla de una sección (para el índice que hace scroll en modo "todo").
export function anclaPaso(n) {
  return `em-paso-${n}`;
}
