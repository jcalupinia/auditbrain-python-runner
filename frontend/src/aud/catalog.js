// Catálogo de categorías y herramientas del módulo AUD (External Audit).
// En M1, solo "Impuestos" tiene herramientas activas; el resto muestra
// "Próximamente" en la UI.

export const CATEGORIES = [
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
      },
    ],
  },
  { id: "PLANIFICACION", label: "Planificación", type: "etapa" },
  { id: "CAJA_BANCOS", label: "Caja y bancos", type: "ciclo" },
  { id: "INVERSIONES", label: "Inversiones", type: "ciclo" },
  {
    id: "CXC",
    label: "Cuentas por cobrar",
    type: "ciclo",
    tools: [
      {
        id: "AUD.CXC.PCE",
        label: "Matriz de pérdidas crediticias esperadas · NIIF 9",
        description:
          "Sube los tres análisis de antigüedad de cartera (t-2, t-1 y el corte actual). Deriva las tasas del comportamiento observado, ancla la exposición a los estados financieros, separa los saldos de evaluación individual y entrega el papel de trabajo en Excel con fórmulas auditables. El movimiento de la provisión se declara en la pantalla, con su referencia: sin él, el método de permanencia queda sin sustento y se reporta como pendiente.",
      },
    ],
  },
  { id: "INVENTARIOS", label: "Inventarios", type: "ciclo" },
  { id: "ACTIVOS_FIJOS", label: "Activos fijos", type: "ciclo" },
  {
    id: "INTANGIBLES",
    label: "Activos intangibles e impuestos diferidos",
    type: "ciclo",
  },
  { id: "PROVEEDORES", label: "Proveedores y cuentas por pagar", type: "ciclo" },
  {
    id: "PRESTAMOS",
    label: "Préstamos y obligaciones financieras",
    type: "ciclo",
  },
  { id: "PATRIMONIO", label: "Patrimonio", type: "ciclo" },
  { id: "INGRESOS", label: "Ingresos", type: "resultados" },
  { id: "COSTOS_GASTOS", label: "Costos y gastos", type: "resultados" },
  { id: "NOMINA", label: "Nómina", type: "resultados" },
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
      },
    ],
  },
];
