// Configuración por procesador de la vista de 3 pasos (VistaProceso). Cada
// herramienta que usa esa vista declara aquí su encabezado, sus tarjetas de
// requerimientos primarios y sus tarjetas de ejecución (paso 3) con los
// requerimientos que cada una utiliza. Sin lógica: solo datos.
//
// Estructura de una config:
//   {
//     processor,      // id del procesador del backend (branch en PruebasEncargo)
//     eyebrow,        // título superior (mayúsculas)
//     titulo,         // título grande del módulo (mockup)
//     subtitulo,      // subtítulo del módulo (mockup)
//     principales,    // [{ id, titulo, icono, tipos }]  tarjetas primarias del paso 1
//     ejecuciones,    // [{ clave, titulo, subtitulo, icono, relacionados, reproceso? }]  paso 3
//   }
//
// `icono` es una clave del mapa de íconos de VistaProceso (chart, doc, pdf, shield,
// bank, list, table, search, refresh, dashboard, line, pie, calc, warning, gears).
// `tipos` es el texto de formatos del mockup (p. ej. ".xlsx", "PDF", ".xlsx / .pdf").
// `relacionados` de cada ejecución indica qué requerimientos usa: una lista de ids
// (["RQ-001", "RQ-002"]) o la cadena "todos". `reproceso: true` (solo en efectivo)
// habilita el panel de reproceso y la descarga REPROCESO_CONCILIACION.xlsx.

