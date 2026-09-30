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

// === ETAPA 1 · Circulante / operativo ===

// --- Cuentas por Cobrar y deterioro (cxc_cartera) ---
const CXC = {
  processor: "cxc_cartera",
  icono: "coins", color: "green",
  eyebrow: "CUENTAS POR COBRAR Y DETERIORO",
  titulo: "Cuentas por Cobrar y Deterioro",
  subtitulo: "Análisis integral de cartera, confirmaciones, deterioro y cobrabilidad",
  principales: [
    { id: "RQ-001", titulo: "Cartera por Factura", icono: "doc", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Mayor de Cuentas por Cobrar", icono: "book", color: "blue", tipos: ".xlsx / .pdf" },
    { id: "RQ-003", titulo: "Confirmaciones de Clientes", icono: "people", color: "gold", tipos: "PDF" },
    { id: "RQ-004", titulo: "Cobros Posteriores al Cierre", icono: "bank", color: "purple", tipos: ".pdf / .xlsx" },
    { id: "RQ-007", titulo: "Política de Crédito y Deterioro", icono: "shield", color: "red", tipos: ".pdf / .xlsx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Cuentas por Cobrar",
      subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "sumaria", titulo: "Sumaria y Detalle de Cartera",
      subtitulo: "Cédula sumaria y detalle por factura.", icono: "table", color: "green", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "aging", titulo: "Antigüedad de la Cartera",
      subtitulo: "Aging por tramos de vencimiento.", icono: "clock", color: "purple", relacionados: ["RQ-001"] },
    { clave: "circularizacion", titulo: "Circularización",
      subtitulo: "Cotejo de confirmaciones de clientes (NIA 505).", icono: "refresh", color: "blue", relacionados: ["RQ-003"] },
    { clave: "cobros", titulo: "Cobros Posteriores",
      subtitulo: "Recaudo posterior como evidencia de existencia.", icono: "box", color: "blue", relacionados: ["RQ-004"] },
    { clave: "corte", titulo: "Corte de Ventas",
      subtitulo: "Prueba de corte de ingresos.", icono: "chart", color: "gold", relacionados: ["RQ-005", "RQ-001"] },
    { clave: "costo_amortizado", titulo: "Costo Amortizado e Intereses",
      subtitulo: "Ventas a plazo e interés implícito.", icono: "calc", color: "blue", relacionados: ["RQ-006", "RQ-002"] },
    { clave: "deterioro", titulo: "Matriz de Deterioro",
      subtitulo: "Deterioro requerido vs registrado.", icono: "warning", color: "red", relacionados: ["RQ-007", "RQ-001"] },
    { clave: "asientos", titulo: "Asientos de Ajuste",
      subtitulo: "Ajustes propuestos al saldo.", icono: "sliders", color: "blue", relacionados: ["RQ-002"] },
  ],
};

// --- Proveedores y cuentas por pagar (proveedores_cxp) ---
const PROVEEDORES = {
  processor: "proveedores_cxp",
  eyebrow: "PROVEEDORES Y CUENTAS POR PAGAR",
  titulo: "Proveedores y Cuentas por Pagar",
  subtitulo: "Pasivos Comerciales · Auditoría Externa",
  principales: [
    { id: "RQ-001", titulo: "Auxiliar de Proveedores", icono: "chart", tipos: ".xlsx / .csv" },
    { id: "RQ-003", titulo: "Mayor de Proveedores", icono: "list", tipos: ".xlsx / .pdf" },
    { id: "RQ-004", titulo: "Confirmaciones de Proveedores", icono: "doc", tipos: "PDF" },
    { id: "RQ-002", titulo: "Pagos y Facturas Posteriores", icono: "bank", tipos: ".xlsx / .csv" },
    { id: "RQ-006", titulo: "Ingresos a Bodega / Actas", icono: "table", tipos: ".pdf / .xlsx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Cuentas por Pagar",
      subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", relacionados: "todos" },
    { clave: "sumaria", titulo: "Sumaria y Detalle",
      subtitulo: "Cédula sumaria y detalle por documento.", icono: "table", relacionados: ["RQ-001", "RQ-003"] },
    { clave: "aging", titulo: "Antigüedad de Proveedores",
      subtitulo: "Aging por tramos de vencimiento.", icono: "calendar", relacionados: ["RQ-001"] },
    { clave: "pagos_posteriores", titulo: "Pagos Posteriores",
      subtitulo: "Pagos posteriores como evidencia del pasivo.", icono: "refresh", relacionados: ["RQ-002", "RQ-005"] },
    { clave: "pasivos_no_registrados", titulo: "Búsqueda de Pasivos No Registrados",
      subtitulo: "Integridad del pasivo (NIA 505/500).", icono: "search", relacionados: ["RQ-002", "RQ-006"] },
    { clave: "confirmaciones", titulo: "Confirmaciones de Proveedores",
      subtitulo: "Cotejo de respuestas de confirmación.", icono: "doc", relacionados: ["RQ-004"] },
    { clave: "corte", titulo: "Corte de Compras",
      subtitulo: "Prueba de corte de compras y recepciones.", icono: "calendar", relacionados: ["RQ-006"] },
    { clave: "costo_amortizado", titulo: "Costo Amortizado e Intereses",
      subtitulo: "Compras a plazo e interés implícito.", icono: "calc", relacionados: ["RQ-007", "RQ-003"] },
    { clave: "clasificacion", titulo: "Clasificación Corriente / No Corriente",
      subtitulo: "Presentación del pasivo por vencimiento.", icono: "list", relacionados: ["RQ-001"] },
    { clave: "asientos", titulo: "Asientos de Ajuste",
      subtitulo: "Ajustes propuestos al saldo.", icono: "gears", relacionados: ["RQ-003"] },
  ],
};

// --- Inventarios, producción y costo de ventas (inventarios_costos) ---
const INVENTARIOS = {
  processor: "inventarios_costos",
  eyebrow: "INVENTARIOS Y COSTOS",
  titulo: "Inventarios y Costos",
  subtitulo: "Existencia, Costo y Obsolescencia · Auditoría Externa",
  principales: [
    { id: "RQ-001", titulo: "Inventario Valorado (Kardex)", icono: "chart", tipos: ".xlsx / .csv" },
    { id: "RQ-003", titulo: "Movimiento por Línea Vendida", icono: "list", tipos: ".xlsx / .csv" },
    { id: "RQ-005", titulo: "Actas de Recuento Físico", icono: "doc", tipos: ".pdf / .docx" },
    { id: "RQ-006", titulo: "Ventas y Precios Posteriores", icono: "bank", tipos: ".xlsx / .pdf" },
    { id: "RQ-008", titulo: "Política de Obsolescencia", icono: "shield", tipos: ".pdf / .docx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Inventarios",
      subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", relacionados: "todos" },
    { clave: "inventario", titulo: "Inventario Valorado",
      subtitulo: "Sumaria y detalle por ítem del kardex.", icono: "table", relacionados: ["RQ-001"] },
    { clave: "conteo", titulo: "Existencia (Conteo vs Kardex)",
      subtitulo: "Observación del recuento físico (NIA 501).", icono: "search", relacionados: ["RQ-005", "RQ-001"] },
    { clave: "prueba_costo", titulo: "Prueba de Costo",
      subtitulo: "Cotejo del costo unitario contra soporte.", icono: "calc", relacionados: ["RQ-001", "RQ-010"] },
    { clave: "conciliacion", titulo: "Conciliación Kardex–Mayor",
      subtitulo: "Cuadre del inventario contra contabilidad.", icono: "refresh", relacionados: ["RQ-001"] },
    { clave: "costo_prod_ventas", titulo: "Costo de Producción y Ventas",
      subtitulo: "Armado del costo y del costo de ventas.", icono: "chart", relacionados: ["RQ-002", "RQ-003"] },
    { clave: "vnr", titulo: "Valor Realizable Neto (VNR)",
      subtitulo: "Medición al menor entre costo y VNR (NIC 2).", icono: "calc", relacionados: ["RQ-006"] },
    { clave: "obsolescencia", titulo: "Obsolescencia y Lenta Rotación",
      subtitulo: "Provisión por deterioro de inventario.", icono: "warning", relacionados: ["RQ-008", "RQ-001"] },
    { clave: "excepcion_mp", titulo: "Excepción NIC 2.32 (Materias Primas)",
      subtitulo: "Materias primas cuyo producto se vende con utilidad.", icono: "shield", relacionados: ["RQ-006"] },
    { clave: "corte", titulo: "Corte de Inventarios",
      subtitulo: "Prueba de corte de compras y ventas.", icono: "calendar", relacionados: ["RQ-004"] },
  ],
};

// --- Ingresos de contratos con clientes (ingresos_contratos) ---
const INGRESOS = {
  processor: "ingresos_contratos",
  eyebrow: "INGRESOS DE CONTRATOS CON CLIENTES",
  titulo: "Ingresos",
  subtitulo: "Contratos con Clientes · Auditoría Externa",
  principales: [
    { id: "RQ-001", titulo: "Anexo de Contratos por Obligación", icono: "chart", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Mayor de Ingresos", icono: "list", tipos: ".xlsx / .pdf" },
    { id: "RQ-003", titulo: "Contratos y Órdenes de Compra", icono: "doc", tipos: "PDF" },
    { id: "RQ-004", titulo: "Guías de Remisión / Actas", icono: "bank", tipos: ".pdf / .xlsx" },
    { id: "RQ-006", titulo: "Notas de Crédito Posteriores", icono: "refresh", tipos: ".xlsx / .pdf" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Ingresos",
      subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", relacionados: "todos" },
    { clave: "detalle", titulo: "Detalle por Obligación",
      subtitulo: "Sumaria y detalle por obligación de desempeño.", icono: "table", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "precio", titulo: "Precio y Asignación",
      subtitulo: "Precio de la transacción y su asignación.", icono: "calc", relacionados: ["RQ-001", "RQ-007"] },
    { clave: "satisfaccion", titulo: "Satisfacción y % de Avance",
      subtitulo: "Reconocimiento en el tiempo o a un punto.", icono: "chart", relacionados: ["RQ-003", "RQ-005"] },
    { clave: "reconocimiento", titulo: "Ingreso Reconocible vs Registrado",
      subtitulo: "Comparación con lo contabilizado.", icono: "search", relacionados: ["RQ-002"] },
    { clave: "devoluciones", titulo: "Devoluciones y Notas de Crédito",
      subtitulo: "Contraprestación variable posterior al cierre.", icono: "refresh", relacionados: ["RQ-006"] },
    { clave: "financiacion", titulo: "Componente de Financiación",
      subtitulo: "Ventas a plazo e interés implícito.", icono: "calc", relacionados: ["RQ-008"] },
    { clave: "activo_pasivo", titulo: "Activo y Pasivo del Contrato",
      subtitulo: "Facturación anticipada y por facturar.", icono: "list", relacionados: ["RQ-002"] },
    { clave: "corte", titulo: "Corte de Ingresos",
      subtitulo: "Prueba de corte de ventas.", icono: "calendar", relacionados: ["RQ-004"] },
    { clave: "asientos", titulo: "Asientos de Ajuste",
      subtitulo: "Ajustes propuestos al saldo.", icono: "gears", relacionados: ["RQ-002"] },
  ],
};

export const CONFIG = {
  efectivo: EFECTIVO,
  planificacion: PLANIFICACION,
  cxc: CXC,
  proveedores: PROVEEDORES,
  inventarios: INVENTARIOS,
  ingresos: INGRESOS,
};

// Devuelve la config de la vista de 3 pasos para un processor, o null si ese
// procesador no usa esta vista (sigue con VistaTrabajo). Data-driven: recorre
// CONFIG, así que agregar una herramienta es solo agregar su entrada arriba.
export function configDeProcesador(processor) {
  return Object.values(CONFIG).find((c) => c.processor === processor) || null;
}
