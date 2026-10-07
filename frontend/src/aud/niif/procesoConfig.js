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
  icono: "bank", color: "teal",
  eyebrow: "EFECTIVO Y EQUIVALENTES DE EFECTIVO",
  titulo: "Efectivo y Equivalentes de Efectivo",
  subtitulo: "Conciliaciones Bancarias · Auditoría Externa",
  principales: [
    { id: "RQ-001", titulo: "Anexo de Caja y Bancos", icono: "coins", color: "teal", tipos: ".xlsx / .csv / .pdf / .jpg" },
    { id: "RQ-002", titulo: "Conciliaciones Bancarias", icono: "doc", color: "blue", tipos: ".xlsx / .csv / .pdf / .jpg" },
    { id: "RQ-010", titulo: "Estados de Cuenta Bancarios", icono: "bank", color: "purple", tipos: ".xlsx / .csv / .pdf / .jpg" },
    { id: "RQ-004", titulo: "Estados y Conciliaciones Posteriores al Corte", icono: "clock", color: "green", tipos: ".pdf / .xlsx / .jpg" },
    { id: "RQ-009", titulo: "Mayores Contables", icono: "book", color: "gold", tipos: ".xlsx / .csv / .pdf / .jpg" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Efectivo y Equivalentes de Efectivo",
      subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "sumaria", titulo: "Sumaria", subtitulo: "Cédula sumaria de efectivo y equivalentes de efectivo.",
      icono: "table", color: "green", relacionados: ["RQ-001", "RQ-009"], seccion: "sec-DA1_Sumaria" },
    { clave: "resumen_conciliaciones", titulo: "Resumen de Conciliaciones Bancarias",
      subtitulo: "Resumen por cuenta y período.", icono: "chart", color: "teal", relacionados: ["RQ-001", "RQ-002", "RQ-010"], seccion: "sec-DA3_Conciliaciones" },
    { clave: "partidas", titulo: "Análisis de Partidas Conciliatorias",
      subtitulo: "Identificación y análisis de diferencias.", icono: "search", color: "purple", relacionados: ["RQ-002"], seccion: "sec-DA4_Partidas" },
    { clave: "reproceso", titulo: "Reproceso de Conciliación Bancaria – Último Mes",
      subtitulo: "Actualiza y recalcula el último mes.", icono: "refresh", color: "blue", reproceso: true,
      relacionados: ["RQ-009", "RQ-010", "RQ-011"] },
    { clave: "corte", titulo: "Corte de Documentos", subtitulo: "Prueba de corte de ingresos y egresos.",
      icono: "calendar", color: "gold", relacionados: ["RQ-002", "RQ-004"], seccion: "sec-07_Corte" },
    { clave: "confirmaciones", titulo: "Confirmaciones Bancarias", subtitulo: "Cotejo de respuestas de confirmación (NIA 505).",
      icono: "people", color: "gold", relacionados: ["RQ-005"], seccion: "sec-06_Confirmaciones" },
    { clave: "restringido", titulo: "Efectivo Restringido", subtitulo: "Fondos con restricción y su revelación.",
      icono: "shield", color: "red", relacionados: ["RQ-006"], seccion: "sec-08_Restringido" },
    { clave: "equivalentes", titulo: "Equivalentes de Efectivo", subtitulo: "Clasificación de inversiones ≤ 3 meses.",
      icono: "pie", color: "teal", relacionados: ["RQ-007"], seccion: "sec-09_Equivalentes" },
    { clave: "asientos", titulo: "Asientos de Ajuste y Reclasificación", subtitulo: "Ajustes propuestos al saldo.",
      icono: "sliders", color: "blue", relacionados: ["RQ-001", "RQ-002"], seccion: "sec-11_Asientos" },
    { clave: "arqueo", titulo: "Arqueo de Caja", subtitulo: "Recuento de caja física por denominación.",
      icono: "calc", color: "green", relacionados: ["RQ-012", "RQ-008"], seccion: "sec-DA5_Arqueo" },
  ],
};

// --- Planificación de la auditoría (NIA 300, 315, 320, 330, 510) ---
const PLANIFICACION = {
  processor: "planificacion_nia",
  icono: "dashboard", color: "blue",
  eyebrow: "PLANIFICACIÓN DE LA AUDITORÍA",
  titulo: "Planificación",
  subtitulo: "Análisis de Auditoría · Auditoría Externa",
  // Tarjetas primarias en su orden. RQ-003 (Estado de Resultados del año anterior
  // al mismo corte) es OPCIONAL y solo aplica a la visita preliminar: con él la
  // comparación del ERI es exacta (ago-vs-ago); sin él, el ERI anterior se
  // prorratea (dic ÷ 12 × meses). Se muestra como tarjeta visible —antes caía en
  // «Documentos de soporte» y pasaba desapercibido—. El resto (RQ-009 y RQ-007)
  // queda en «Documentos de soporte».
  principales: [
    { id: "RQ-002", titulo: "Estados Financieros Año Actual", icono: "chart", color: "blue", tipos: ".xlsx" },
    { id: "RQ-001", titulo: "Estados Financieros Año Anterior", icono: "chart", color: "teal", tipos: ".xlsx" },
    { id: "RQ-003", titulo: "Estado de Resultados Año Anterior (mismo corte · visita preliminar)", icono: "line", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-006", titulo: "Notas a los Estados Financieros Año Anterior", icono: "doc", color: "gold", tipos: ".xlsx / .pdf / .docx" },
    { id: "RQ-005", titulo: "Informe de Auditoría Año Anterior", icono: "pdf", color: "red", tipos: "PDF" },
    { id: "RQ-004", titulo: "Carta de Control Interno Año Anterior", icono: "shield", color: "purple", tipos: ".xlsx / .pdf" },
    { id: "RQ-008", titulo: "Certificado del RUC", icono: "bank", color: "green", tipos: ".pdf / .xlsx" },
  ],
  // 11 tarjetas de ejecución (paso 3) del mockup aprobado, con subtítulo, ícono y
  // requerimientos relacionados. Sin reproceso (es exclusivo de efectivo).
  // `seccion`: pestaña (#data-tab) del papel HTML que abre cada botón (deep-link).
  // El HTML de Planificación lo pinta el MOTOR DEL ARTEFACTO AuditBrain, cuyas
  // pestañas son: dashboard · perfil · situacion · resultados · analitico ·
  // ratios · materia · riesgos · notas · control · programa (ver artefacto_html.py
  // y el manejador de #hash de la plantilla).
  ejecuciones: [
    { clave: "tablero", titulo: "Tablero Ejecutivo", subtitulo: "Resumen general del análisis.",
      icono: "dashboard", color: "blue", relacionados: "todos", seccion: "dashboard" },
    { clave: "perfil", titulo: "Perfil del Encargo", subtitulo: "Información del cliente y del encargo.",
      icono: "doc", color: "gold", relacionados: ["RQ-005", "RQ-008", "RQ-004"], seccion: "perfil" },
    { clave: "situacion", titulo: "Situación Financiera", subtitulo: "Análisis del estado de situación financiera.",
      icono: "chart", color: "teal", relacionados: ["RQ-001", "RQ-002"], seccion: "situacion" },
    { clave: "resultados", titulo: "Estado de Resultados", subtitulo: "Análisis del estado de resultados.",
      icono: "line", color: "green", relacionados: ["RQ-002", "RQ-003"], seccion: "resultados" },
    { clave: "analitico", titulo: "Analítico Preliminar", subtitulo: "Análisis comparativo y variaciones.",
      icono: "chart", color: "purple", relacionados: ["RQ-001", "RQ-002"], seccion: "analitico" },
    { clave: "indices", titulo: "Índices Financieros", subtitulo: "Cálculo y análisis de indicadores.",
      icono: "pie", color: "gold", relacionados: ["RQ-001", "RQ-002"], seccion: "ratios" },
    { clave: "materialidad", titulo: "Materialidad", subtitulo: "Cálculo de materialidad y umbrales.",
      icono: "calc", color: "blue", relacionados: ["RQ-001", "RQ-002"], seccion: "materia" },
    { clave: "riesgos", titulo: "Matriz de Riesgos", subtitulo: "Identificación y evaluación de riesgos.",
      icono: "warning", color: "red", relacionados: ["RQ-004", "RQ-005"], seccion: "riesgos" },
    { clave: "notas", titulo: "Notas a los EEFF", subtitulo: "Revisión y análisis de notas.",
      icono: "doc", color: "gold", relacionados: ["RQ-006", "RQ-009"], seccion: "notas" },
    { clave: "control", titulo: "Control & Anomalías", subtitulo: "Evaluación de controles y anomalías.",
      icono: "gears", color: "purple", relacionados: ["RQ-004"], seccion: "control" },
    { clave: "programa", titulo: "Programa", subtitulo: "Programa de auditoría planificación.",
      icono: "list", color: "blue", relacionados: "todos", seccion: "programa" },
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
      subtitulo: "Cédula sumaria y detalle por factura.", icono: "table", color: "green", relacionados: ["RQ-001", "RQ-002"], seccion: "sec-01_Resumen" },
    { clave: "aging", titulo: "Antigüedad de la Cartera",
      subtitulo: "Aging por tramos de vencimiento.", icono: "clock", color: "purple", relacionados: ["RQ-001"], seccion: "sec-04_Aging" },
    { clave: "circularizacion", titulo: "Circularización",
      subtitulo: "Cotejo de confirmaciones de clientes (NIA 505).", icono: "refresh", color: "blue", relacionados: ["RQ-003"], seccion: "sec-06_Circularizacion" },
    { clave: "cobros", titulo: "Cobros Posteriores",
      subtitulo: "Recaudo posterior como evidencia de existencia.", icono: "box", color: "blue", relacionados: ["RQ-004"], seccion: "sec-05_Cobros_posteriores" },
    { clave: "corte", titulo: "Corte de Ventas",
      subtitulo: "Prueba de corte de ingresos.", icono: "chart", color: "gold", relacionados: ["RQ-005", "RQ-001"], seccion: "sec-07_Corte_ventas" },
    { clave: "costo_amortizado", titulo: "Costo Amortizado e Intereses",
      subtitulo: "Ventas a plazo e interés implícito.", icono: "calc", color: "blue", relacionados: ["RQ-006", "RQ-002"], seccion: "sec-08_Costo_amortizado" },
    { clave: "deterioro", titulo: "Matriz de Deterioro",
      subtitulo: "Deterioro requerido vs registrado.", icono: "warning", color: "red", relacionados: ["RQ-007", "RQ-001"], seccion: "sec-09_Matriz_deterioro" },
    { clave: "asientos", titulo: "Asientos de Ajuste",
      subtitulo: "Ajustes propuestos al saldo.", icono: "sliders", color: "blue", relacionados: ["RQ-002"], seccion: "sec-11_Asientos" },
  ],
};

