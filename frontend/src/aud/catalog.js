// Catálogo de categorías y herramientas del módulo AUD (External Audit).
// En M1, solo "Impuestos" tiene herramientas activas; el resto muestra
// "Próximamente" en la UI.

export const CATEGORIES = [
  {
    id: "INGESTA",
    label: "Motor de ingesta",
    type: "herramienta",
    tools: [
      {
        id: "AUD.INGESTA.MOTOR",
        label: "Motor de ingesta y normalización · capa transversal",
        description:
          "Ingiere, normaliza y valida un documento una sola vez (F-101/103/104, ATS, balances, mayores, XML/PDF/Excel) y entrega un dataset con trazabilidad al origen, método de extracción y confianza por campo. Determinístico primero: la IA no se dispara al ingerir.",
        pruebas: [
          "Clasificación determinista del documento",
          "Extracción con trazabilidad al origen (archivo·página·fila·celda)",
          "Normalización de montos, fechas y tipos (regional . y ,)",
          "Nivel de confianza por campo y cola de revisión",
          "Validación de calidad y sello SHA-256 reproducible",
        ],
      },
    ],
  },
  {
    id: "MOTOR_BALANCES",
    label: "Motor de balances",
    type: "herramienta",
    tools: [
      {
        id: "AUD.MOTOR_BALANCES",
        label: "Motor de balances · homologación SRI-Super",
        description:
          "Sube balances y resultados (multiarchivo), homologa contra el plan Super Cías/SRI, marca las cuentas huérfanas y valida el cuadre por período. Sin cuadres forzados.",
        pruebas: [
          "Consolidación de varios archivos y períodos",
          "Homologación contra el plan Super Cías/SRI",
          "Cuentas huérfanas",
          "Cuadre activo = pasivo + patrimonio por período",
          "Estados en el formato de la Superintendencia",
        ],
      },
    ],
  },
  {
    id: "MOTOR_ANALITICO",
    label: "Motor de auditoría analítica",
    type: "herramienta",
    tools: [
      {
        id: "AUD.MOTOR_ANALITICO",
        label: "Motor de auditoría analítica · 38 pruebas forenses",
        description:
          "Corre las 38 pruebas deterministas (NIA 240/315/330/500/530) sobre el mayor, comprobantes, ventas, proveedores y nómina. Datos anonimizados hasta SP4; los datos van directo al servidor de la firma.",
        pruebas: [
          "Asientos inusuales del mayor",
          "Ventas e ingresos",
          "Compras y conciliación con el SRI",
          "Gastos: duplicados, fraccionamiento y Ley de Benford",
          "Proveedores y partes relacionadas",
        ],
      },
    ],
  },
  {
    id: "CONFIRMACIONES",
    label: "Confirmaciones de saldos",
    type: "herramienta",
    tools: [
      {
        id: "AUD.CONFIRMACIONES.SALDOS",
        label: "Motor de confirmaciones · circularización",
        description:
          "Sube la muestra y genera un modelo de carta por rubro (bancos, clientes, proveedores, relacionados, seguros, abogados, terceros, inversiones), en el idioma que elijas y para AuditConsulting o Partner. Cartas en Word, control de confirmaciones en Excel y envío por correo. Sin envío automático.",
        pruebas: [
          "Muestra a circularizar",
          "Cartas por rubro",
          "Manifiesto de envío",
          "Control de confirmaciones",
          "Cobertura por rubro frente al mayor",
        ],
      },
    ],
  },
  { id: "PLANIFICACION", label: "Planificación", type: "etapa" },
  { id: "CAJA_BANCOS", label: "Caja y bancos", type: "ciclo" },
  { id: "INVERSIONES", label: "Inversiones", type: "ciclo" },
  { id: "CXC", label: "Cuentas por cobrar", type: "ciclo" },
  { id: "INVENTARIOS", label: "Inventarios", type: "ciclo", tools: [{ id: "AUD.INVENTARIOS.VNR", label: "Valor neto de realización", description: "NIIF completas o PYMES · evidencia, cálculo, ajustes, reversos y diferidos · Excel auditable y HTML.", pruebas: ["Inventario valorado", "Precios de venta", "Costos necesarios para vender", "Cálculo del VNR", "Conciliación con el mayor", "Ajustes y reversiones", "Impuesto diferido"] }] },
  { id: "ACTIVOS_FIJOS", label: "Propiedad, planta y equipo", type: "ciclo" },
  { id: "ARRENDAMIENTOS", label: "Arrendamientos", type: "ciclo" },
  { id: "PROPIEDADES_INVERSION", label: "Propiedades de inversión", type: "ciclo" },
  {
    id: "INTANGIBLES",
    label: "Activos intangibles y goodwill",
    type: "ciclo",
  },
  { id: "BIOLOGICOS", label: "Activos biológicos y agricultura", type: "ciclo" },
  { id: "SEGUROS", label: "Cobertura de seguros de activos", type: "ciclo" },
  { id: "PROVEEDORES", label: "Proveedores y cuentas por pagar", type: "ciclo" },
  {
    id: "PRESTAMOS",
    label: "Préstamos y obligaciones financieras",
    type: "ciclo",
  },
  { id: "PROVISIONES", label: "Provisiones y contingencias", type: "ciclo" },
  { id: "PATRIMONIO", label: "Patrimonio", type: "ciclo" },
  { id: "INGRESOS", label: "Ingresos", type: "resultados" },
  { id: "COSTOS_GASTOS", label: "Costos y gastos", type: "resultados" },
  { id: "NOMINA", label: "Beneficios sociales y nómina", type: "resultados" },
  {
    id: "IMPUESTOS",
    label: "Impuestos",
    type: "cumplimiento",
    tools: [
      {
        id: "AUD.IMPUESTOS.OBLIGACIONES_FISCALES",
        label: "Auditoría de Obligaciones Fiscales",
        description:
          "Genera el papel de trabajo DM Obligaciones Fiscales a partir de F-103, F-104, ATS y mayores. Cédulas DM6 IVA y DM7 Retenciones pobladas automáticamente.",
        pruebas: [
          "Revisión de saldos (DM3)",
          "Compras (DM4)",
          "Ventas (DM5)",
          "IVA (DM6)",
          "Retenciones por pagar (DM7)",
          "ATS (DM8)",
        ],
      },
    ],
  },
  {
    id: "CONCLUSION",
    label: "Conclusión y dictamen",
    type: "etapa",
    tools: [
      {
        id: "AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO",
        label: "Informe de Cumplimiento Tributario",
        description:
          "Genera el informe de opinión (AuditConsulting / Partner) a partir del Informe de Auditoría Externa y el F-101. Descarga el Word listo para firmar.",
        pruebas: [
          "Lectura del informe de auditoría externa",
          "Lectura de la declaración del impuesto a la renta (F-101)",
          "Informe de opinión en Word para firmar",
        ],
      },
    ],
  },
];
