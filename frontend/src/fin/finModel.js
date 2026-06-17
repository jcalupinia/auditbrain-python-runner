// Modelo del módulo FIN · CFO Intelligence.
// Reutiliza el mismo modelo de datos `D` de Planificación de Utilidades
// (claves con arrays [a0,a1,a2]) y lo mapea al modelo del Dashboard Ejecutivo
// (claves con {anio:valor}) que consume la plantilla HTML autocontenida.

import { ANIOS, ESF_SCHEMA } from "../tax/seed.js";
import { tAC, tActivo, tPC, tPasivo, tPat } from "../tax/engine.js";

export const FIN_YRS = ANIOS; // [2023, 2024, 2025] (compat / período por defecto)

export const NIVELES = ["resumido", "detallado"];

// Mapea las claves del modelo del parser (detalle por cuenta) a las claves del
// DASHBOARD (rubros que muestra la plantilla en Resumido), espejo de mapToDashboard.
// Permite el drill-down: clic en un rubro → cuentas cuya clave-dash coincide.
export const PARSER_TO_DASH = {
  // Activos
  efectivo: "efectivo", inversiones: "actFin", cxc: "cxc", inventario: "inventario",
  cxcRel: "cxcRelac", anticiposProv: "anticiposProv", otrasCxc: "otrosAct", impRec: "actImpCorr",
  ppe: "propEquip", actImpDif: "actImpDif", cxcLP: "cxcLP", otrosActNoCorr: "otrosActNoCorr",
  // Pasivos
  oblBanc: "oblBanc", cxp: "cxp", benef: "benefEmpl", impPagar: "pasImpCorr",
  cxpRelCorr: "cxpRelacPas", provisiones: "provisiones", anticipos: "otrasCxp", otrasCxp: "otrasCxp",
  prestamosLP: "prestamosLP", benefPost: "benDefLP", cxpRel: "benDefLP", pasImpDif: "pasImpDifLP",
  // Patrimonio
  capital: "capital", reservas: "resLegal", ori: "oriAcum", resAcum: "utilAcum",
  // Estado de Resultados
  ventas: "ingOrd", otrosIng: "ingNoOrd", otrosIngFin: "ingNoOrd", costo: "costoVta",
  gAdmin: "gastAdm", gFin: "gastFin", impDif: "irDif", partTrab: "irCorr", irCausado: "irCorr",
};

// Período de análisis → número de meses que cubre el flujo (Estado de Resultados).
export const PERIODO_MESES = { anual: 12, semestral: 6, trimestral: 3, mensual: 1 };

// Claves de FLUJO (Estado de Resultados). Solo estas se prorratean al normalizar
// períodos de distinta longitud. Las del balance (stock) NUNCA se tocan.
export const ER_KEYS = [
  "ventas", "otrosIng", "otrosIngFin", "costo", "gAdmin", "gFin",
  "partTrab", "irCausado", "impDif",
];

// Prorratea el Estado de Resultados de cada período a una base común de meses.
// `periodos[i] = { meses, normalizar }`. Balance intacto. Devuelve un D nuevo.
export function normalizarER(D, periodos, baseMeses) {
  const out = {};
  Object.keys(D).forEach((k) => { out[k] = Array.isArray(D[k]) ? D[k].slice() : D[k]; });
  (periodos || []).forEach((p, i) => {
    if (!p || !p.normalizar || !p.meses || p.meses === baseMeses) return;
    const f = baseMeses / p.meses;
    ER_KEYS.forEach((k) => {
      if (Array.isArray(out[k]) && out[k][i] != null) out[k][i] = Math.round(out[k][i] * f);
    });
  });
  return out;
}

// Cabecera editable del dashboard (marca / contexto del cliente).
export const DEFAULT_HEADER = {
  empresa: "",
  subtitulo: "Estados financieros · NIIF · USD · Análisis ejecutivo CFO Intelligence",
  pie: "NIIF · Estados financieros para análisis interno",
};

