/* AuditBrain Command Center — datos mock.
 * Fuente: AuditBrain Informe Ejecutivo v1.7 (Mayo 2026).
 * NO se inventan cifras: todo proviene del documento. Regla #1.
 * Esta capa será reemplazable por /api/v1/* en una fase posterior. */

export const META = {
  product: "AuditBrain Executive Advisory",
  tagline: "No es una firma con IA. Es una firma de IA.",
  version: "v1.7",
  phase: "Fase 2.5 — Operativización",
  date: "Mayo 2026",
  classification: "CONFIDENCIAL",
  org: "Audit Consulting Group · Big Four + Inteligencia Artificial",
};

/* 11 capas + ROUTER + GOV. Estado, skills y códigos del Informe §2 / §3.1 */
export const LAYERS = [
  { code: "ROUTER", num: "0", name: "Master Router", short: "Puerta única de entrada · despacho por target",
    skills: { done: 0, total: 10, ids: "131–140" }, status: "operativo", agent: "thinking",
    desc: "Enrutamiento de toda solicitud externa. Flow 21: Router → AUT.",
    deliverable: "Dispatch table v1.7", spark: [4, 6, 5, 8, 7, 9, 8] },
  { code: "AUT", num: "1", name: "Automation Core", short: "Capa de transporte universal",
    skills: { done: 0, total: 20, ids: "111–130" }, status: "operativo", agent: "producing",
    desc: "Flow 20: toda invocación intermodular pasa por AUT. No modifica contenido (Regla #4).",
    deliverable: "Orquestación n8n · 15 templates", spark: [6, 7, 7, 9, 8, 10, 9] },
  { code: "ADV", num: "2", name: "Executive Advisory", short: "Capa de convergencia",
    skills: { done: 19, total: 19, ids: "001–019" }, status: "operativo", agent: "producing",
    desc: "Diagnóstico estratégico, matriz de riesgos, plan 90 días. Convergencia de hallazgos.",
    deliverable: "Board Pack · diagnóstico GRUPO_002", spark: [7, 8, 9, 8, 10, 9, 11] },
  { code: "AUD", num: "3", name: "External Audit", short: "Auditoría externa · NIA",
    skills: { done: 5, total: 5, ids: "006–010" }, status: "operativo", agent: "awaiting",
    desc: "Hallazgos CCCEER, Benford, NIA 570 (empresa en funcionamiento).",
    deliverable: "Informe auditoría · NIA 570 GRUPO_002", spark: [5, 6, 5, 7, 9, 8, 10] },
  { code: "TAX", num: "4", name: "Tax Structuring", short: "Estructuración · TP · CDI · BEPS",
    skills: { done: 5, total: 20, ids: "026–030 / 066–080" }, status: "operativo", agent: "thinking",
    desc: "Estructuración tributaria, precios de transferencia, sustancia económica.",
    deliverable: "Memo TAX preliminar (rev. humana)", spark: [4, 5, 7, 6, 8, 9, 8] },
  { code: "LEG", num: "5", name: "Legal Intelligence", short: "Contratos · litigios · compliance",
    skills: { done: 6, total: 21, ids: "020–025 / 081–095" }, status: "operativo", agent: "idle",
    desc: "Cláusulas críticas, obligaciones, contingencias, gobierno corporativo.",
    deliverable: "Resumen legal ejecutivo", spark: [3, 4, 4, 6, 5, 7, 6] },
  { code: "FIN", num: "6", name: "CFO Intelligence", short: "Covenants · dividendos · forecast",
    skills: { done: 4, total: 19, ids: "012–015 / 096–110" }, status: "operativo", agent: "producing",
    desc: "Flow 11 TAX↔FIN. Monthly CFO Report, covenants, decisión de dividendos.",
    deliverable: "Monthly CFO Report", spark: [6, 7, 6, 8, 9, 10, 11] },
  { code: "CYB", num: "7", name: "Cybersecurity & IT Audit", short: "ITGC · BCP/DRP · ISO 27001",
    skills: { done: 15, total: 15, ids: "051–065" }, status: "operativo", agent: "awaiting",
    desc: "Auditoría ITGC, madurez NIST, plan de remediación. 15/15 skills ✅.",
    deliverable: "Auditoría ITGC · gap BCP/DRP CO", spark: [8, 9, 9, 11, 10, 12, 12] },
  { code: "DATA", num: "8", name: "Data & BI Intelligence", short: "ETL · anomalías · KPIs",
    skills: { done: 10, total: 10, ids: "036–045" }, status: "parcial", agent: "thinking",
    desc: "Detección de anomalías, outliers, transacciones inusuales. Capa parcial.",
    deliverable: "Alertas de anomalías", spark: [5, 6, 8, 7, 9, 8, 9] },
  { code: "MKT", num: "10", name: "Marketing Intelligence", short: "Capa autónoma · posicionamiento",
    skills: { done: null, total: null, ids: "—" }, status: "operativo", agent: "idle",
    desc: "Posicionamiento y marca corporativa. Capa autónoma sin skills.",
    deliverable: "Campaña de posicionamiento", spark: [3, 3, 4, 3, 5, 4, 5] },
  { code: "CRE", num: "11", name: "Creative Studio", short: "Capa autónoma · slides premium",
    skills: { done: null, total: null, ids: "—" }, status: "operativo", agent: "producing",
    desc: "Slides ejecutivos premium con narrativa integrada. Capa autónoma.",
    deliverable: "Presentación boardroom", spark: [4, 5, 5, 7, 6, 8, 7] },
];

