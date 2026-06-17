// Catálogo de categorías y herramientas del módulo FIN (CFO Intelligence).
// Espejo del patrón de tax/catalog.js: categoría -> herramientas.

export const FIN_CATEGORIES = [
  {
    id: "ANALISIS_FINANCIERO",
    label: "Análisis Financiero Empresarial",
    type: "estrategia",
    tools: [
      {
        id: "FIN.DASHBOARD.EJECUTIVO",
        label: "Análisis Financiero Empresarial",
        description:
          "Centro de trabajo del gerente financiero. Fase 1 · Análisis de estados financieros: elige la fuente de información (Formulario 101, balances internos o auditados), define el nivel de detalle (resumido/detallado) y genera un dashboard ejecutivo interactivo con resumen, estados, variaciones, principales gastos, gastos atípicos, activos fijos, inversiones y proyección 3 estados. Exporta a HTML autocontenido, Excel e informe gerencial.",
      },
    ],
  },
  { id: "PRESUPUESTO", label: "Presupuesto y forecast", type: "estrategia" },
  { id: "TESORERIA", label: "Tesorería y flujo de caja", type: "cumplimiento" },
  { id: "COSTOS", label: "Análisis de costos", type: "cumplimiento" },
  { id: "VALORACION", label: "Valoración y M&A", type: "estrategia" },
];