// Detalle CFO (las 4 sub-secciones nuevas). Tablas editables independientes.
export const EMPTY_DETALLE = {
  gastos: [], // { concepto, v:[a0,a1,a2] }
  atipicos: [], // { concepto, anio, monto, just }
  activos: [], // { desc, categoria, anio, monto }
  inversiones: [], // { instrumento, anio, monto, rendimiento }
};

// Filas en blanco para "agregar".
export const BLANK_ROW = {
  gastos: () => ({ concepto: "", v: FIN_YRS.map(() => 0) }),
  atipicos: () => ({ concepto: "", anio: FIN_YRS[FIN_YRS.length - 1], monto: 0, just: "" }),
  activos: () => ({ desc: "", categoria: "", anio: FIN_YRS[FIN_YRS.length - 1], monto: 0 }),
  inversiones: () => ({ instrumento: "", anio: FIN_YRS[FIN_YRS.length - 1], monto: 0, rendimiento: "" }),
};

// Suma segura de varias claves de `D` en el año c (índice 0..2).
const sum = (D, c, keys) => keys.reduce((s, k) => s + (D[k] ? +D[k][c] || 0 : 0), 0);

// Convierte el modelo `D` (Planificación de Utilidades) al objeto DEFAULT que
// espera la plantilla del dashboard. La ecuación A = P + Patrimonio se conserva
// exacta porque las agrupaciones son particiones de los mismos rubros.
export function mapToDashboard(D, labels = FIN_YRS) {
  const yobj = (fn) => {
    const o = {};
    // Se conservan 2 decimales (centavos): el balance cuadra EXACTO (A=P+Patrimonio)
    // sin el ruido de ±$ que producía redondear cada rubro a entero. La presentación
    // (n$) redondea igual a entero, así que lo mostrado no cambia.
    labels.forEach((y, c) => {
      const v = fn(c);
      o[y] = v == null ? v : Math.round(v * 100) / 100;
    });
    return o;
  };
  return {
    // ── Estado de Resultados (costos/gastos en negativo) ──
    ingOrd: yobj((c) => +D.ventas[c] || 0),
    costoVta: yobj((c) => -(+D.costo[c] || 0)),
    gastAdm: yobj((c) => -(+D.gAdmin[c] || 0)),
    gastFin: yobj((c) => -(+D.gFin[c] || 0)),
    ingNoOrd: yobj((c) => (+D.otrosIng[c] || 0) + (+D.otrosIngFin[c] || 0)),
    // Participación trabajadores se agrupa con el bloque de impuestos para que
    // la utilidad neta reconstruya EXACTAMENTE la utilidad auditada.
    irCorr: yobj((c) => -((+D.irCausado[c] || 0) + (+D.partTrab[c] || 0))),
    irDif: yobj((c) => -(+D.impDif[c] || 0)),
    dna: yobj((c) => (D.dna ? +D.dna[c] || 0 : 0)), // depreciación + amortización (para EBITDA)
    ori: yobj(() => 0),
    // ── Balance · Activos ──
    efectivo: yobj((c) => +D.efectivo[c] || 0),
    actFin: yobj((c) => +D.inversiones[c] || 0),
    cxc: yobj((c) => +D.cxc[c] || 0),
    inventario: yobj((c) => (D.inventario ? +D.inventario[c] || 0 : 0)),
    cxcRelac: yobj((c) => (D.cxcRel ? +D.cxcRel[c] || 0 : 0)),
    anticiposProv: yobj((c) => (D.anticiposProv ? +D.anticiposProv[c] || 0 : 0)),
    otrosAct: yobj((c) => (D.otrasCxc ? +D.otrasCxc[c] || 0 : 0)),
    actImpCorr: yobj((c) => (D.impRec ? +D.impRec[c] || 0 : 0)),
    propEquip: yobj((c) => +D.ppe[c] || 0),
    actImpDif: yobj((c) => +D.actImpDif[c] || 0),
    cxcLP: yobj((c) => (D.cxcLP ? +D.cxcLP[c] || 0 : 0)),
    otrosActNoCorr: yobj((c) => (D.otrosActNoCorr ? +D.otrosActNoCorr[c] || 0 : 0)),
    // ── Balance · Pasivos ──
    oblBanc: yobj((c) => (D.oblBanc ? +D.oblBanc[c] || 0 : 0)),
    cxp: yobj((c) => +D.cxp[c] || 0),
    benefEmpl: yobj((c) => (D.benef ? +D.benef[c] || 0 : 0)),
    pasImpCorr: yobj((c) => +D.impPagar[c] || 0),
    cxpRelacPas: yobj((c) => (D.cxpRelCorr ? +D.cxpRelCorr[c] || 0 : 0)),
    provisiones: yobj((c) => (D.provisiones ? +D.provisiones[c] || 0 : 0)),
    otrasCxp: yobj((c) => sum(D, c, ["anticipos", "otrasCxp"])),
    prestamosLP: yobj((c) => (D.prestamosLP ? +D.prestamosLP[c] || 0 : 0)),
    benDefLP: yobj((c) => sum(D, c, ["benefPost", "cxpRel"])),
    pasImpDifLP: yobj((c) => (D.pasImpDif ? +D.pasImpDif[c] || 0 : 0)),
    // ── Patrimonio ──
    capital: yobj((c) => +D.capital[c] || 0),
    resLegal: yobj((c) => +D.reservas[c] || 0),
    oriAcum: yobj((c) => +D.ori[c] || 0),
    utilAcum: yobj((c) => +D.resAcum[c] || 0),
    // ── KPIs operativos (placeholder editable en el artefacto) ──
    numHab: yobj(() => null),
    ocupacion: yobj(() => null),
    adr: yobj(() => null),
    nps: yobj(() => null),
  };
}