export const GOV_LAYER = {
  code: "GOV",
  name: "Governance Layer",
  short: "23 reglas inviolables · 6 pilares · 5 niveles",
  skills: { done: 8, total: 8, ids: "032–050" },
  status: "operativo",
  rulesActive: 23,
  pillars: 6,
  escalationLevels: 5,
  currentEscalation: "N2",
  highRiskSkills: 75,
  foundational:
    "Ningún output de AuditBrain sale del sistema sin aprobación del Socio responsable del módulo.",
};

/* Reglas inviolables para el sistema — Informe §9.4 */
export const GOV_RULES = [
  { n: 1, text: "No inventar datos, normativas, hallazgos ni referencias no confirmadas.", on: true },
  { n: 2, text: "Separar siempre hechos / análisis / riesgos / recomendaciones.", on: true },
  { n: 3, text: "Todo output de riesgo ALTO requiere flag de revisión humana obligatoria.", on: true },
  { n: 4, text: "AUT no modifica el contenido profesional de otros módulos — solo transporta.", on: true },
  { n: 5, text: "Toda acción del sistema debe quedar registrada en el Audit Trail.", on: true },
  { n: 6, text: "El Governance Layer es inviolable — ninguna regla puede saltarse por eficiencia.", on: true },
  { n: 7, text: "Clasificar riesgos solo como Bajo / Medio / Alto.", on: true },
  { n: 8, text: "Lenguaje ejecutivo, profesional y consultivo. Estilo Big Four + IA.", on: true },
];

/* Cola de aprobaciones — outputs de Alto Riesgo esperando al Socio.
 * Ilustrativo (UI); refleja hallazgos reales de GRUPO_002 §7.2. */
export const APPROVAL_QUEUE = [
  { id: "AP-0042", title: "Memo TAX — sustancia económica holding ETVE", layer: "TAX", risk: "Alto", sla: "4 h", owner: "Socio TAX" },
  { id: "AP-0043", title: "Informe AUD — NIA 570 empresa en funcionamiento", layer: "AUD", risk: "Alto", sla: "6 h", owner: "Socio AUD" },
  { id: "AP-0044", title: "Gap BCP/DRP inexistente — Operadora CO", layer: "CYB", risk: "Alto", sla: "8 h", owner: "Socio CYB" },
  { id: "AP-0045", title: "Board Pack integral GRUPO_002 (24 slides + anexos)", layer: "ADV", risk: "Alto", sla: "12 h", owner: "Socio ADV" },
];

/* KPIs objetivo del proyecto — Informe §6.1 */
export const KPIS = [
  { label: "Workflow integrado (W005)", value: "23 d", target: "12 d", unit: "días", pct: 0.52, tone: "med" },
  { label: "Skills operativas en Claude", value: "62", target: "140", unit: "skills", pct: 0.44, tone: "med" },
  { label: "Proyectos Claude creados", value: "10", target: "10", unit: "/10", pct: 1, tone: "low" },
  { label: "Tests backend passing", value: "446", target: "446", unit: "0 failed", pct: 1, tone: "low" },
  { label: "Flujos intermodulares", value: "21", target: "21", unit: "documentados", pct: 1, tone: "low" },
  { label: "Workflows n8n en producción", value: "0", target: "15", unit: "templates", pct: 0, tone: "high" },
  { label: "Conectores ERP productivos", value: "0", target: "3+2", unit: "ERP+banco", pct: 0, tone: "high" },
  { label: "Clientes operando", value: "0", target: "3 piloto", unit: "clientes", pct: 0, tone: "high" },
];

/* Semáforos de estado — Informe §10 */
export const STATUS_BOARD = [
  { k: "Proyectos Claude activos", v: "10 de 10", s: "low" },
  { k: "Skills físicas creadas", v: "62 de 140 (44%)", s: "med" },
  { k: "Tests backend passing", v: "446 · 0 failed", s: "low" },
  { k: "Flujos intermodulares", v: "21 documentados", s: "low" },
  { k: "Workflows n8n templates", v: "15 diseñados · 0 prod", s: "med" },
  { k: "Conectores ERP reales", v: "0 en producción", s: "high" },
  { k: "Clientes piloto", v: "0", s: "high" },
  { k: "Fase actual", v: "2.5 — Operativización", s: "med" },
];

