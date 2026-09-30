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
  // Tarjetas primarias en su orden. RQ-003 (Estado de Resultados del año anterior
  // al mismo corte) es OPCIONAL y solo aplica a la visita preliminar: con él la
  // comparación del ERI es exacta (ago-vs-ago); sin él, el ERI anterior se
  // prorratea (dic ÷ 12 × meses). Se muestra como tarjeta visible —antes caía en
  // «Documentos de soporte» y pasaba desapercibido—. El resto (RQ-009 y RQ-007)
  // queda en «Documentos de soporte».
  principales: [
    { id: "RQ-002", titulo: "Estados Financieros Año Actual", icono: "chart", tipos: ".xlsx" },
    { id: "RQ-001", titulo: "Estados Financieros Año Anterior", icono: "chart", tipos: ".xlsx" },
    { id: "RQ-003", titulo: "Estado de Resultados Año Anterior (mismo corte · visita preliminar)", icono: "line", tipos: ".xlsx / .csv" },
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


// === Etapas 2-5 · resto de herramientas del catálogo ===

const PPE = {
  processor: "ppe_propiedad_planta",
  icono: "building", color: "blue",
  eyebrow: "PROPIEDAD, PLANTA Y EQUIPO",
  titulo: "Propiedad, Planta y Equipo",
  subtitulo: "Auditoría de PPE: depreciación, componentes, revaluación, deterioro y costos por préstamos",
  principales: [
    { id: "RQ-001", titulo: "Auxiliar de Propiedad, Planta y Equipo", icono: "doc", color: "green", tipos: ".xlsx / .csv" },
    { id: "RQ-004", titulo: "Política de Vidas Útiles y Residuales", icono: "shield", color: "gold", tipos: ".pdf / .docx" },
    { id: "RQ-002", titulo: "Detalle de Adiciones del Año", icono: "coins", color: "blue", tipos: ".xlsx / .csv" },
    { id: "RQ-006", titulo: "Cálculo del Importe Recuperable", icono: "warning", color: "red", tipos: ".xlsx / .pdf" },
    { id: "RQ-005", titulo: "Informe del Perito de Revaluación", icono: "chart", color: "purple", tipos: "PDF" },
  ],
  ejecuciones: [
    { clave: "procedimiento", titulo: "Procedimiento de Propiedad, Planta y Equipo", subtitulo: "Papeles de trabajo y conclusiones.", icono: "doc", color: "blue", relacionados: "todos" },
    { clave: "sumaria", titulo: "Sumaria y Auxiliar de Activos", subtitulo: "Cédula sumaria y detalle por activo.", icono: "table", color: "green", relacionados: ["RQ-001"] },
    { clave: "depreciacion", titulo: "Recálculo de Depreciación y VNL", subtitulo: "Depreciación auditada y valor neto en libros.", icono: "calc", color: "purple", relacionados: ["RQ-001", "RQ-004"] },
    { clave: "vidas_utiles", titulo: "Vidas Útiles, Residual y Método", subtitulo: "Revisión de vidas útiles, valor residual y método.", icono: "clock", color: "gold", relacionados: ["RQ-004"] },
    { clave: "componentes", titulo: "Componentes", subtitulo: "Depreciación por componentes significativos.", icono: "box", color: "teal", relacionados: ["RQ-001"] },
    { clave: "adiciones", titulo: "Adiciones y Costos por Préstamos", subtitulo: "Altas del año y capitalización.", icono: "coins", color: "blue", relacionados: ["RQ-002"] },
    { clave: "prestamos", titulo: "Préstamos, Capitalización y Desmantelamiento", subtitulo: "Costos por préstamos capitalizados y provisiones de desmantelamiento.", icono: "bank", color: "purple", relacionados: ["RQ-003", "RQ-007", "RQ-008"] },
    { clave: "revaluacion", titulo: "Revaluación", subtitulo: "Modelo de revaluación y superávit.", icono: "chart", color: "gold", relacionados: ["RQ-005"] },
    { clave: "deterioro", titulo: "Deterioro", subtitulo: "Importe recuperable vs valor en libros.", icono: "warning", color: "red", relacionados: ["RQ-006"] },
    { clave: "bajas", titulo: "Bajas del Año", subtitulo: "Retiros y resultado en la baja.", icono: "refresh", color: "teal", relacionados: ["RQ-009"] },
    { clave: "movimiento", titulo: "Movimiento, Conciliación y Ajustes", subtitulo: "Roll-forward auxiliar-mayor y ajustes propuestos.", icono: "sliders", color: "blue", relacionados: ["RQ-001"] },
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
    { clave: "registro", titulo: "Registro y Titularidad de Inmuebles", subtitulo: "Existencia y derechos sobre los inmuebles.", icono: "building", color: "green", relacionados: ["RQ-001", "RQ-005"] },
    { clave: "clasificacion", titulo: "Clasificación", subtitulo: "Clasificación como propiedad de inversión.", icono: "list", color: "teal", relacionados: ["RQ-001", "RQ-006"] },
    { clave: "valor_razonable", titulo: "Valor Razonable", subtitulo: "Costo inicial y medición a valor razonable.", icono: "chart", color: "purple", relacionados: ["RQ-003"] },
    { clave: "modelo_costo", titulo: "Modelo del Costo", subtitulo: "Depreciación y deterioro bajo modelo del costo.", icono: "calc", color: "gold", relacionados: ["RQ-001"] },
    { clave: "medicion", titulo: "Medición Auditada por Inmueble", subtitulo: "Medición auditada y diferencias por inmueble.", icono: "table", color: "blue", relacionados: ["RQ-003"] },
    { clave: "transferencias", titulo: "Transferencias", subtitulo: "Cambios de uso y transferencias.", icono: "refresh", color: "gold", relacionados: ["RQ-006"] },
    { clave: "superavit", titulo: "Superávit de Revaluación", subtitulo: "Historial del superávit y cambios en patrimonio.", icono: "pie", color: "purple", relacionados: ["RQ-009"] },
    { clave: "alquileres", titulo: "Ingresos por Alquiler", subtitulo: "Ingresos por arrendamiento del ejercicio.", icono: "bank", color: "teal", relacionados: ["RQ-004"] },
    { clave: "bajas", titulo: "Bajas", subtitulo: "Retiros del ejercicio y resultado en la baja.", icono: "box", color: "red", relacionados: ["RQ-002"] },
    { clave: "conciliacion", titulo: "Sumaria y Conciliación", subtitulo: "Cédula sumaria y conciliación de saldos.", icono: "sliders", color: "green", relacionados: ["RQ-001"] },
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
    { clave: "auxiliar", titulo: "Auxiliar de Intangibles y Goodwill", subtitulo: "Detalle por partida y titularidad.", icono: "book", color: "green", relacionados: ["RQ-001", "RQ-005"] },
    { clave: "reconocimiento", titulo: "Reconocimiento e I+D", subtitulo: "Criterios de capitalización (NIC 38.57).", icono: "search", color: "teal", relacionados: ["RQ-002"] },
    { clave: "amortizacion", titulo: "Amortización", subtitulo: "Recálculo de amortización y vida finita/indefinida.", icono: "calc", color: "gold", relacionados: ["RQ-007", "RQ-001"] },
    { clave: "vida_util", titulo: "Vida Útil y Valor Residual", subtitulo: "Revisión de vida útil y residual al cierre.", icono: "clock", color: "purple", relacionados: ["RQ-006"] },
    { clave: "deterioro", titulo: "Deterioro e Importe Recuperable", subtitulo: "Valor en uso y VR menos costos de disposición.", icono: "warning", color: "red", relacionados: ["RQ-003"] },
    { clave: "goodwill", titulo: "Goodwill y Combinaciones de Negocios", subtitulo: "Asignación del precio de compra y prueba de goodwill.", icono: "bank", color: "purple", relacionados: ["RQ-004", "RQ-003"] },
    { clave: "reversion", titulo: "Reversión del Deterioro", subtitulo: "Reversiones admitidas y su límite.", icono: "refresh", color: "gold", relacionados: ["RQ-003"] },
    { clave: "ajuste", titulo: "Valor Neto y Ajuste Propuesto", subtitulo: "Valor neto auditado y ajustes propuestos.", icono: "sliders", color: "blue", relacionados: ["RQ-001"] },
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
    { clave: "clasificacion", titulo: "Clasificación y Datos", subtitulo: "Clasificación de activos biológicos y sus datos.", icono: "list", color: "green", relacionados: ["RQ-001"] },
    { clave: "existencia", titulo: "Existencia: Conteo vs Registros", subtitulo: "Conteo físico contra registros de campo.", icono: "search", color: "teal", relacionados: ["RQ-005", "RQ-001"] },
    { clave: "valoracion", titulo: "Valoración: VR menos Costos de Venta", subtitulo: "Valor razonable menos costos de venta.", icono: "coins", color: "gold", relacionados: ["RQ-003", "RQ-004"] },
    { clave: "transformacion", titulo: "Transformación Biológica y Cambio de VR", subtitulo: "Cambio de valor razonable del ejercicio.", icono: "refresh", color: "purple", relacionados: ["RQ-007", "RQ-005"] },
    { clave: "conciliacion", titulo: "Conciliación de Cambios (NIC 41.50)", subtitulo: "Conciliación del movimiento del período.", icono: "table", color: "blue", relacionados: ["RQ-007"] },
    { clave: "modelo_costo", titulo: "Modelo del Costo y Deterioro", subtitulo: "Medición al costo cuando el VR no es fiable.", icono: "warning", color: "red", relacionados: ["RQ-006"] },
    { clave: "cosecha", titulo: "Producto Agrícola en la Cosecha", subtitulo: "Producción cosechada en el punto de cosecha.", icono: "calendar", color: "gold", relacionados: ["RQ-002"] },
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
    { clave: "universo", titulo: "Universo de Préstamos", subtitulo: "Sumaria y detalle por operación de deuda.", icono: "table", color: "green", relacionados: ["RQ-001", "RQ-008"] },
    { clave: "tie_costo_amortizado", titulo: "TIE y Costo Amortizado", subtitulo: "Tasa efectiva, amortización y costo amortizado al corte.", icono: "calc", color: "purple", relacionados: ["RQ-003", "RQ-005"] },
    { clave: "comisiones", titulo: "Comisiones y Costos de Transacción", subtitulo: "Costos capitalizables al pasivo financiero.", icono: "coins", color: "gold", relacionados: ["RQ-005"] },
    { clave: "intereses", titulo: "Recálculo de Intereses", subtitulo: "Gasto financiero e intereses por pagar.", icono: "line", color: "teal", relacionados: ["RQ-008", "RQ-003"] },
    { clave: "confirmaciones", titulo: "Confirmaciones Bancarias", subtitulo: "Cotejo de respuestas de confirmación (NIA 505).", icono: "people", color: "blue", relacionados: ["RQ-004"] },
    { clave: "covenants", titulo: "Covenants y Dispensas", subtitulo: "DSCR, ratios de endeudamiento y cartas de dispensa.", icono: "shield", color: "red", relacionados: ["RQ-006", "RQ-007"] },
    { clave: "clasificacion", titulo: "Clasificación Corriente / No Corriente", subtitulo: "Presentación del pasivo por vencimiento.", icono: "list", color: "green", relacionados: ["RQ-001"] },
    { clave: "modificaciones", titulo: "Modificaciones y Prueba del 10 %", subtitulo: "Flujos de la adenda descontados a la TIE original (NIIF 9).", icono: "refresh", color: "gold", relacionados: ["RQ-002", "RQ-003"] },
    { clave: "conciliacion", titulo: "Conciliación y Ajustes", subtitulo: "Cuadre contra libros y ajustes propuestos.", icono: "gears", color: "blue", relacionados: ["RQ-008", "RQ-001"] },
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
    { clave: "inventario", titulo: "Inventario de Inversiones", subtitulo: "Sumaria y detalle por instrumento.", icono: "table", color: "teal", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "clasificacion", titulo: "Clasificación y Modelo de Negocio", subtitulo: "SPPI y modelo de negocio (NIIF 9).", icono: "sliders", color: "purple", relacionados: ["RQ-003", "RQ-004"] },
    { clave: "costo_amortizado", titulo: "Costo Amortizado y TIE", subtitulo: "Tasa efectiva y medición a costo amortizado.", icono: "calc", color: "green", relacionados: ["RQ-004", "RQ-001"] },
    { clave: "valor_razonable", titulo: "Valor Razonable y Jerarquía", subtitulo: "Medición a valor razonable y niveles NIIF 13.", icono: "chart", color: "gold", relacionados: ["RQ-005"] },
    { clave: "intereses_dividendos", titulo: "Intereses y Dividendos", subtitulo: "Rendimientos devengados y dividendos decretados.", icono: "coins", color: "blue", relacionados: ["RQ-006", "RQ-001"] },
    { clave: "deterioro", titulo: "Deterioro", subtitulo: "Pérdida crediticia esperada por instrumento.", icono: "warning", color: "red", relacionados: ["RQ-007"] },
    { clave: "reclasificacion", titulo: "Reclasificación", subtitulo: "Cambios de modelo de negocio y su efecto.", icono: "refresh", color: "purple", relacionados: ["RQ-003"] },
    { clave: "conciliacion", titulo: "Conciliación y Ajustes", subtitulo: "Cuadre contra libros y ajustes propuestos.", icono: "gears", color: "green", relacionados: ["RQ-001", "RQ-002"] },
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
    { clave: "movimiento", titulo: "Movimiento Patrimonial", subtitulo: "Sumaria y detalle por componente del patrimonio.", icono: "table", color: "gold", relacionados: ["RQ-001", "RQ-006"] },
    { clave: "transacciones", titulo: "Actas y Transacciones", subtitulo: "Cotejo de movimientos contra actas de junta.", icono: "book", color: "purple", relacionados: ["RQ-002", "RQ-003"] },
    { clave: "capital", titulo: "Capital y Aumentos", subtitulo: "Aportes e inscripción de aumentos de capital.", icono: "building", color: "green", relacionados: ["RQ-004"] },
    { clave: "reserva_legal", titulo: "Reserva Legal", subtitulo: "Apropiación y suficiencia de la reserva legal.", icono: "shield", color: "teal", relacionados: ["RQ-001"] },
    { clave: "dividendos", titulo: "Dividendos", subtitulo: "Decreto, pago y retención de dividendos.", icono: "coins", color: "gold", relacionados: ["RQ-002", "RQ-003"] },
    { clave: "clasificacion", titulo: "Clasificación Deuda / Patrimonio", subtitulo: "Instrumentos con opción de venta y preferentes (NIC 32).", icono: "sliders", color: "red", relacionados: ["RQ-005"] },
    { clave: "recompra", titulo: "Recompra de Acciones Propias", subtitulo: "Acciones propias en cartera y su presentación.", icono: "refresh", color: "purple", relacionados: ["RQ-002"] },
    { clave: "ajustes", titulo: "Patrimonio Auditado y Asientos", subtitulo: "Ajustes propuestos y conciliación final.", icono: "gears", color: "blue", relacionados: ["RQ-006", "RQ-001"] },
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
    { clave: "provisiones", titulo: "Provisiones y Contingencias", subtitulo: "Sumaria y detalle de provisiones del cliente.", icono: "table", color: "green", relacionados: ["RQ-001", "RQ-006"] },
    { clave: "obligacion_probabilidad", titulo: "Obligación Presente y Probabilidad", subtitulo: "Reconocimiento y probabilidad de salida (NIC 37).", icono: "search", color: "purple", relacionados: ["RQ-001", "RQ-007"] },
    { clave: "mejor_estimacion", titulo: "Mejor Estimación", subtitulo: "Cuantificación de la mejor estimación.", icono: "calc", color: "gold", relacionados: ["RQ-001"] },
    { clave: "valor_presente", titulo: "Valor Presente y Reversión del Descuento", subtitulo: "Descuento y actualización financiera del período.", icono: "coins", color: "teal", relacionados: ["RQ-006"] },
    { clave: "litigios", titulo: "Litigios y Cartas de Abogados", subtitulo: "Cotejo con respuestas de los abogados (NIA 501).", icono: "people", color: "blue", relacionados: ["RQ-003", "RQ-007"] },
    { clave: "garantias", titulo: "Garantías", subtitulo: "Provisión por garantías por línea de producto.", icono: "shield", color: "green", relacionados: ["RQ-002", "RQ-001"] },
    { clave: "onerosos", titulo: "Contratos Onerosos", subtitulo: "Provisión por contratos de carácter oneroso.", icono: "warning", color: "red", relacionados: ["RQ-004"] },
    { clave: "desmantelamiento", titulo: "Desmantelamiento", subtitulo: "Provisión por desmantelamiento y retiro.", icono: "box", color: "gold", relacionados: ["RQ-004"] },
    { clave: "reconocimiento_contingencias", titulo: "Reconocimiento y Contingencias a Revelar", subtitulo: "Provisión requerida vs libros y contingencias a revelar.", icono: "list", color: "purple", relacionados: ["RQ-001", "RQ-005"] },
    { clave: "ajustes", titulo: "Ajustes y Conciliación", subtitulo: "Ajustes propuestos y conciliación final.", icono: "gears", color: "blue", relacionados: ["RQ-006", "RQ-001"] },
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
    { clave: "recalculo_nomina", titulo: "Empleados y Recálculo de Nómina", subtitulo: "Recálculo de bruto y neto por empleado.", icono: "table", color: "purple", relacionados: ["RQ-001", "RQ-003"] },
    { clave: "iess", titulo: "Aportes IESS y Planillas", subtitulo: "Cotejo de aportes y planillas del IESS.", icono: "bank", color: "green", relacionados: ["RQ-004"] },
    { clave: "decimos", titulo: "Décimo Tercero y Décimo Cuarto", subtitulo: "Recálculo de décimos y su provisión.", icono: "coins", color: "gold", relacionados: ["RQ-001", "RQ-003"] },
    { clave: "vacaciones", titulo: "Vacaciones", subtitulo: "Provisión y pago de vacaciones.", icono: "calendar", color: "teal", relacionados: ["RQ-007", "RQ-001"] },
    { clave: "fondo_reserva", titulo: "Fondo de Reserva", subtitulo: "Recálculo del fondo de reserva.", icono: "box", color: "blue", relacionados: ["RQ-004", "RQ-001"] },
    { clave: "dbo_actuarial", titulo: "Jubilación Patronal y Desahucio: DBO", subtitulo: "Obligación por beneficios definidos.", icono: "calc", color: "red", relacionados: ["RQ-002", "RQ-005"] },
    { clave: "resultados_ori", titulo: "Costo Post-Empleo: Resultados y ORI", subtitulo: "Gasto en resultados y remediciones en ORI.", icono: "pie", color: "purple", relacionados: ["RQ-005", "RQ-002"] },
    { clave: "censo_actuarial", titulo: "Censo Actuarial y Desahucio Legal", subtitulo: "Validación del censo enviado al actuario.", icono: "people", color: "gold", relacionados: ["RQ-005"] },
    { clave: "conciliacion_gl", titulo: "Conciliación Nómina–Mayor", subtitulo: "Cuadre de nómina contra el mayor contable.", icono: "refresh", color: "green", relacionados: ["RQ-006", "RQ-001"] },
    { clave: "ajustes", titulo: "Ajustes Propuestos", subtitulo: "Asientos de ajuste sobre nómina y pasivos.", icono: "gears", color: "blue", relacionados: ["RQ-006"] },
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
    { clave: "conciliacion", titulo: "Conciliación Tributaria", subtitulo: "Renglones del F-101 y base imponible.", icono: "table", color: "blue", relacionados: ["RQ-001", "RQ-004"] },
    { clave: "impuesto_corriente", titulo: "Impuesto Corriente", subtitulo: "Cálculo del impuesto causado y anticipos.", icono: "calc", color: "green", relacionados: ["RQ-001", "RQ-005"] },
    { clave: "perdidas", titulo: "Pérdidas Tributarias", subtitulo: "Amortización por año de origen.", icono: "line", color: "red", relacionados: ["RQ-003", "RQ-004"] },
    { clave: "diferencias_temp", titulo: "Diferencias Temporarias y Diferido", subtitulo: "Activos y pasivos por impuesto diferido.", icono: "sliders", color: "purple", relacionados: ["RQ-002"] },
    { clave: "recuperabilidad", titulo: "Recuperabilidad del Activo Diferido", subtitulo: "Análisis de ganancias fiscales futuras.", icono: "search", color: "gold", relacionados: ["RQ-006"] },
    { clave: "movimiento", titulo: "Movimiento: Resultados y ORI", subtitulo: "Efecto en resultados y en ORI.", icono: "chart", color: "teal", relacionados: ["RQ-007", "RQ-002"] },
    { clave: "compensacion", titulo: "Compensación y Presentación", subtitulo: "Neteo y presentación en el estado de situación.", icono: "box", color: "blue", relacionados: ["RQ-007"] },
    { clave: "tasa_efectiva", titulo: "Tasa Efectiva (NIC 12.81 c)", subtitulo: "Conciliación de la tasa efectiva.", icono: "pie", color: "purple", relacionados: ["RQ-001", "RQ-007"] },
    { clave: "partic_exentos", titulo: "Participación Atribuible a Exentos", subtitulo: "Participación de trabajadores sobre exentos.", icono: "coins", color: "gold", relacionados: ["RQ-008", "RQ-001"] },
    { clave: "asientos", titulo: "Asientos Propuestos", subtitulo: "Ajustes de impuesto corriente y diferido.", icono: "gears", color: "green", relacionados: ["RQ-007"] },
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
    { clave: "analisis_global", titulo: "Análisis Global por Cuenta (NIA 520)", subtitulo: "Variaciones año actual, anterior y presupuesto.", icono: "chart", color: "teal", relacionados: ["RQ-001", "RQ-003"] },
    { clave: "transacciones", titulo: "Transacciones de la Muestra", subtitulo: "Selección y marcas de la muestra de gasto.", icono: "list", color: "blue", relacionados: ["RQ-002"] },
    { clave: "vouching", titulo: "Verificación del Soporte Documental", subtitulo: "Vouching de facturas, contratos y pagos.", icono: "search", color: "gold", relacionados: ["RQ-004", "RQ-002"] },
    { clave: "corte", titulo: "Corte de Gastos", subtitulo: "Prueba de corte sobre el período del servicio.", icono: "calendar", color: "purple", relacionados: ["RQ-005", "RQ-002"] },
    { clave: "devengo", titulo: "Devengo y Gastos Anticipados", subtitulo: "Reconocimiento en el período correcto.", icono: "clock", color: "green", relacionados: ["RQ-002", "RQ-003"] },
    { clave: "partes_relacionadas", titulo: "Partes Relacionadas", subtitulo: "Identificación de transacciones con partes relacionadas.", icono: "people", color: "red", relacionados: ["RQ-006", "RQ-008"] },
    { clave: "rp_integridad", titulo: "Integridad de la Revelación de Partes Relacionadas", subtitulo: "Cobertura del maestro y la revelación.", icono: "shield", color: "gold", relacionados: ["RQ-006", "RQ-008"] },
    { clave: "inusuales", titulo: "Partidas Inusuales", subtitulo: "Detección de partidas atípicas de gasto.", icono: "warning", color: "red", relacionados: ["RQ-002"] },
    { clave: "tributario", titulo: "Referencia Tributaria (Ecuador)", subtitulo: "Deducibilidad y referencia fiscal.", icono: "calc", color: "blue", relacionados: ["RQ-003"] },
    { clave: "asientos", titulo: "Asientos y Ajustes", subtitulo: "Ajustes propuestos y conciliación.", icono: "gears", color: "green", relacionados: ["RQ-003"] },
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
    { clave: "vigencia", titulo: "Vigencia de Pólizas al Corte", subtitulo: "Pólizas vigentes y vencidas a la fecha de corte.", icono: "calendar", color: "purple", relacionados: ["RQ-002", "RQ-003"] },
    { clave: "cobertura_activo", titulo: "Universo y Cobertura por Activo", subtitulo: "Cotejo del maestro de activos contra pólizas.", icono: "table", color: "gold", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "cobertura_poliza", titulo: "Cobertura por Póliza (Infraseguro)", subtitulo: "Suma asegurada frente al valor de referencia.", icono: "search", color: "teal", relacionados: ["RQ-002", "RQ-004"] },
    { clave: "deducibles_exposicion", titulo: "Deducibles y Exposición Máxima", subtitulo: "Deducibles y exposición neta por póliza.", icono: "sliders", color: "blue", relacionados: ["RQ-003"] },
    { clave: "sin_cobertura", titulo: "Activos Sin Cobertura", subtitulo: "Activos asegurables sin póliza vigente.", icono: "warning", color: "red", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "prima_anticipada", titulo: "Prima Pagada por Anticipado", subtitulo: "Devengo del seguro prepagado.", icono: "coins", color: "green", relacionados: ["RQ-006"] },
    { clave: "siniestros", titulo: "Siniestros Pendientes y Revelación", subtitulo: "Reclamos en curso y su revelación.", icono: "shield", color: "purple", relacionados: ["RQ-005"] },
    { clave: "ajustes", titulo: "Ajustes Propuestos y Conciliación", subtitulo: "Asientos de ajuste y cuadre con el mayor.", icono: "gears", color: "gold", relacionados: ["RQ-006"] },
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
    { clave: "contratos", titulo: "Universo de Contratos", subtitulo: "Inventario y cobertura de contratos al corte.", icono: "building", color: "teal", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "clasificacion", titulo: "Identificación, Clasificación y Exenciones", subtitulo: "Alcance, corto plazo y bajo valor.", icono: "list", color: "gold", relacionados: ["RQ-001", "RQ-002"] },
    { clave: "plazo", titulo: "Plazo y Opciones", subtitulo: "Plazo razonablemente cierto y opciones.", icono: "calendar", color: "purple", relacionados: ["RQ-002", "RQ-007"] },
    { clave: "medicion_inicial", titulo: "Medición Inicial", subtitulo: "Pasivo por arrendamiento y activo por derecho de uso.", icono: "calc", color: "green", relacionados: ["RQ-003", "RQ-004"] },
    { clave: "amortizacion", titulo: "Tabla de Amortización", subtitulo: "Intereses y amortización del pasivo.", icono: "table", color: "blue", relacionados: ["RQ-003", "RQ-004"] },
    { clave: "pasivo_corte", titulo: "Pasivo al Corte", subtitulo: "Porción corriente y no corriente.", icono: "coins", color: "teal", relacionados: ["RQ-004"] },
    { clave: "derecho_uso", titulo: "Derecho de Uso", subtitulo: "Depreciación y deterioro del activo.", icono: "warning", color: "gold", relacionados: ["RQ-004", "RQ-005"] },
    { clave: "gasto_lineal", titulo: "Gasto Lineal", subtitulo: "Contratos exentos y operativos.", icono: "line", color: "purple", relacionados: ["RQ-001", "RQ-007"] },
    { clave: "venta_arr_posterior", titulo: "Venta con Arrendamiento Posterior", subtitulo: "Medición inicial y posterior del sale & leaseback.", icono: "refresh", color: "red", relacionados: ["RQ-006", "RQ-008"] },
    { clave: "conciliacion", titulo: "Conciliación y Ajuste", subtitulo: "Cruce con la contabilidad y asientos.", icono: "gears", color: "blue", relacionados: ["RQ-004"] },
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
    { clave: "tasas_historicas", titulo: "Tasas Históricas", subtitulo: "Tasas de pérdida por tramo con castigos.", icono: "line", color: "teal", relacionados: ["RQ-002", "RQ-003"] },
    { clave: "matriz_provisiones", titulo: "Matriz de Provisiones", subtitulo: "PCE por tramo con ajuste prospectivo.", icono: "table", color: "red", relacionados: ["RQ-001", "RQ-004"] },
    { clave: "revelacion_niif7", titulo: "Revelación NIIF 7 (35M/35N)", subtitulo: "Exposición al riesgo de crédito.", icono: "shield", color: "gold", relacionados: ["RQ-001"] },
    { clave: "movimiento", titulo: "Movimiento de la Provisión (NIIF 7 35H)", subtitulo: "Conciliación del saldo de la provisión.", icono: "refresh", color: "purple", relacionados: ["RQ-002", "RQ-003"] },
    { clave: "fiscal", titulo: "Fiscal e Impuesto Diferido", subtitulo: "Diferencia contable-fiscal y diferido.", icono: "calc", color: "blue", relacionados: ["RQ-001"] },
    { clave: "asientos", titulo: "Asientos Propuestos", subtitulo: "Ajustes al deterioro registrado.", icono: "gears", color: "teal", relacionados: ["RQ-001"] },
    { clave: "detalle", titulo: "Detalle por Factura", subtitulo: "PCE calculada factura a factura.", icono: "list", color: "green", relacionados: ["RQ-001"] },
    { clave: "castigos", titulo: "Castigos del Ejercicio", subtitulo: "Bajas de cartera del período.", icono: "warning", color: "red", relacionados: ["RQ-003"] },
    { clave: "cobros_posteriores", titulo: "Cobros Posteriores al Cierre", subtitulo: "Evidencia de cobrabilidad tras el corte.", icono: "bank", color: "purple", relacionados: ["RQ-006"] },
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
    { clave: "evidencia_historica", titulo: "Evidencia Histórica", subtitulo: "Comportamiento de la cartera en tres ejercicios.", icono: "line", color: "teal", relacionados: ["RQ-001", "RQ-002", "RQ-003"] },
    { clave: "matriz_deterioro", titulo: "Matriz de Deterioro", subtitulo: "Deterioro requerido por tramo de mora.", icono: "table", color: "gold", relacionados: ["RQ-001", "RQ-004"] },
    { clave: "por_cliente", titulo: "Deterioro por Cliente", subtitulo: "Análisis individualizado de clientes.", icono: "people", color: "green", relacionados: ["RQ-001"] },
    { clave: "movimiento_provision", titulo: "Movimiento de la Provisión", subtitulo: "Conciliación de altas, usos y reversos.", icono: "refresh", color: "purple", relacionados: ["RQ-004", "RQ-005"] },
    { clave: "mayor", titulo: "Provisión según el Mayor", subtitulo: "Cruce del movimiento contra el libro mayor.", icono: "book", color: "blue", relacionados: ["RQ-005"] },
    { clave: "fiscal", titulo: "Fiscal", subtitulo: "Diferencia contable-fiscal del deterioro.", icono: "calc", color: "teal", relacionados: ["RQ-001"] },
    { clave: "impuesto_diferido", titulo: "Impuesto Diferido por Factura", subtitulo: "Activo/pasivo diferido factura a factura.", icono: "coins", color: "gold", relacionados: ["RQ-004"] },
    { clave: "asientos", titulo: "Asientos Propuestos", subtitulo: "Ajustes al deterioro registrado.", icono: "gears", color: "red", relacionados: ["RQ-001", "RQ-005"] },
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
  pce: PCE_NIIF9,
  perdidas: PERDIDAS_INCURRIDAS_S11,
};

// Devuelve la config de la vista de 3 pasos para un processor, o null si ese
// procesador no usa esta vista (sigue con VistaTrabajo). Data-driven: recorre
// CONFIG, así que agregar una herramienta es solo agregar su entrada arriba.
export function configDeProcesador(processor) {
  return Object.values(CONFIG).find((c) => c.processor === processor) || null;
}
