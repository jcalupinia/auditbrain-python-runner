// Catálogo de categorías y herramientas del módulo AUD (External Audit).
// En M1, solo "Impuestos" tiene herramientas activas; el resto muestra
// "Próximamente" en la UI.

export const CATEGORIES = [
  { id: "PLANIFICACION", label: "Planificación", type: "etapa" },
  { id: "CAJA_BANCOS", label: "Caja y bancos", type: "ciclo" },
  { id: "INVERSIONES", label: "Inversiones", type: "ciclo" },
  { id: "CXC", label: "Cuentas por cobrar", type: "ciclo" },
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
  { id: "CONCLUSION", label: "Conclusión y dictamen", type: "etapa" },
];
