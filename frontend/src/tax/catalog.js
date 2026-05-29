// Catálogo de categorías y herramientas del módulo TAX (Tax Structuring).
// Espejo del patrón de aud/catalog.js: categoría -> herramientas.

export const TAX_CATEGORIES = [
  {
    id: "PLANIFICACION_TRIBUTARIA",
    label: "Planificación Tributaria",
    type: "estrategia",
    tools: [
      {
        id: "TAX.PLANIFICACION.UTILIDADES_RETENIDAS",
        label: "Planificación Impuesto Utilidades Retenidas",
        description:
          "Pago a cuenta sobre utilidades no distribuidas (Ecuador). Sube el Formulario 101 o un balance resumido y extrae los estados financieros; calcula base, tarifa, crédito y proyecta 2026–2028 con informe gerencial.",
      },
    ],
  },
  { id: "PRECIOS_TRANSFERENCIA", label: "Precios de transferencia", type: "cumplimiento" },
  { id: "IVA_RETENCIONES", label: "IVA y retenciones", type: "cumplimiento" },
  { id: "DIFERIDOS", label: "Impuestos diferidos", type: "cumplimiento" },
  { id: "REORGANIZACIONES", label: "Reorganizaciones societarias", type: "estrategia" },
];