/* Workflows n8n W001–W015 — §5.1 (15 templates diseñados, 0 en producción).
 * W005 = workflow integrado, métrica 23→12 días (§7.3). */
export const WORKFLOWS = Array.from({ length: 15 }, (_, i) => {
  const id = `W${String(i + 1).padStart(3, "0")}`;
  const integrated = id === "W005";
  return {
    id,
    name: integrated ? "Workflow integral multi-capa" : `Template intermodular ${id}`,
    layers: integrated ? ["AUD", "TAX", "LEG", "FIN", "CYB", "ADV"] : ["AUT", "ADV"],
    phase: integrated ? 4 : (i % 5) + 1,
    phases: 6,
    days: integrated ? 12 : null,
    daysBaseline: integrated ? 23 : null,
    state: "Diseñado · 0 en producción",
    highlight: integrated,
  };
});

/* Caso de referencia GRUPO_002 — Informe §7 */
export const GRUPO_002 = {
  name: "GRUPO_002",
  exposure: "USD 42M (grupo)",
  status: "Validado end-to-end · workflow 23 → 12 días",
  entities: [
    { e: "Holding ETVE", j: "España", role: "Tenedora + estructura fiscal", exp: "USD 42M grupo" },
    { e: "Operadora EC", j: "Ecuador", role: "Operación principal + nómina", exp: "Por determinar" },
    { e: "Operadora CO", j: "Colombia", role: "Operación regional + BCP/DRP crítico", exp: "Por determinar" },
    { e: "Operadora PE", j: "Perú", role: "Expansión — operación más reciente", exp: "Por determinar" },
  ],
  findings: [
    { n: 1, t: "Sustancia económica del holding insuficiente — riesgo BEPS y CDI", m: "TAX + LEG", r: "Alto" },
    { n: 2, t: "Precios de transferencia sin documentación formal (TP faltante)", m: "TAX + AUD", r: "Alto" },
    { n: 3, t: "NIA 570 activado — señales de empresa en funcionamiento", m: "AUD + FIN", r: "Alto" },
    { n: 4, t: "BCP/DRP inexistente en Operadora CO", m: "CYB + LEG", r: "Alto" },
    { n: 5, t: "Gaps de compliance tributario multi-jurisdiccional", m: "TAX + LEG + FIN", r: "Alto" },
  ],
  decisions: [
    "NO distribuir dividendos en 2025 — acordado por directorio.",
    "Plan de remediación 90 días activado (TAX + LEG + FIN + CYB).",
    "Reducción de workflow de 23 a 12 días validada con este caso.",
  ],
};

/* Flujos intermodulares críticos — Informe §2.1 (21 flows en total) */
export const FLOWS = [
  { id: "Flow 11", a: "TAX", b: "FIN", t: "Decisión financiero-fiscal coordinada", crit: true },
  { id: "Flow 14", a: "TAX", b: "LEG", t: "Validación cruzada legal-fiscal", crit: true },
  { id: "Flow 20", a: "AUT", b: "ALL", t: "Capa de transporte universal", crit: true },
  { id: "Flow 21", a: "ROUTER", b: "AUT", t: "Puerta única de entrada externa", crit: true },
];

/* Audit Trail preview — stream ilustrativo (Regla #5). Riesgo Bajo/Medio/Alto. */
export const AUDIT_TRAIL = [
  { t: "07:58:12", layer: "GOV", evt: "Regla #3 aplicada — flag revisión humana en output TAX", risk: "Alto" },
  { t: "07:57:40", layer: "AUD", evt: "NIA 570 activado · GRUPO_002 — señal empresa en funcionamiento", risk: "Alto" },
  { t: "07:56:05", layer: "TAX", evt: "Flow 11 → FIN: coordinación decisión de dividendos 2025", risk: "Medio" },
  { t: "07:54:31", layer: "AUT", evt: "Flow 20 — transporte de payload ADV → CRE (sin modificar)", risk: "Bajo" },
  { t: "07:52:18", layer: "CYB", evt: "Hallazgo registrado — BCP/DRP inexistente Operadora CO", risk: "Alto" },
  { t: "07:50:02", layer: "ROUTER", evt: "Flow 21 — solicitud externa enrutada a AUT (latencia 212ms)", risk: "Bajo" },
  { t: "07:48:47", layer: "ADV", evt: "Convergencia de hallazgos → Board Pack GRUPO_002 en cola", risk: "Medio" },
  { t: "07:46:11", layer: "DATA", evt: "Detección de outliers en transacciones intercompany", risk: "Medio" },
];

export const AGENT_STATE = {
  idle: { label: "En espera", tone: "faint" },
  thinking: { label: "Analizando", tone: "cyan" },
  producing: { label: "Generando entregable", tone: "gold" },
  awaiting: { label: "Espera aprobación Socio", tone: "high" },
};

export const STATUS_TONE = {
  operativo: "low",
  parcial: "med",
  pendiente: "high",
};