// --- Proveedores y cuentas por pagar (proveedores_cxp) ---
const PROVEEDORES = {
  processor: "proveedores_cxp",
  icono: "people", color: "gold",
  eyebrow: "PROVEEDORES Y CUENTAS POR PAGAR",
  titulo: "Proveedores y Cuentas por Pagar",
  subtitulo: "Pasivos Comerciales · Auditoría Externa",
  principales: [
    { id: "RQ-001", titulo: "Auxiliar de Proveedores", icono: "coins", color: "gold", tipos: ".xlsx / .csv" },
    { id: "RQ-003", titulo: "Mayor de Proveedores", icono: "book", color: "blue", tipos: ".xlsx / .pdf" },
    { id: "RQ-004", titulo: "Confirmaciones de Proveedores", icono: "people", color: "purple", tipos: "PDF" },
    { id: "RQ-002", titulo: "Pagos y Facturas Posteriores", icono: "bank", color: "teal", tipos: ".xlsx / .csv" },
    { id: "RQ-006", titulo: "Ingresos a Bodega / Actas", icono: "box", color: "green", tipos: ".pdf / .xlsx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Cuentas por Pagar",
      subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "sumaria", titulo: "Sumaria y Detalle",
      subtitulo: "Cédula sumaria y detalle por documento.", icono: "table", color: "gold", relacionados: ["RQ-001", "RQ-003"], seccion: "sec-01_Resumen" },
    { clave: "aging", titulo: "Antigüedad de Proveedores",
      subtitulo: "Aging por tramos de vencimiento.", icono: "clock", color: "purple", relacionados: ["RQ-001"], seccion: "sec-04_Aging" },
    { clave: "pagos_posteriores", titulo: "Pagos Posteriores",
      subtitulo: "Pagos posteriores como evidencia del pasivo.", icono: "refresh", color: "blue", relacionados: ["RQ-002", "RQ-005"], seccion: "sec-05_Pagos_posteriores" },
    { clave: "pasivos_no_registrados", titulo: "Búsqueda de Pasivos No Registrados",
      subtitulo: "Integridad del pasivo (NIA 505/500).", icono: "search", color: "red", relacionados: ["RQ-002", "RQ-006"], seccion: "sec-06_Pasivos_no_registrados" },
    { clave: "confirmaciones", titulo: "Confirmaciones de Proveedores",
      subtitulo: "Cotejo de respuestas de confirmación.", icono: "people", color: "purple", relacionados: ["RQ-004"], seccion: "sec-07_Confirmaciones" },
    { clave: "corte", titulo: "Corte de Compras",
      subtitulo: "Prueba de corte de compras y recepciones.", icono: "calendar", color: "gold", relacionados: ["RQ-006"], seccion: "sec-08_Corte_compras" },
    { clave: "costo_amortizado", titulo: "Costo Amortizado e Intereses",
      subtitulo: "Compras a plazo e interés implícito.", icono: "calc", color: "blue", relacionados: ["RQ-007", "RQ-003"], seccion: "sec-09_Costo_amortizado" },
    { clave: "clasificacion", titulo: "Clasificación Corriente / No Corriente",
      subtitulo: "Presentación del pasivo por vencimiento.", icono: "list", color: "teal", relacionados: ["RQ-001"], seccion: "sec-10_Clasificacion" },
    { clave: "asientos", titulo: "Asientos de Ajuste",
      subtitulo: "Ajustes propuestos al saldo.", icono: "sliders", color: "blue", relacionados: ["RQ-003"], seccion: "sec-12_Asientos" },
  ],
};