// Línea calculada del balance (espejo del tool de Planificación de Utilidades).
function calcLine(D, key, c) {
  switch (key) {
    case "totalAC": return tAC(D, c);
    case "totalANC": return D.ppe[c] + D.actImpDif[c];
    case "totalActivo": return tActivo(D, c);
    case "totalPC": return tPC(D, c);
    case "totalPNC": return D.benefPost[c] + D.cxpRel[c] + D.pasImpDif[c];
    case "totalPasivo": return tPasivo(D, c);
    case "totalPat": return tPat(D, c);
    default: return 0;
  }
}

// Construye el balance a nivel DETALLADO (todas las cuentas del ESF_SCHEMA),
// con valores por año. Lo consume la plantilla cuando el usuario pide "detallado".
export function buildDetailedBalance(D, labels = FIN_YRS) {
  return ESF_SCHEMA.map((sp) => {
    const [t, key, label] = sp;
    if (t === "sec") return { t: "sec", label: sp[1] };
    const vals = {};
    labels.forEach((y, c) => {
      vals[y] = Math.round(t === "in" ? +D[key][c] || 0 : calcLine(D, key, c));
    });
    return { t: t === "in" ? "in" : "tot", label, vals };
  });
}

// Verificación de cuadratura A = P + Patrimonio sobre el modelo mapeado.
export function checkBalance(dash, labels = FIN_YRS) {
  return labels.map((y) => {
    const A =
      dash.efectivo[y] + dash.actFin[y] + dash.cxc[y] + (dash.cxcRelac?.[y] || 0) +
      (dash.anticiposProv?.[y] || 0) + (dash.inventario?.[y] || 0) +
      dash.otrosAct[y] + dash.actImpCorr[y] + dash.propEquip[y] + dash.actImpDif[y] +
      (dash.cxcLP?.[y] || 0) + (dash.otrosActNoCorr?.[y] || 0);
    const P =
      dash.oblBanc[y] + dash.cxp[y] + (dash.benefEmpl?.[y] || 0) + dash.pasImpCorr[y] +
      (dash.cxpRelacPas?.[y] || 0) + (dash.provisiones?.[y] || 0) + dash.otrasCxp[y] +
      (dash.prestamosLP?.[y] || 0) + dash.benDefLP[y] + (dash.pasImpDifLP?.[y] || 0);
    const Pat = dash.capital[y] + dash.resLegal[y] + dash.oriAcum[y] + dash.utilAcum[y];
    return { anio: y, A, P, Pat, dif: A - (P + Pat) };
  });
}