// --- Efectivo y Equivalentes de Efectivo (comportamiento idéntico al histórico) ---
const EFECTIVO = {
  processor: "efectivo_equivalentes",
  eyebrow: "EFECTIVO Y EQUIVALENTES DE EFECTIVO",
  titulo: "Efectivo y Equivalentes de Efectivo",
  subtitulo: "Conciliaciones Bancarias · Auditoría Externa",
  principales: [
    { id: "RQ-001", titulo: "Anexo de Caja y Bancos", icono: "chart", tipos: ".xlsx" },
    { id: "RQ-002", titulo: "Conciliaciones Bancarias", icono: "doc", tipos: ".xlsx" },
    { id: "RQ-010", titulo: "Estados de Cuenta Bancarios", icono: "bank", tipos: ".xlsx / .pdf" },
    { id: "RQ-009", titulo: "Mayores Contables", icono: "list", tipos: ".xlsx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Efectivo y Equivalentes de Efectivo",
      subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", relacionados: "todos" },
    { clave: "sumaria", titulo: "Sumaria", subtitulo: "Cédula sumaria de efectivo y equivalentes de efectivo.",
      icono: "table", relacionados: ["RQ-001", "RQ-009"] },
    { clave: "resumen_conciliaciones", titulo: "Resumen de Conciliaciones Bancarias",
      subtitulo: "Resumen por cuenta y período.", icono: "chart", relacionados: ["RQ-001", "RQ-002", "RQ-010"] },
    { clave: "partidas", titulo: "Análisis de Partidas Conciliatorias",
      subtitulo: "Identificación y análisis de diferencias.", icono: "search", relacionados: ["RQ-002"] },
    { clave: "reproceso", titulo: "Reproceso de Conciliación Bancaria – Último Mes",
      subtitulo: "Actualiza y recalcula el último mes.", icono: "refresh", reproceso: true,
      relacionados: ["RQ-009", "RQ-010", "RQ-011"] },
    { clave: "corte", titulo: "Corte de Documentos", subtitulo: "Prueba de corte de ingresos y egresos.",
      icono: "calendar", relacionados: ["RQ-002", "RQ-004"] },
    { clave: "confirmaciones", titulo: "Confirmaciones Bancarias", subtitulo: "Cotejo de respuestas de confirmación (NIA 505).",
      icono: "doc", relacionados: ["RQ-005"] },
    { clave: "restringido", titulo: "Efectivo Restringido", subtitulo: "Fondos con restricción y su revelación.",
      icono: "shield", relacionados: ["RQ-006"] },
    { clave: "equivalentes", titulo: "Equivalentes de Efectivo", subtitulo: "Clasificación de inversiones ≤ 3 meses.",
      icono: "pie", relacionados: ["RQ-007"] },
    { clave: "asientos", titulo: "Asientos de Ajuste y Reclasificación", subtitulo: "Ajustes propuestos al saldo.",
      icono: "gears", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "arqueo", titulo: "Arqueo de Caja", subtitulo: "Recuento de caja física por denominación.",
      icono: "calc", relacionados: ["RQ-012", "RQ-008"] },
  ],
};

// --- Planificación de la auditoría (NIA 300, 315, 320, 330, 510) ---
const PLANIFICACION = {
  processor: "planificacion_nia",
  eyebrow: "PLANIFICACIÓN DE LA AUDITORÍA",
  titulo: "Planificación",
  subtitulo: "Análisis de Auditoría · Auditoría Externa",
  // 6 tarjetas primarias del mockup aprobado, en su orden. El resto de RQ (RQ-003,
  // RQ-009 y RQ-007) cae en «Documentos de soporte».
  principales: [
    { id: "RQ-002", titulo: "Estados Financieros Año Actual", icono: "chart", tipos: ".xlsx" },
    { id: "RQ-001", titulo: "Estados Financieros Año Anterior", icono: "chart", tipos: ".xlsx" },
    { id: "RQ-006", titulo: "Notas a los Estados Financieros Año Anterior", icono: "doc", tipos: ".xlsx" },
    { id: "RQ-005", titulo: "Informe de Auditoría Año Anterior", icono: "pdf", tipos: "PDF" },
    { id: "RQ-004", titulo: "Carta de Control Interno Año Anterior", icono: "shield", tipos: ".xlsx / .pdf" },
    { id: "RQ-008", titulo: "Certificado del RUC", icono: "bank", tipos: ".pdf / .xlsx" },
  ],
  // 11 tarjetas de ejecución (paso 3) del mockup aprobado, con subtítulo, ícono y
  // requerimientos relacionados. Sin reproceso (es exclusivo de efectivo).
  ejecuciones: [
    { clave: "tablero", titulo: "Tablero Ejecutivo", subtitulo: "Resumen general del análisis.",
      icono: "dashboard", relacionados: "todos" },
    { clave: "perfil", titulo: "Perfil del Encargo", subtitulo: "Información del cliente y del encargo.",
      icono: "doc", relacionados: ["RQ-005", "RQ-008", "RQ-004"] },
    { clave: "situacion", titulo: "Situación Financiera", subtitulo: "Análisis del estado de situación financiera.",
      icono: "chart", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "resultados", titulo: "Estado de Resultados", subtitulo: "Análisis del estado de resultados.",
      icono: "line", relacionados: ["RQ-002", "RQ-003"] },
    { clave: "analitico", titulo: "Analítico Preliminar", subtitulo: "Análisis comparativo y variaciones.",
      icono: "chart", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "indices", titulo: "Índices Financieros", subtitulo: "Cálculo y análisis de indicadores.",
      icono: "pie", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "materialidad", titulo: "Materialidad", subtitulo: "Cálculo de materialidad y umbrales.",
      icono: "calc", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "riesgos", titulo: "Matriz de Riesgos", subtitulo: "Identificación y evaluación de riesgos.",
      icono: "warning", relacionados: ["RQ-004", "RQ-005"] },
    { clave: "notas", titulo: "Notas a los EEFF", subtitulo: "Revisión y análisis de notas.",
      icono: "doc", relacionados: ["RQ-006", "RQ-009"] },
    { clave: "control", titulo: "Control & Anomalías", subtitulo: "Evaluación de controles y anomalías.",
      icono: "gears", relacionados: ["RQ-004"] },
    { clave: "programa", titulo: "Programa", subtitulo: "Programa de auditoría planificación.",
      icono: "list", relacionados: "todos" },
  ],
};

export const CONFIG = {
  efectivo: EFECTIVO,
  planificacion: PLANIFICACION,
};

// Devuelve la config de la vista de 3 pasos para un processor, o null si ese
// procesador no usa esta vista (sigue con VistaTrabajo).
export function configDeProcesador(processor) {
  if (processor === EFECTIVO.processor) return EFECTIVO;
  if (processor === PLANIFICACION.processor) return PLANIFICACION;
  return null;
}