// --- Inventarios, producción y costo de ventas (inventarios_costos) ---
const INVENTARIOS = {
  processor: "inventarios_costos",
  icono: "box", color: "gold",
  eyebrow: "INVENTARIOS Y COSTOS",
  titulo: "Inventarios y Costos",
  subtitulo: "Existencia, Costo y Obsolescencia · Auditoría Externa",
  principales: [
    { id: "RQ-001", titulo: "Inventario Valorado (Kardex)", icono: "box", color: "gold", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Costeo de Producción", icono: "chart", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-003", titulo: "Movimiento por Línea Vendida", icono: "list", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-004", titulo: "Documentos de Corte", icono: "calendar", color: "teal", tipos: ".xlsx / .csv" },
    { id: "RQ-011", titulo: "Libro Mayor de Inventario", icono: "book", color: "gold", tipos: ".xlsx / .csv" },
    { id: "RQ-012", titulo: "Inventario del Año Anterior", icono: "clock", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-005", titulo: "Actas de Recuento Físico", icono: "doc", color: "purple", tipos: ".pdf / .docx" },
    { id: "RQ-006", titulo: "Ventas y Precios Posteriores", icono: "bank", color: "teal", tipos: ".xlsx / .pdf" },
    { id: "RQ-008", titulo: "Política de Obsolescencia", icono: "shield", color: "red", tipos: ".pdf / .docx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Inventarios",
      subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "inventario", titulo: "Inventario Valorado",
      subtitulo: "Sumaria y detalle por ítem del kardex.", icono: "table", color: "gold", relacionados: ["RQ-001"], seccion: "sec-03_Inventario" },
    { clave: "conteo", titulo: "Existencia (Conteo vs Kardex)",
      subtitulo: "Observación del recuento físico (NIA 501).", icono: "search", color: "purple", relacionados: ["RQ-005", "RQ-001"], seccion: "sec-04_Conteo" },
    { clave: "prueba_costo", titulo: "Prueba de Costo",
      subtitulo: "Cotejo del costo unitario contra soporte.", icono: "calc", color: "blue", relacionados: ["RQ-001", "RQ-010"], seccion: "sec-05_Prueba_costo" },
    { clave: "conciliacion", titulo: "Conciliación Kardex–Mayor",
      subtitulo: "Cuadre del inventario contra contabilidad.", icono: "refresh", color: "teal", relacionados: ["RQ-001"], seccion: "sec-06_Conciliacion" },
    { clave: "costo_prod_ventas", titulo: "Costo de Producción y Ventas",
      subtitulo: "Armado del costo y del costo de ventas.", icono: "chart", color: "green", relacionados: ["RQ-002", "RQ-003"], seccion: "sec-07_Costo_produccion" },
    { clave: "vnr", titulo: "Valor Realizable Neto (VNR)",
      subtitulo: "Medición al menor entre costo y VNR (NIC 2).", icono: "calc", color: "gold", relacionados: ["RQ-006"], seccion: "sec-09_VNR" },
    { clave: "obsolescencia", titulo: "Obsolescencia y Lenta Rotación",
      subtitulo: "Provisión por deterioro de inventario.", icono: "warning", color: "red", relacionados: ["RQ-008", "RQ-001"], seccion: "sec-10_Obsolescencia" },
    { clave: "excepcion_mp", titulo: "Excepción NIC 2.32 (Materias Primas)",
      subtitulo: "Materias primas cuyo producto se vende con utilidad.", icono: "shield", color: "purple", relacionados: ["RQ-006"], seccion: "sec-11_Excepcion_MP" },
    { clave: "corte", titulo: "Corte de Inventarios",
      subtitulo: "Prueba de corte de compras y ventas.", icono: "calendar", color: "blue", relacionados: ["RQ-004"], seccion: "sec-12_Corte" },
    { clave: "comparacion", titulo: "Comparación Año a Año",
      subtitulo: "Inventario sin movimiento (no rotó) vs. año anterior.", icono: "refresh", color: "teal", relacionados: ["RQ-012", "RQ-001"], seccion: "sec-17_Comparacion" },
    { clave: "sumaria", titulo: "Sumaria del Inventario",
      subtitulo: "Resumen por bodega y por tipo de inventario.", icono: "table", color: "gold", relacionados: ["RQ-001"], seccion: "sec-18_Sumaria" },
    { clave: "movimiento_mayor", titulo: "Movimiento del Libro Mayor",
      subtitulo: "Debe, Haber y saldo por cuenta del mayor.", icono: "book", color: "blue", relacionados: ["RQ-011"], seccion: "sec-19_Movimiento" },
    { clave: "integridad", titulo: "Pruebas de Integridad",
      subtitulo: "Lo del cliente frente al recálculo del auditor.", icono: "search", color: "purple", relacionados: ["RQ-001", "RQ-011"], seccion: "sec-20_Integridad" },
  ],
};

// --- Ingresos de contratos con clientes (ingresos_contratos) ---
const INGRESOS = {
  processor: "ingresos_contratos",
  icono: "line", color: "green",
  eyebrow: "INGRESOS DE CONTRATOS CON CLIENTES",
  titulo: "Ingresos",
  subtitulo: "Contratos con Clientes · Auditoría Externa",
  principales: [
    { id: "RQ-001", titulo: "Anexo de Contratos por Obligación", icono: "chart", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Mayor de Ingresos", icono: "book", color: "blue", tipos: ".xlsx / .pdf" },
    { id: "RQ-003", titulo: "Contratos y Órdenes de Compra", icono: "doc", color: "gold", tipos: "PDF" },
    { id: "RQ-004", titulo: "Guías de Remisión / Actas", icono: "box", color: "purple", tipos: ".pdf / .xlsx" },
    { id: "RQ-006", titulo: "Notas de Crédito Posteriores", icono: "refresh", color: "red", tipos: ".xlsx / .pdf" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Ingresos",
      subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "detalle", titulo: "Detalle por Obligación",
      subtitulo: "Sumaria y detalle por obligación de desempeño.", icono: "table", color: "green", relacionados: ["RQ-001", "RQ-002"], seccion: "sec-03_Detalle" },
    { clave: "precio", titulo: "Precio y Asignación",
      subtitulo: "Precio de la transacción y su asignación.", icono: "calc", color: "gold", relacionados: ["RQ-001", "RQ-007"], seccion: "sec-04_Precio_variable" },
    { clave: "satisfaccion", titulo: "Satisfacción y % de Avance",
      subtitulo: "Reconocimiento en el tiempo o a un punto.", icono: "chart", color: "teal", relacionados: ["RQ-003", "RQ-005"], seccion: "sec-06_Satisfaccion" },
    { clave: "reconocimiento", titulo: "Ingreso Reconocible vs Registrado",
      subtitulo: "Comparación con lo contabilizado.", icono: "search", color: "purple", relacionados: ["RQ-002"], seccion: "sec-09_Reconocimiento" },
    { clave: "devoluciones", titulo: "Devoluciones y Notas de Crédito",
      subtitulo: "Contraprestación variable posterior al cierre.", icono: "refresh", color: "red", relacionados: ["RQ-006"], seccion: "sec-07_Devoluciones" },
    { clave: "financiacion", titulo: "Componente de Financiación",
      subtitulo: "Ventas a plazo e interés implícito.", icono: "calc", color: "blue", relacionados: ["RQ-008"], seccion: "sec-08_Financiacion" },
    { clave: "activo_pasivo", titulo: "Activo y Pasivo del Contrato",
      subtitulo: "Facturación anticipada y por facturar.", icono: "list", color: "gold", relacionados: ["RQ-002"], seccion: "sec-10_Activo_pasivo" },
    { clave: "corte", titulo: "Corte de Ingresos",
      subtitulo: "Prueba de corte de ventas.", icono: "calendar", color: "blue", relacionados: ["RQ-004"], seccion: "sec-11_Corte" },
    { clave: "asientos", titulo: "Asientos de Ajuste",
      subtitulo: "Ajustes propuestos al saldo.", icono: "sliders", color: "green", relacionados: ["RQ-002"], seccion: "sec-14_Asientos" },
  ],
};


// === Etapas 2-5 · resto de herramientas del catálogo ===

const PPE = {
  processor: "ppe_propiedad_planta",
  icono: "building", color: "blue",
  eyebrow: "PROPIEDAD, PLANTA Y EQUIPO",
  titulo: "Propiedad, Planta y Equipo",
  subtitulo: "Auditoría de PPE: depreciación, componentes, revaluación, deterioro y costos por préstamos",
  principales: [
    { id: "RQ-011", titulo: "Variaciones de Cuentas (Sumaria)", icono: "chart", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-010", titulo: "Libro Mayor de Activos Fijos", icono: "book", color: "teal", tipos: ".xlsx / .csv" },
    { id: "RQ-001", titulo: "Anexo de Activos Fijos", icono: "doc", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-004", titulo: "Política de Activos Fijos", icono: "shield", color: "gold", tipos: ".pdf / .docx" },
    { id: "RQ-012", titulo: "Facturas de Adiciones", icono: "coins", color: "blue", tipos: "PDF" },
    { id: "RQ-009", titulo: "Facturas de Salidas / Bajas", icono: "refresh", color: "red", tipos: "PDF" },
    { id: "RQ-005", titulo: "Informe de Perito · Revaluación", icono: "chart", color: "purple", tipos: "PDF" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Propiedad, Planta y Equipo", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "sumaria", titulo: "Sumaria y Auxiliar de Activos", subtitulo: "Cédula sumaria (variaciones) y detalle por activo.", icono: "table", color: "green", relacionados: ["RQ-011", "RQ-001"], seccion: "sec-23_Sumaria" },
    { clave: "depreciacion", titulo: "Recálculo de Depreciación y VNL", subtitulo: "Depreciación auditada y valor neto en libros.", icono: "calc", color: "purple", relacionados: ["RQ-001", "RQ-004"], seccion: "sec-04_Depreciacion" },
    { clave: "vidas_utiles", titulo: "Vidas Útiles, Residual y Método", subtitulo: "Revisión de vidas útiles, valor residual y método.", icono: "clock", color: "gold", relacionados: ["RQ-004"], seccion: "sec-05_Vidas_residual" },
    { clave: "componentes", titulo: "Componentes", subtitulo: "Depreciación por componentes significativos.", icono: "box", color: "teal", relacionados: ["RQ-001"], seccion: "sec-06_Componentes" },
    { clave: "adiciones", titulo: "Adiciones y Costos por Préstamos", subtitulo: "Altas del año y capitalización.", icono: "coins", color: "blue", relacionados: ["RQ-002", "RQ-012"], seccion: "sec-10_Adiciones" },
    { clave: "prestamos", titulo: "Préstamos, Capitalización y Desmantelamiento", subtitulo: "Costos por préstamos capitalizados y provisiones de desmantelamiento.", icono: "bank", color: "purple", relacionados: ["RQ-003", "RQ-007", "RQ-008"], seccion: "sec-11_Prestamos" },
    { clave: "revaluacion", titulo: "Revaluación", subtitulo: "Modelo de revaluación y superávit.", icono: "chart", color: "gold", relacionados: ["RQ-005"], seccion: "sec-08_Revaluacion" },
    { clave: "deterioro", titulo: "Deterioro", subtitulo: "Importe recuperable vs valor en libros.", icono: "warning", color: "red", relacionados: ["RQ-006"], seccion: "sec-09_Deterioro" },
    { clave: "bajas", titulo: "Bajas del Año", subtitulo: "Retiros y resultado en la baja.", icono: "refresh", color: "teal", relacionados: ["RQ-009"], seccion: "sec-07_Bajas" },
    { clave: "vaucheo", titulo: "Vaucheo de Facturas", subtitulo: "Cruce de facturas (adiciones y bajas) con lo registrado.", icono: "search", color: "gold", relacionados: ["RQ-012", "RQ-009"], seccion: "sec-26_Vaucheo" },
    { clave: "movimiento", titulo: "Movimiento, Conciliación y Ajustes", subtitulo: "Movimiento del mayor, roll-forward auxiliar-mayor y ajustes propuestos.", icono: "sliders", color: "blue", relacionados: ["RQ-010", "RQ-001"], seccion: "sec-14_Roll_forward" },
  ],
};

const PROPIEDADES_INVERSION = {
  processor: "propiedades_inversion",
  icono: "bank", color: "teal",
  eyebrow: "PROPIEDADES DE INVERSIÓN",
  titulo: "Propiedades de Inversión",
  subtitulo: "Auditoría de inmuebles de inversión: valor razonable, modelo del costo, transferencias y alquileres",
  principales: [
    { id: "RQ-001", titulo: "Registro de Propiedades de Inversión", icono: "building", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-005", titulo: "Escrituras y Certificados del Registro", icono: "shield", color: "gold", tipos: "PDF" },
    { id: "RQ-003", titulo: "Informes de Tasación al Corte", icono: "chart", color: "purple", tipos: "PDF" },
    { id: "RQ-004", titulo: "Contratos de Arrendamiento Vigentes", icono: "bank", color: "blue", tipos: "PDF" },
    { id: "RQ-007", titulo: "Gastos Directos de Operación", icono: "coins", color: "red", tipos: ".xlsx / .pdf" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Propiedades de Inversión", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "registro", titulo: "Registro y Titularidad de Inmuebles", subtitulo: "Existencia y derechos sobre los inmuebles.", icono: "building", color: "green", relacionados: ["RQ-001", "RQ-005"], seccion: "sec-03_Inmuebles" },
    { clave: "clasificacion", titulo: "Clasificación", subtitulo: "Clasificación como propiedad de inversión.", icono: "list", color: "teal", relacionados: ["RQ-001", "RQ-006"], seccion: "sec-04_Clasificacion" },
    { clave: "valor_razonable", titulo: "Valor Razonable", subtitulo: "Costo inicial y medición a valor razonable.", icono: "chart", color: "purple", relacionados: ["RQ-003"], seccion: "sec-06_Valor_razonable" },
    { clave: "modelo_costo", titulo: "Modelo del Costo", subtitulo: "Depreciación y deterioro bajo modelo del costo.", icono: "calc", color: "gold", relacionados: ["RQ-001"], seccion: "sec-07_Modelo_costo" },
    { clave: "medicion", titulo: "Medición Auditada por Inmueble", subtitulo: "Medición auditada y diferencias por inmueble.", icono: "table", color: "blue", relacionados: ["RQ-003"], seccion: "sec-08_Medicion" },
    { clave: "transferencias", titulo: "Transferencias", subtitulo: "Cambios de uso y transferencias.", icono: "refresh", color: "gold", relacionados: ["RQ-006"], seccion: "sec-09_Transferencias" },
    { clave: "superavit", titulo: "Superávit de Revaluación", subtitulo: "Historial del superávit y cambios en patrimonio.", icono: "pie", color: "purple", relacionados: ["RQ-009"], seccion: "sec-10_Superavit" },
    { clave: "alquileres", titulo: "Ingresos por Alquiler", subtitulo: "Ingresos por arrendamiento del ejercicio.", icono: "bank", color: "teal", relacionados: ["RQ-004"], seccion: "sec-11_Alquileres" },
    { clave: "bajas", titulo: "Bajas", subtitulo: "Retiros del ejercicio y resultado en la baja.", icono: "box", color: "red", relacionados: ["RQ-002"], seccion: "sec-12_Bajas" },
    { clave: "conciliacion", titulo: "Sumaria y Conciliación", subtitulo: "Cédula sumaria y conciliación de saldos.", icono: "sliders", color: "green", relacionados: ["RQ-001"], seccion: "sec-13_Conciliacion" },
  ],
};

const INTANGIBLES = {
  processor: "intangibles_goodwill",
  icono: "book", color: "purple",
  eyebrow: "INTANGIBLES Y GOODWILL",
  titulo: "Intangibles y Goodwill",
  subtitulo: "Auditoría de intangibles: reconocimiento, amortización, vida útil, deterioro y goodwill",
  principales: [
    { id: "RQ-001", titulo: "Auxiliar de Intangibles y Goodwill", icono: "doc", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-005", titulo: "Contratos de Licencias, Marcas y Patentes", icono: "shield", color: "gold", tipos: "PDF" },
    { id: "RQ-002", titulo: "Memorias de Proyectos de Desarrollo", icono: "search", color: "blue", tipos: ".pdf / .docx / .xlsx" },
    { id: "RQ-006", titulo: "Análisis de Vida Útil y Valor Residual", icono: "clock", color: "teal", tipos: ".pdf / .docx / .xlsx" },
    { id: "RQ-003", titulo: "Pruebas de Deterioro", icono: "warning", color: "red", tipos: ".xlsx / .pdf" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Intangibles y Goodwill", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "auxiliar", titulo: "Auxiliar de Intangibles y Goodwill", subtitulo: "Detalle por partida y titularidad.", icono: "book", color: "green", relacionados: ["RQ-001", "RQ-005"], seccion: "sec-03_Intangibles" },
    { clave: "reconocimiento", titulo: "Reconocimiento e I+D", subtitulo: "Criterios de capitalización (NIC 38.57).", icono: "search", color: "teal", relacionados: ["RQ-002"], seccion: "sec-04_Reconocimiento" },
    { clave: "amortizacion", titulo: "Amortización", subtitulo: "Recálculo de amortización y vida finita/indefinida.", icono: "calc", color: "gold", relacionados: ["RQ-007", "RQ-001"], seccion: "sec-05_Amortizacion" },
    { clave: "vida_util", titulo: "Vida Útil y Valor Residual", subtitulo: "Revisión de vida útil y residual al cierre.", icono: "clock", color: "purple", relacionados: ["RQ-006"], seccion: "sec-06_Vida_util" },
    { clave: "deterioro", titulo: "Deterioro e Importe Recuperable", subtitulo: "Valor en uso y VR menos costos de disposición.", icono: "warning", color: "red", relacionados: ["RQ-003"], seccion: "sec-07_Deterioro" },
    { clave: "goodwill", titulo: "Goodwill y Combinaciones de Negocios", subtitulo: "Asignación del precio de compra y prueba de goodwill.", icono: "bank", color: "purple", relacionados: ["RQ-004", "RQ-003"] },
    { clave: "reversion", titulo: "Reversión del Deterioro", subtitulo: "Reversiones admitidas y su límite.", icono: "refresh", color: "gold", relacionados: ["RQ-003"], seccion: "sec-08_Reversion" },
    { clave: "ajuste", titulo: "Valor Neto y Ajuste Propuesto", subtitulo: "Valor neto auditado y ajustes propuestos.", icono: "sliders", color: "blue", relacionados: ["RQ-001"], seccion: "sec-09_Ajuste" },
  ],
};

const ACTIVOS_BIOLOGICOS = {
  processor: "activos_biologicos",
  icono: "box", color: "green",
  eyebrow: "ACTIVOS BIOLÓGICOS",
  titulo: "Activos Biológicos",
  subtitulo: "Auditoría bajo NIC 41: existencia, valor razonable menos costos de venta, transformación biológica y cosecha",
  principales: [
    { id: "RQ-001", titulo: "Anexo de Activos Biológicos por Lote", icono: "list", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-005", titulo: "Actas de Conteo y Registros de Campo", icono: "people", color: "gold", tipos: ".pdf / .xlsx" },
    { id: "RQ-003", titulo: "Precios de Mercado o Informe del Perito", icono: "chart", color: "purple", tipos: ".pdf / .xlsx" },
    { id: "RQ-004", titulo: "Detalle de Costos de Venta", icono: "coins", color: "blue", tipos: ".xlsx / .pdf" },
    { id: "RQ-007", titulo: "Mayor de Activos Biológicos", icono: "book", color: "red", tipos: ".xlsx / .pdf" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Activos Biológicos", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "clasificacion", titulo: "Clasificación y Datos", subtitulo: "Clasificación de activos biológicos y sus datos.", icono: "list", color: "green", relacionados: ["RQ-001"], seccion: "sec-03_Activos" },
    { clave: "existencia", titulo: "Existencia: Conteo vs Registros", subtitulo: "Conteo físico contra registros de campo.", icono: "search", color: "teal", relacionados: ["RQ-005", "RQ-001"], seccion: "sec-04_Existencia" },
    { clave: "valoracion", titulo: "Valoración: VR menos Costos de Venta", subtitulo: "Valor razonable menos costos de venta.", icono: "coins", color: "gold", relacionados: ["RQ-003", "RQ-004"], seccion: "sec-05_Valoracion" },
    { clave: "transformacion", titulo: "Transformación Biológica y Cambio de VR", subtitulo: "Cambio de valor razonable del ejercicio.", icono: "refresh", color: "purple", relacionados: ["RQ-007", "RQ-005"], seccion: "sec-06_Transformacion" },
    { clave: "conciliacion", titulo: "Conciliación de Cambios (NIC 41.50)", subtitulo: "Conciliación del movimiento del período.", icono: "table", color: "blue", relacionados: ["RQ-007"], seccion: "sec-07_Conciliacion" },
    { clave: "modelo_costo", titulo: "Modelo del Costo y Deterioro", subtitulo: "Medición al costo cuando el VR no es fiable.", icono: "warning", color: "red", relacionados: ["RQ-006"], seccion: "sec-08_Modelo_costo" },
    { clave: "cosecha", titulo: "Producto Agrícola en la Cosecha", subtitulo: "Producción cosechada en el punto de cosecha.", icono: "calendar", color: "gold", relacionados: ["RQ-002"], seccion: "sec-09_Cosecha" },
  ],
};

const PRESTAMOS = {
  processor: "prestamos_obligaciones",
  icono: "bank", color: "purple",
  eyebrow: "PRÉSTAMOS Y OBLIGACIONES FINANCIERAS",
  titulo: "Préstamos y Obligaciones Financieras",
  subtitulo: "Costo amortizado, TIE, covenants, confirmaciones y modificaciones de deuda",
  principales: [
    { id: "RQ-001", titulo: "Anexo de Préstamos al Corte", icono: "doc", color: "purple", tipos: ".xlsx / .csv" },
    { id: "RQ-003", titulo: "Contratos y Tablas de Amortización", icono: "book", color: "blue", tipos: ".pdf / .xlsx" },
    { id: "RQ-004", titulo: "Confirmaciones Bancarias", icono: "people", color: "gold", tipos: "PDF" },
    { id: "RQ-005", titulo: "Liquidaciones de Desembolso", icono: "bank", color: "green", tipos: ".pdf / .xlsx" },
    { id: "RQ-008", titulo: "Mayor y Auxiliares de Préstamos", icono: "list", color: "teal", tipos: ".xlsx / .pdf" },
    { id: "RQ-006", titulo: "Covenants y Cartas de Dispensa", icono: "shield", color: "red", tipos: ".pdf / .xlsx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Préstamos y Obligaciones", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "universo", titulo: "Universo de Préstamos", subtitulo: "Sumaria y detalle por operación de deuda.", icono: "table", color: "green", relacionados: ["RQ-001", "RQ-008"], seccion: "sec-03_Prestamos" },
    { clave: "tie_costo_amortizado", titulo: "TIE y Costo Amortizado", subtitulo: "Tasa efectiva, amortización y costo amortizado al corte.", icono: "calc", color: "purple", relacionados: ["RQ-003", "RQ-005"], seccion: "sec-04_Condiciones_TIE" },
    { clave: "comisiones", titulo: "Comisiones y Costos de Transacción", subtitulo: "Costos capitalizables al pasivo financiero.", icono: "coins", color: "gold", relacionados: ["RQ-005"], seccion: "sec-07_Comisiones" },
    { clave: "intereses", titulo: "Recálculo de Intereses", subtitulo: "Gasto financiero e intereses por pagar.", icono: "line", color: "teal", relacionados: ["RQ-008", "RQ-003"], seccion: "sec-08_Intereses" },
    { clave: "confirmaciones", titulo: "Confirmaciones Bancarias", subtitulo: "Cotejo de respuestas de confirmación (NIA 505).", icono: "people", color: "blue", relacionados: ["RQ-004"], seccion: "sec-09_Confirmacion" },
    { clave: "covenants", titulo: "Covenants y Dispensas", subtitulo: "DSCR, ratios de endeudamiento y cartas de dispensa.", icono: "shield", color: "red", relacionados: ["RQ-006", "RQ-007"], seccion: "sec-10_Covenants" },
    { clave: "clasificacion", titulo: "Clasificación Corriente / No Corriente", subtitulo: "Presentación del pasivo por vencimiento.", icono: "list", color: "green", relacionados: ["RQ-001"], seccion: "sec-11_Clasificacion" },
    { clave: "modificaciones", titulo: "Modificaciones y Prueba del 10 %", subtitulo: "Flujos de la adenda descontados a la TIE original (NIIF 9).", icono: "refresh", color: "gold", relacionados: ["RQ-002", "RQ-003"], seccion: "sec-14_Flujos_modificacion" },
    { clave: "conciliacion", titulo: "Conciliación y Ajustes", subtitulo: "Cuadre contra libros y ajustes propuestos.", icono: "gears", color: "blue", relacionados: ["RQ-008", "RQ-001"], seccion: "sec-13_Conciliacion" },
  ],
};

const INVERSIONES = {
  processor: "inversiones_instrumentos",
  icono: "pie", color: "teal",
  eyebrow: "INVERSIONES E INSTRUMENTOS FINANCIEROS",
  titulo: "Inversiones e Instrumentos Financieros",
  subtitulo: "Clasificación, costo amortizado, valor razonable, deterioro y reclasificación",
  principales: [
    { id: "RQ-001", titulo: "Anexo de Inversiones por Instrumento", icono: "doc", color: "teal", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Estados de Cuenta y Confirmaciones", icono: "bank", color: "blue", tipos: ".pdf / .xlsx" },
    { id: "RQ-003", titulo: "Política de Inversiones y Modelo de Negocio", icono: "shield", color: "purple", tipos: ".pdf / .docx" },
    { id: "RQ-004", titulo: "Prospectos y Contratos de los Títulos", icono: "book", color: "green", tipos: "PDF" },
    { id: "RQ-005", titulo: "Vector de Precios y Valuaciones", icono: "chart", color: "gold", tipos: ".pdf / .xlsx" },
    { id: "RQ-007", titulo: "Calificaciones de Riesgo de Emisores", icono: "warning", color: "red", tipos: ".pdf / .xlsx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Inversiones", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "inventario", titulo: "Inventario de Inversiones", subtitulo: "Sumaria y detalle por instrumento.", icono: "table", color: "teal", relacionados: ["RQ-001", "RQ-002"], seccion: "sec-03_Inventario" },
    { clave: "clasificacion", titulo: "Clasificación y Modelo de Negocio", subtitulo: "SPPI y modelo de negocio (NIIF 9).", icono: "sliders", color: "purple", relacionados: ["RQ-003", "RQ-004"], seccion: "sec-04_Clasificacion" },
    { clave: "costo_amortizado", titulo: "Costo Amortizado y TIE", subtitulo: "Tasa efectiva y medición a costo amortizado.", icono: "calc", color: "green", relacionados: ["RQ-004", "RQ-001"], seccion: "sec-05_Costo_amortizado" },
    { clave: "valor_razonable", titulo: "Valor Razonable y Jerarquía", subtitulo: "Medición a valor razonable y niveles NIIF 13.", icono: "chart", color: "gold", relacionados: ["RQ-005"], seccion: "sec-06_Valor_razonable" },
    { clave: "intereses_dividendos", titulo: "Intereses y Dividendos", subtitulo: "Rendimientos devengados y dividendos decretados.", icono: "coins", color: "blue", relacionados: ["RQ-006", "RQ-001"], seccion: "sec-07_Intereses_dividendos" },
    { clave: "deterioro", titulo: "Deterioro", subtitulo: "Pérdida crediticia esperada por instrumento.", icono: "warning", color: "red", relacionados: ["RQ-007"], seccion: "sec-08_Deterioro" },
    { clave: "reclasificacion", titulo: "Reclasificación", subtitulo: "Cambios de modelo de negocio y su efecto.", icono: "refresh", color: "purple", relacionados: ["RQ-003"], seccion: "sec-09_Reclasificacion" },
    { clave: "conciliacion", titulo: "Conciliación y Ajustes", subtitulo: "Cuadre contra libros y ajustes propuestos.", icono: "gears", color: "green", relacionados: ["RQ-001", "RQ-002"], seccion: "sec-10_Conciliacion" },
  ],
};

const PATRIMONIO = {
  processor: "patrimonio",
  icono: "building", color: "gold",
  eyebrow: "PATRIMONIO",
  titulo: "Patrimonio",
  subtitulo: "Movimiento patrimonial, capital, reservas, dividendos y clasificación deuda/patrimonio",
  principales: [
    { id: "RQ-001", titulo: "Movimiento de Cuentas Patrimoniales", icono: "chart", color: "gold", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Actas y Transacciones Patrimoniales", icono: "list", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-003", titulo: "Libro de Actas de Junta General", icono: "book", color: "purple", tipos: "PDF" },
    { id: "RQ-004", titulo: "Escrituras y Certificado Supercias", icono: "bank", color: "green", tipos: "PDF" },
    { id: "RQ-006", titulo: "Estado de Cambios en el Patrimonio", icono: "doc", color: "teal", tipos: ".xlsx / .pdf" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Patrimonio", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "movimiento", titulo: "Movimiento Patrimonial", subtitulo: "Sumaria y detalle por componente del patrimonio.", icono: "table", color: "gold", relacionados: ["RQ-001", "RQ-006"], seccion: "sec-03_Movimiento" },
    { clave: "transacciones", titulo: "Actas y Transacciones", subtitulo: "Cotejo de movimientos contra actas de junta.", icono: "book", color: "purple", relacionados: ["RQ-002", "RQ-003"], seccion: "sec-04_Transacciones" },
    { clave: "capital", titulo: "Capital y Aumentos", subtitulo: "Aportes e inscripción de aumentos de capital.", icono: "building", color: "green", relacionados: ["RQ-004"], seccion: "sec-07_Capital" },
    { clave: "reserva_legal", titulo: "Reserva Legal", subtitulo: "Apropiación y suficiencia de la reserva legal.", icono: "shield", color: "teal", relacionados: ["RQ-001"], seccion: "sec-05_Reserva_legal" },
    { clave: "dividendos", titulo: "Dividendos", subtitulo: "Decreto, pago y retención de dividendos.", icono: "coins", color: "gold", relacionados: ["RQ-002", "RQ-003"], seccion: "sec-06_Dividendos" },
    { clave: "clasificacion", titulo: "Clasificación Deuda / Patrimonio", subtitulo: "Instrumentos con opción de venta y preferentes (NIC 32).", icono: "sliders", color: "red", relacionados: ["RQ-005"], seccion: "sec-08_Clasificacion" },
    { clave: "recompra", titulo: "Recompra de Acciones Propias", subtitulo: "Acciones propias en cartera y su presentación.", icono: "refresh", color: "purple", relacionados: ["RQ-002"], seccion: "sec-09_Recompra" },
    { clave: "ajustes", titulo: "Patrimonio Auditado y Asientos", subtitulo: "Ajustes propuestos y conciliación final.", icono: "gears", color: "blue", relacionados: ["RQ-006", "RQ-001"], seccion: "sec-10_Ajuste" },
  ],
};

const PROVISIONES = {
  processor: "provisiones_contingencias",
  icono: "warning", color: "red",
  eyebrow: "PROVISIONES Y CONTINGENCIAS",
  titulo: "Provisiones y Contingencias",
  subtitulo: "Obligación presente, mejor estimación, valor presente, litigios y contingencias a revelar",
  principales: [
    { id: "RQ-001", titulo: "Detalle de Provisiones y Contingencias", icono: "chart", color: "red", tipos: ".xlsx / .csv" },
    { id: "RQ-003", titulo: "Respuestas de los Abogados", icono: "people", color: "gold", tipos: "PDF" },
    { id: "RQ-006", titulo: "Mayor de Provisiones y Gastos", icono: "list", color: "blue", tipos: ".xlsx / .pdf" },
    { id: "RQ-007", titulo: "Carta de Manifestaciones de la Gerencia", icono: "doc", color: "purple", tipos: "PDF" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Provisiones y Contingencias", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "provisiones", titulo: "Provisiones y Contingencias", subtitulo: "Sumaria y detalle de provisiones del cliente.", icono: "table", color: "green", relacionados: ["RQ-001", "RQ-006"], seccion: "sec-03_Provisiones" },
    { clave: "obligacion_probabilidad", titulo: "Obligación Presente y Probabilidad", subtitulo: "Reconocimiento y probabilidad de salida (NIC 37).", icono: "search", color: "purple", relacionados: ["RQ-001", "RQ-007"], seccion: "sec-05_Obligacion_prob" },
    { clave: "mejor_estimacion", titulo: "Mejor Estimación", subtitulo: "Cuantificación de la mejor estimación.", icono: "calc", color: "gold", relacionados: ["RQ-001"], seccion: "sec-06_Mejor_estimacion" },
    { clave: "valor_presente", titulo: "Valor Presente y Reversión del Descuento", subtitulo: "Descuento y actualización financiera del período.", icono: "coins", color: "teal", relacionados: ["RQ-006"], seccion: "sec-07_Valor_presente" },
    { clave: "litigios", titulo: "Litigios y Cartas de Abogados", subtitulo: "Cotejo con respuestas de los abogados (NIA 501).", icono: "people", color: "blue", relacionados: ["RQ-003", "RQ-007"], seccion: "sec-09_Litigios_abogados" },
    { clave: "garantias", titulo: "Garantías", subtitulo: "Provisión por garantías por línea de producto.", icono: "shield", color: "green", relacionados: ["RQ-002", "RQ-001"], seccion: "sec-10_Garantias_calculo" },
    { clave: "onerosos", titulo: "Contratos Onerosos", subtitulo: "Provisión por contratos de carácter oneroso.", icono: "warning", color: "red", relacionados: ["RQ-004"], seccion: "sec-11_Onerosos" },
    { clave: "desmantelamiento", titulo: "Desmantelamiento", subtitulo: "Provisión por desmantelamiento y retiro.", icono: "box", color: "gold", relacionados: ["RQ-004"], seccion: "sec-12_Desmantelamiento" },
    { clave: "reconocimiento_contingencias", titulo: "Reconocimiento y Contingencias a Revelar", subtitulo: "Provisión requerida vs libros y contingencias a revelar.", icono: "list", color: "purple", relacionados: ["RQ-001", "RQ-005"], seccion: "sec-13_Reconocimiento" },
    { clave: "ajustes", titulo: "Ajustes y Conciliación", subtitulo: "Ajustes propuestos y conciliación final.", icono: "gears", color: "blue", relacionados: ["RQ-006", "RQ-001"], seccion: "sec-15_Ajustes" },
  ],
};

const NOMINA = {
  processor: "nomina_beneficios",
  icono: "people", color: "purple",
  eyebrow: "NÓMINA Y BENEFICIOS A EMPLEADOS",
  titulo: "Nómina y Beneficios a Empleados",
  subtitulo: "Recálculo de nómina, aportes IESS, beneficios sociales y obligaciones post-empleo (NIC 19)",
  principales: [
    { id: "RQ-001", titulo: "Anexo de Empleados del Ejercicio", icono: "people", color: "purple", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Resumen del Informe Actuarial", icono: "calc", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-003", titulo: "Roles de Pago y Contratos", icono: "doc", color: "teal", tipos: ".xlsx / .pdf" },
    { id: "RQ-004", titulo: "Planillas y Pagos del IESS", icono: "bank", color: "green", tipos: ".pdf / .xlsx" },
    { id: "RQ-005", titulo: "Informe Actuarial Completo y Censo", icono: "pdf", color: "red", tipos: ".pdf / .xlsx" },
    { id: "RQ-006", titulo: "Mayores de Nómina y Pasivos Laborales", icono: "book", color: "gold", tipos: ".xlsx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Nómina y Beneficios", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "recalculo_nomina", titulo: "Empleados y Recálculo de Nómina", subtitulo: "Recálculo de bruto y neto por empleado.", icono: "table", color: "purple", relacionados: ["RQ-001", "RQ-003"], seccion: "sec-06_Recalculo_nomina" },
    { clave: "iess", titulo: "Aportes IESS y Planillas", subtitulo: "Cotejo de aportes y planillas del IESS.", icono: "bank", color: "green", relacionados: ["RQ-004"], seccion: "sec-07_IESS" },
    { clave: "decimos", titulo: "Décimo Tercero y Décimo Cuarto", subtitulo: "Recálculo de décimos y su provisión.", icono: "coins", color: "gold", relacionados: ["RQ-001", "RQ-003"], seccion: "sec-08_Decimo_tercero" },
    { clave: "vacaciones", titulo: "Vacaciones", subtitulo: "Provisión y pago de vacaciones.", icono: "calendar", color: "teal", relacionados: ["RQ-007", "RQ-001"], seccion: "sec-10_Vacaciones" },
    { clave: "fondo_reserva", titulo: "Fondo de Reserva", subtitulo: "Recálculo del fondo de reserva.", icono: "box", color: "blue", relacionados: ["RQ-004", "RQ-001"], seccion: "sec-11_Fondo_reserva" },
    { clave: "dbo_actuarial", titulo: "Jubilación Patronal y Desahucio: DBO", subtitulo: "Obligación por beneficios definidos.", icono: "calc", color: "red", relacionados: ["RQ-002", "RQ-005"], seccion: "sec-12_DBO_actuarial" },
    { clave: "resultados_ori", titulo: "Costo Post-Empleo: Resultados y ORI", subtitulo: "Gasto en resultados y remediciones en ORI.", icono: "pie", color: "purple", relacionados: ["RQ-005", "RQ-002"], seccion: "sec-13_Resultados_ORI" },
    { clave: "censo_actuarial", titulo: "Censo Actuarial y Desahucio Legal", subtitulo: "Validación del censo enviado al actuario.", icono: "people", color: "gold", relacionados: ["RQ-005"], seccion: "sec-14_Censo_actuarial" },
    { clave: "conciliacion_gl", titulo: "Conciliación Nómina–Mayor", subtitulo: "Cuadre de nómina contra el mayor contable.", icono: "refresh", color: "green", relacionados: ["RQ-006", "RQ-001"], seccion: "sec-15_Conciliacion_GL" },
    { clave: "ajustes", titulo: "Ajustes Propuestos", subtitulo: "Asientos de ajuste sobre nómina y pasivos.", icono: "gears", color: "blue", relacionados: ["RQ-006"], seccion: "sec-16_Ajustes" },
  ],
};

const IMPUESTO = {
  processor: "impuesto_corriente_diferido",
  icono: "calc", color: "blue",
  eyebrow: "IMPUESTO CORRIENTE Y DIFERIDO",
  titulo: "Impuesto Corriente y Diferido",
  subtitulo: "Conciliación tributaria, diferencias temporarias, activo diferido y tasa efectiva (NIC 12)",
  principales: [
    { id: "RQ-001", titulo: "Conciliación Tributaria (F-101)", icono: "table", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Anexo de Diferencias Temporarias", icono: "sliders", color: "purple", tipos: ".xlsx / .csv" },
    { id: "RQ-004", titulo: "Formulario 101 Presentado", icono: "pdf", color: "red", tipos: ".pdf" },
    { id: "RQ-005", titulo: "Retenciones, Anticipos y Crédito Tributario", icono: "coins", color: "gold", tipos: ".pdf / .xlsx" },
    { id: "RQ-006", titulo: "Proyecciones y Recuperabilidad", icono: "line", color: "teal", tipos: ".xlsx / .pdf" },
    { id: "RQ-007", titulo: "Mayor de Impuesto y Gasto por Impuesto", icono: "book", color: "green", tipos: ".xlsx / .pdf" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Impuesto Corriente y Diferido", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "conciliacion", titulo: "Conciliación Tributaria", subtitulo: "Renglones del F-101 y base imponible.", icono: "table", color: "blue", relacionados: ["RQ-001", "RQ-004"], seccion: "sec-03_Conciliacion" },
    { clave: "impuesto_corriente", titulo: "Impuesto Corriente", subtitulo: "Cálculo del impuesto causado y anticipos.", icono: "calc", color: "green", relacionados: ["RQ-001", "RQ-005"], seccion: "sec-04_Impuesto_corriente" },
    { clave: "perdidas", titulo: "Pérdidas Tributarias", subtitulo: "Amortización por año de origen.", icono: "line", color: "red", relacionados: ["RQ-003", "RQ-004"], seccion: "sec-05_Perdidas" },
    { clave: "diferencias_temp", titulo: "Diferencias Temporarias y Diferido", subtitulo: "Activos y pasivos por impuesto diferido.", icono: "sliders", color: "purple", relacionados: ["RQ-002"], seccion: "sec-06_Diferencias_temp" },
    { clave: "recuperabilidad", titulo: "Recuperabilidad del Activo Diferido", subtitulo: "Análisis de ganancias fiscales futuras.", icono: "search", color: "gold", relacionados: ["RQ-006"], seccion: "sec-08_Recuperabilidad" },
    { clave: "movimiento", titulo: "Movimiento: Resultados y ORI", subtitulo: "Efecto en resultados y en ORI.", icono: "chart", color: "teal", relacionados: ["RQ-007", "RQ-002"], seccion: "sec-09_Movimiento" },
    { clave: "compensacion", titulo: "Compensación y Presentación", subtitulo: "Neteo y presentación en el estado de situación.", icono: "box", color: "blue", relacionados: ["RQ-007"], seccion: "sec-10_Compensacion" },
    { clave: "tasa_efectiva", titulo: "Tasa Efectiva (NIC 12.81 c)", subtitulo: "Conciliación de la tasa efectiva.", icono: "pie", color: "purple", relacionados: ["RQ-001", "RQ-007"], seccion: "sec-11_Tasa_efectiva" },
    { clave: "partic_exentos", titulo: "Participación Atribuible a Exentos", subtitulo: "Participación de trabajadores sobre exentos.", icono: "coins", color: "gold", relacionados: ["RQ-008", "RQ-001"], seccion: "sec-13_Partic_exentos" },
    { clave: "asientos", titulo: "Asientos Propuestos", subtitulo: "Ajustes de impuesto corriente y diferido.", icono: "gears", color: "green", relacionados: ["RQ-007"], seccion: "sec-14_Asientos" },
  ],
};

const GASTOS = {
  processor: "gastos_analisis",
  icono: "line", color: "teal",
  eyebrow: "ANÁLISIS DE GASTOS",
  titulo: "Análisis de Gastos",
  subtitulo: "Análisis global, vouching, corte, devengo y partes relacionadas (NIA 520, 550)",
  principales: [
    { id: "RQ-001", titulo: "Sumaria de Cuentas de Gasto", icono: "table", color: "teal", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Muestra de Transacciones de Gasto", icono: "list", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-003", titulo: "Mayor de Gastos y Balance de Comprobación", icono: "book", color: "green", tipos: ".xlsx / .pdf" },
    { id: "RQ-004", titulo: "Facturas, Contratos y Aprobaciones", icono: "doc", color: "gold", tipos: ".pdf" },
    { id: "RQ-005", titulo: "Facturas y Pagos Posteriores al Cierre", icono: "calendar", color: "purple", tipos: ".pdf / .xlsx" },
    { id: "RQ-006", titulo: "Maestro de Partes Relacionadas", icono: "people", color: "red", tipos: ".xlsx / .pdf / .docx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Análisis de Gastos", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "analisis_global", titulo: "Análisis Global por Cuenta (NIA 520)", subtitulo: "Variaciones año actual, anterior y presupuesto.", icono: "chart", color: "teal", relacionados: ["RQ-001", "RQ-003"], seccion: "sec-03_Analisis_global" },
    { clave: "transacciones", titulo: "Transacciones de la Muestra", subtitulo: "Selección y marcas de la muestra de gasto.", icono: "list", color: "blue", relacionados: ["RQ-002"], seccion: "sec-05_Transacciones" },
    { clave: "vouching", titulo: "Verificación del Soporte Documental", subtitulo: "Vouching de facturas, contratos y pagos.", icono: "search", color: "gold", relacionados: ["RQ-004", "RQ-002"], seccion: "sec-06_Vouching" },
    { clave: "corte", titulo: "Corte de Gastos", subtitulo: "Prueba de corte sobre el período del servicio.", icono: "calendar", color: "purple", relacionados: ["RQ-005", "RQ-002"], seccion: "sec-07_Corte" },
    { clave: "devengo", titulo: "Devengo y Gastos Anticipados", subtitulo: "Reconocimiento en el período correcto.", icono: "clock", color: "green", relacionados: ["RQ-002", "RQ-003"], seccion: "sec-08_Devengo" },
    { clave: "partes_relacionadas", titulo: "Partes Relacionadas", subtitulo: "Identificación de transacciones con partes relacionadas.", icono: "people", color: "red", relacionados: ["RQ-006", "RQ-008"], seccion: "sec-10_Partes_relacionadas" },
    { clave: "rp_integridad", titulo: "Integridad de la Revelación de Partes Relacionadas", subtitulo: "Cobertura del maestro y la revelación.", icono: "shield", color: "gold", relacionados: ["RQ-006", "RQ-008"], seccion: "sec-11_RP_Integridad" },
    { clave: "inusuales", titulo: "Partidas Inusuales", subtitulo: "Detección de partidas atípicas de gasto.", icono: "warning", color: "red", relacionados: ["RQ-002"], seccion: "sec-12_Inusuales" },
    { clave: "tributario", titulo: "Referencia Tributaria (Ecuador)", subtitulo: "Deducibilidad y referencia fiscal.", icono: "calc", color: "blue", relacionados: ["RQ-003"], seccion: "sec-13_Tributario" },
    { clave: "asientos", titulo: "Asientos y Ajustes", subtitulo: "Ajustes propuestos y conciliación.", icono: "gears", color: "green", relacionados: ["RQ-003"], seccion: "sec-15_Asientos" },
  ],
};

const SEGUROS = {
  processor: "seguros_cobertura",
  icono: "shield", color: "gold",
  eyebrow: "SEGUROS Y COBERTURA",
  titulo: "Seguros y Cobertura",
  subtitulo: "Cobertura de activos, infraseguro, deducibles, prima anticipada y siniestros",
  principales: [
    { id: "RQ-001", titulo: "Maestro de Activos Asegurables", icono: "building", color: "gold", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Detalle de Pólizas Vigentes y Vencidas", icono: "list", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-003", titulo: "Pólizas y Endosos", icono: "pdf", color: "teal", tipos: ".pdf" },
    { id: "RQ-006", titulo: "Mayor de Seguros Pagados por Anticipado", icono: "book", color: "green", tipos: ".xlsx / .pdf" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Seguros y Cobertura", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "vigencia", titulo: "Vigencia de Pólizas al Corte", subtitulo: "Pólizas vigentes y vencidas a la fecha de corte.", icono: "calendar", color: "purple", relacionados: ["RQ-002", "RQ-003"], seccion: "sec-05_Vigencia" },
    { clave: "cobertura_activo", titulo: "Universo y Cobertura por Activo", subtitulo: "Cotejo del maestro de activos contra pólizas.", icono: "table", color: "gold", relacionados: ["RQ-001", "RQ-002"], seccion: "sec-06_Cobertura_activo" },
    { clave: "cobertura_poliza", titulo: "Cobertura por Póliza (Infraseguro)", subtitulo: "Suma asegurada frente al valor de referencia.", icono: "search", color: "teal", relacionados: ["RQ-002", "RQ-004"], seccion: "sec-07_Cobertura_poliza" },
    { clave: "deducibles_exposicion", titulo: "Deducibles y Exposición Máxima", subtitulo: "Deducibles y exposición neta por póliza.", icono: "sliders", color: "blue", relacionados: ["RQ-003"], seccion: "sec-08_Deducibles_exposicion" },
    { clave: "sin_cobertura", titulo: "Activos Sin Cobertura", subtitulo: "Activos asegurables sin póliza vigente.", icono: "warning", color: "red", relacionados: ["RQ-001", "RQ-002"], seccion: "sec-09_Sin_cobertura" },
    { clave: "prima_anticipada", titulo: "Prima Pagada por Anticipado", subtitulo: "Devengo del seguro prepagado.", icono: "coins", color: "green", relacionados: ["RQ-006"], seccion: "sec-10_Prima_anticipada" },
    { clave: "siniestros", titulo: "Siniestros Pendientes y Revelación", subtitulo: "Reclamos en curso y su revelación.", icono: "shield", color: "purple", relacionados: ["RQ-005"], seccion: "sec-11_Siniestros" },
    { clave: "ajustes", titulo: "Ajustes Propuestos y Conciliación", subtitulo: "Asientos de ajuste y cuadre con el mayor.", icono: "gears", color: "gold", relacionados: ["RQ-006"], seccion: "sec-13_Ajustes" },
  ],
};

// --- Arrendamientos (NIIF 16) ---
const ARRENDAMIENTOS = {
  processor: "arrendamientos",
  icono: "building", color: "teal",
  eyebrow: "ARRENDAMIENTOS",
  titulo: "Arrendamientos",
  subtitulo: "Clasificación, medición del pasivo y derecho de uso, amortización y venta con arrendamiento posterior (NIIF 16)",
  principales: [
    { id: "RQ-001", titulo: "Anexo de Contratos de Arrendamiento", icono: "doc", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Contratos Firmados y Adendas", icono: "book", color: "blue", tipos: ".pdf / .docx" },
    { id: "RQ-003", titulo: "Sustento de la Tasa Implícita o Incremental", icono: "coins", color: "gold", tipos: ".pdf / .xlsx" },
    { id: "RQ-004", titulo: "Mayor y Auxiliares (Pasivo, Derecho de Uso, Depreciación e Intereses)", icono: "list", color: "purple", tipos: ".xlsx / .pdf" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Arrendamientos", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "contratos", titulo: "Universo de Contratos", subtitulo: "Inventario y cobertura de contratos al corte.", icono: "building", color: "teal", relacionados: ["RQ-001", "RQ-002"], seccion: "sec-03_Contratos" },
    { clave: "clasificacion", titulo: "Identificación, Clasificación y Exenciones", subtitulo: "Alcance, corto plazo y bajo valor.", icono: "list", color: "gold", relacionados: ["RQ-001", "RQ-002"], seccion: "sec-04_Identificacion" },
    { clave: "plazo", titulo: "Plazo y Opciones", subtitulo: "Plazo razonablemente cierto y opciones.", icono: "calendar", color: "purple", relacionados: ["RQ-002", "RQ-007"], seccion: "sec-05_Plazo" },
    { clave: "medicion_inicial", titulo: "Medición Inicial", subtitulo: "Pasivo por arrendamiento y activo por derecho de uso.", icono: "calc", color: "green", relacionados: ["RQ-003", "RQ-004"], seccion: "sec-06_Medicion_inicial" },
    { clave: "amortizacion", titulo: "Tabla de Amortización", subtitulo: "Intereses y amortización del pasivo.", icono: "table", color: "blue", relacionados: ["RQ-003", "RQ-004"], seccion: "sec-09_Tabla_amortizacion" },
    { clave: "pasivo_corte", titulo: "Pasivo al Corte", subtitulo: "Porción corriente y no corriente.", icono: "coins", color: "teal", relacionados: ["RQ-004"], seccion: "sec-10_Pasivo_corte" },
    { clave: "derecho_uso", titulo: "Derecho de Uso", subtitulo: "Depreciación y deterioro del activo.", icono: "warning", color: "gold", relacionados: ["RQ-004", "RQ-005"], seccion: "sec-11_Derecho_uso" },
    { clave: "gasto_lineal", titulo: "Gasto Lineal", subtitulo: "Contratos exentos y operativos.", icono: "line", color: "purple", relacionados: ["RQ-001", "RQ-007"], seccion: "sec-12_Gasto_lineal" },
    { clave: "venta_arr_posterior", titulo: "Venta con Arrendamiento Posterior", subtitulo: "Medición inicial y posterior del sale & leaseback.", icono: "refresh", color: "red", relacionados: ["RQ-006", "RQ-008"], seccion: "sec-13_Venta_arr_posterior" },
    { clave: "conciliacion", titulo: "Conciliación y Ajuste", subtitulo: "Cruce con la contabilidad y asientos.", icono: "gears", color: "blue", relacionados: ["RQ-004"], seccion: "sec-15_Conciliacion" },
  ],
};

// --- Pérdida Crediticia Esperada (NIIF 9, simplificada) ---
const PCE_NIIF9 = {
  processor: "pce_simplificada_niif9",
  icono: "warning", color: "red",
  eyebrow: "PÉRDIDA CREDITICIA ESPERADA · NIIF 9",
  titulo: "Pérdida Crediticia Esperada (NIIF 9)",
  subtitulo: "Deterioro de cartera por enfoque simplificado: tasas históricas, matriz de provisiones y revelación NIIF 7",
  principales: [
    { id: "RQ-001", titulo: "Cartera por Factura al Corte", icono: "doc", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Cartera por Factura del Corte Anterior", icono: "book", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-004", titulo: "Información Prospectiva (Proyecciones e Indicadores)", icono: "line", color: "gold", tipos: ".pdf / .docx" },
    { id: "RQ-005", titulo: "Política de Crédito y Cobranza", icono: "shield", color: "red", tipos: ".pdf / .docx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Pérdida Crediticia Esperada", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "tasas_historicas", titulo: "Tasas Históricas", subtitulo: "Tasas de pérdida por tramo con castigos.", icono: "line", color: "teal", relacionados: ["RQ-002", "RQ-003"], seccion: "sec-03_Tasas_historicas" },
    { clave: "matriz_provisiones", titulo: "Matriz de Provisiones", subtitulo: "PCE por tramo con ajuste prospectivo.", icono: "table", color: "red", relacionados: ["RQ-001", "RQ-004"], seccion: "sec-04_Matriz_provisiones" },
    { clave: "revelacion_niif7", titulo: "Revelación NIIF 7 (35M/35N)", subtitulo: "Exposición al riesgo de crédito.", icono: "shield", color: "gold", relacionados: ["RQ-001"], seccion: "sec-05_Revelacion_NIIF7" },
    { clave: "movimiento", titulo: "Movimiento de la Provisión (NIIF 7 35H)", subtitulo: "Conciliación del saldo de la provisión.", icono: "refresh", color: "purple", relacionados: ["RQ-002", "RQ-003"], seccion: "sec-06_Movimiento" },
    { clave: "fiscal", titulo: "Fiscal e Impuesto Diferido", subtitulo: "Diferencia contable-fiscal y diferido.", icono: "calc", color: "blue", relacionados: ["RQ-001"], seccion: "sec-07_Fiscal" },
    { clave: "asientos", titulo: "Asientos Propuestos", subtitulo: "Ajustes al deterioro registrado.", icono: "gears", color: "teal", relacionados: ["RQ-001"], seccion: "sec-08_Asientos" },
    { clave: "detalle", titulo: "Detalle por Factura", subtitulo: "PCE calculada factura a factura.", icono: "list", color: "green", relacionados: ["RQ-001"], seccion: "sec-09_Detalle" },
    { clave: "castigos", titulo: "Castigos del Ejercicio", subtitulo: "Bajas de cartera del período.", icono: "warning", color: "red", relacionados: ["RQ-003"], seccion: "sec-11_Castigos" },
    { clave: "cobros_posteriores", titulo: "Cobros Posteriores al Cierre", subtitulo: "Evidencia de cobrabilidad tras el corte.", icono: "bank", color: "purple", relacionados: ["RQ-006"] },
  ],
};

// --- Pérdida Crediticia Esperada por cohortes (NIIF 9) — herramienta vigente (AUD-ECL-01) ---
const PCE_COHORTES = {
  processor: "pce_cohortes_niif9",
  icono: "table", color: "teal",
  eyebrow: "PÉRDIDA CREDITICIA ESPERADA · NIIF 9",
  titulo: "Pérdida Crediticia Esperada (NIIF 9)",
  subtitulo: "Matriz de provisiones por cohortes (ventana 24 meses t-2 → t), exposición anclada a EEFF, desdoblamiento del incumplimiento y ajuste prospectivo",
  principales: [
    { id: "RQ-001", titulo: "Cartera — Año 1 (t-2, el más antiguo)", icono: "doc", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Cartera — Año 2 (t-1)", icono: "doc", color: "teal", tipos: ".xlsx / .csv" },
    { id: "RQ-003", titulo: "Cartera — Año 3 (t, corte actual)", icono: "doc", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-004", titulo: "Anexo Inicial de la Provisión (Sumaria)", icono: "table", color: "gold", tipos: ".xlsx / .csv" },
    { id: "RQ-005", titulo: "Mayor de la Provisión — Año 1 (t-2)", icono: "list", color: "purple", tipos: ".xlsx / .csv" },
    { id: "RQ-006", titulo: "Mayor de la Provisión — Año 2 (t-1)", icono: "list", color: "purple", tipos: ".xlsx / .csv" },
    { id: "RQ-007", titulo: "Mayor de la Provisión — Año 3 (t)", icono: "list", color: "purple", tipos: ".xlsx / .csv" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Pérdida Crediticia Esperada", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "exposicion", titulo: "Exposición Anclada a EEFF", subtitulo: "Cartera por segmento anclada a los estados financieros.", icono: "shield", color: "teal", relacionados: ["RQ-003"], seccion: "sec-03_Exposicion" },
    { clave: "cohortes", titulo: "Cohortes (Ventana 24 meses)", subtitulo: "Tasa observada por segmento y banda (t-2 → t).", icono: "line", color: "gold", relacionados: ["RQ-001", "RQ-003"], seccion: "sec-04_Cohortes" },
    { clave: "matriz", titulo: "Matriz de Pérdida Esperada", subtitulo: "PCE por tramo con ajuste prospectivo.", icono: "table", color: "red", relacionados: ["RQ-003"], seccion: "sec-05_Matriz_PCE" },
    { clave: "por_banda", titulo: "Pérdida por Banda de Mora", subtitulo: "Exposición y pérdida esperada por banda.", icono: "list", color: "green", relacionados: ["RQ-003"], seccion: "sec-06_Por_banda" },
    { clave: "comparacion", titulo: "Comparación con la Política", subtitulo: "Recálculo frente a la provisión según política.", icono: "calc", color: "purple", relacionados: ["RQ-003"], seccion: "sec-07_Comparacion" },
    { clave: "movimiento", titulo: "Movimiento de la Provisión", subtitulo: "Reconciliación del saldo anterior al registrado.", icono: "refresh", color: "teal", relacionados: ["RQ-004", "RQ-005"], seccion: "sec-09_Movimiento" },
    { clave: "anexo_inicial", titulo: "Anexo Inicial de la Provisión", subtitulo: "Sumaria: saldo del año anterior y del actual.", icono: "book", color: "gold", relacionados: ["RQ-004"], seccion: "sec-14_Anexo_inicial" },
    { clave: "detalle", titulo: "Detalle de Cartera al Corte", subtitulo: "Mora, banda, días de crédito y saldo por factura.", icono: "list", color: "blue", relacionados: ["RQ-003"], seccion: "sec-12_Detalle" },
    { clave: "hallazgos", titulo: "Hallazgos (CCCEER)", subtitulo: "Hallazgos de auditoría con riesgo y recomendación.", icono: "warning", color: "red", relacionados: "todos", seccion: "sec-10_Hallazgos" },
  ],
};

// --- Pérdidas Incurridas (Sección 11 PYMES) ---
const PERDIDAS_INCURRIDAS_S11 = {
  processor: "perdidas_incurridas_s11",
  icono: "table", color: "gold",
  eyebrow: "DETERIORO DE CARTERA · SECCIÓN 11 PYMES",
  titulo: "Pérdidas Incurridas (Sección 11)",
  subtitulo: "Deterioro de cartera por pérdidas incurridas: evidencia histórica, matriz de deterioro, movimiento y fiscal",
  principales: [
    { id: "RQ-001", titulo: "Cartera por Factura al Cierre Corriente", icono: "doc", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-002", titulo: "Cartera por Factura del Cierre Anterior", icono: "book", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-004", titulo: "Provisión y Diferidos por Factura al Inicio", icono: "table", color: "gold", tipos: ".xlsx / .csv" },
    { id: "RQ-005", titulo: "Movimiento de la Provisión según el Mayor", icono: "list", color: "purple", tipos: ".xlsx / .csv" },
    { id: "RQ-006", titulo: "Cobros Posteriores al Cierre", icono: "bank", color: "teal", tipos: ".xlsx / .pdf" },
    { id: "RQ-007", titulo: "Política de Crédito y Cobranza", icono: "shield", color: "red", tipos: ".pdf / .docx" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Pérdidas Incurridas", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "evidencia_historica", titulo: "Evidencia Histórica", subtitulo: "Comportamiento de la cartera en tres ejercicios.", icono: "line", color: "teal", relacionados: ["RQ-001", "RQ-002", "RQ-003"], seccion: "sec-03_Evidencia_historica" },
    { clave: "matriz_deterioro", titulo: "Matriz de Deterioro", subtitulo: "Deterioro requerido por tramo de mora.", icono: "table", color: "gold", relacionados: ["RQ-001", "RQ-004"], seccion: "sec-04_Matriz_deterioro" },
    { clave: "por_cliente", titulo: "Deterioro por Cliente", subtitulo: "Análisis individualizado de clientes.", icono: "people", color: "green", relacionados: ["RQ-001"], seccion: "sec-05_Por_cliente" },
    { clave: "movimiento_provision", titulo: "Movimiento de la Provisión", subtitulo: "Conciliación de altas, usos y reversos.", icono: "refresh", color: "purple", relacionados: ["RQ-004", "RQ-005"], seccion: "sec-06_Movimiento_provision" },
    { clave: "mayor", titulo: "Provisión según el Mayor", subtitulo: "Cruce del movimiento contra el libro mayor.", icono: "book", color: "blue", relacionados: ["RQ-005"], seccion: "sec-07_Mayor" },
    { clave: "fiscal", titulo: "Fiscal", subtitulo: "Diferencia contable-fiscal del deterioro.", icono: "calc", color: "teal", relacionados: ["RQ-001"], seccion: "sec-08_Fiscal" },
    { clave: "impuesto_diferido", titulo: "Impuesto Diferido por Factura", subtitulo: "Activo/pasivo diferido factura a factura.", icono: "coins", color: "gold", relacionados: ["RQ-004"], seccion: "sec-09_Impuesto_diferido" },
    { clave: "asientos", titulo: "Asientos Propuestos", subtitulo: "Ajustes al deterioro registrado.", icono: "gears", color: "red", relacionados: ["RQ-001", "RQ-005"], seccion: "sec-10_Asientos" },
    { clave: "cobros_posteriores", titulo: "Cobros Posteriores al Cierre", subtitulo: "Evidencia de cobrabilidad tras el corte.", icono: "bank", color: "purple", relacionados: ["RQ-006"] },
  ],
};

export const CONFIG = {
  efectivo: EFECTIVO,
  planificacion: PLANIFICACION,
  cxc: CXC,
  proveedores: PROVEEDORES,
  inventarios: INVENTARIOS,
  ingresos: INGRESOS,
  ppe: PPE,
  propiedades: PROPIEDADES_INVERSION,
  intangibles: INTANGIBLES,
  biologicos: ACTIVOS_BIOLOGICOS,
  prestamos: PRESTAMOS,
  inversiones: INVERSIONES,
  patrimonio: PATRIMONIO,
  provisiones: PROVISIONES,
  nomina: NOMINA,
  impuesto: IMPUESTO,
  gastos: GASTOS,
  seguros: SEGUROS,
  arrendamientos: ARRENDAMIENTOS,
  pce_cohortes: PCE_COHORTES,
  pce: PCE_NIIF9,
  perdidas: PERDIDAS_INCURRIDAS_S11,
};

// Devuelve la config de la vista de 3 pasos para un processor, o null si ese
// procesador no usa esta vista (sigue con VistaTrabajo). Data-driven: recorre
// CONFIG, así que agregar una herramienta es solo agregar su entrada arriba.
export function configDeProcesador(processor) {
  return Object.values(CONFIG).find((c) => c.processor === processor) || null;
}
