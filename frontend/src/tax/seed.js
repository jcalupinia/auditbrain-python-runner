// Esquemas de estados financieros, seed de ejemplo (SIGMANSERVICES) y
// defaults. La estructura de filas define también el "formato del balance
// resumido" que el parser (101 / plantilla) debe poblar.

// ESF: ['sec',label] sección | ['in',key,label] input editable |
//      ['sub'|'tot',key,label,op,...] línea calculada.
export const ESF_SCHEMA = [
  ["sec", "ACTIVO CORRIENTE"],
  ["in", "efectivo", "Efectivo y equivalentes"],
  ["in", "inversiones", "Inversiones"],
  ["in", "cxc", "Cuentas por cobrar"],
  ["in", "cxcRel", "CxC relacionadas"],
  ["in", "impRec", "Impuestos por recuperar"],
  ["in", "otrasCxc", "Otras CxC"],
  ["in", "inventario", "Inventario"],
  ["sub", "totalAC", "Total activo corriente"],
  ["sec", "ACTIVO NO CORRIENTE"],
  ["in", "ppe", "Propiedad, planta y equipo"],
  ["in", "actImpDif", "Activos imp. diferidos"],
  ["sub", "totalANC", "Total activo no corriente"],
  ["tot", "totalActivo", "TOTAL ACTIVO"],
  ["sec", "PASIVO CORRIENTE"],
  ["in", "cxp", "Cuentas por pagar"],
  ["in", "impPagar", "Impuestos por pagar"],
  ["in", "benef", "Beneficios sociales"],
  ["in", "anticipos", "Anticipos clientes"],
  ["in", "provisiones", "Provisiones"],
  ["in", "otrasCxp", "Otras CxP"],
  ["sub", "totalPC", "Total pasivo corriente"],
  ["sec", "PASIVO NO CORRIENTE"],
  ["in", "benefPost", "Beneficios post-empleo"],
  ["in", "cxpRel", "CxP relacionadas"],
  ["in", "pasImpDif", "Pasivos imp. diferidos"],
  ["sub", "totalPNC", "Total pasivo no corriente"],
  ["tot", "totalPasivo", "TOTAL PASIVO"],
  ["sec", "PATRIMONIO"],
  ["in", "capital", "Capital"],
  ["in", "reservas", "Reservas"],
  ["in", "ori", "Otros result. integrales"],
  ["in", "resAcum", "Resultados acumulados"],
  ["tot", "totalPat", "TOTAL PATRIMONIO"],
];

export const ER_SCHEMA = [
  ["in", "ventas", "Ventas / ingresos ordinarios"],
  ["in", "otrosIng", "Otros ingresos"],
  ["in", "otrosIngFin", "Otros ingresos financieros"],
  ["in", "costo", "(−) Costo de servicios"],
  ["tot", "ub", "UTILIDAD BRUTA"],
  ["in", "gAdmin", "(−) Gastos admin. y ventas"],
  ["tot", "ebit", "UTILIDAD OPERATIVA (EBIT)"],
  ["in", "gFin", "(−) Gastos financieros"],
  ["sub", "uai", "Utilidad antes de impuestos"],
  ["in", "partTrab", "(−) Participación trabajadores"],
  ["in", "irCausado", "(−) Impuesto renta causado"],
  ["in", "impDif", "(−) Impuesto diferido"],
  ["tot", "neta", "RESULTADO NETO"],
];

// Todas las claves de input (las que el parser debe llenar).
export const INPUT_KEYS = [
  ...ESF_SCHEMA.filter((r) => r[0] === "in").map((r) => r[1]),
  ...ER_SCHEMA.filter((r) => r[0] === "in").map((r) => r[1]),
];

export const ANIOS = [2023, 2024, 2025];
export const PROJ = [2026, 2027, 2028];

// Seed de ejemplo: SIGMANSERVICES S.A. (2023, 2024, 2025).
export const EX = {
  efectivo: [448732, 343842, 478936],
  inversiones: [1501284, 1008598, 601284],
  cxc: [1627271, 1888684, 1621426],
  cxcRel: [265223, 45296, 85786],
  impRec: [5421, 137822, 61379],
  otrasCxc: [157631, 348322, 65870],
  inventario: [1995957, 2036930, 2824704],
  ppe: [794152, 792737, 746932],
  actImpDif: [54413, 55317, 58170],
  cxp: [1868958, 1468450, 1317706],
  impPagar: [320826, 414397, 198919],
  benef: [158325, 176028, 118204],
  anticipos: [802452, 443060, 445930],
  provisiones: [114000, 0, 0],
  otrasCxp: [139, 0, 0],
  benefPost: [45309, 51363, 70641],
  cxpRel: [0, 0, 718],
  pasImpDif: [8773, 0, 0],
  capital: [800, 800, 800],
  reservas: [26108, 26108, 26108],
  ori: [185591, 109499, 106541],
  resAcum: [3318801, 3967845, 4258920],
  ventas: [9776562, 9788597, 7599670],
  otrosIng: [302863, 139154, 169082],
  otrosIngFin: [79432, 81010, 47853],
  costo: [6056277, 5847007, 4608110],
  gAdmin: [3308617, 3259544, 2628007],
  gFin: [0, 0, 5047],
  partTrab: [0, 0, 85846],
  irCausado: [220037, 253165, 149203],
  impDif: [0, 0, 278],
  dna: [0, 0, 0], // Depreciación/amortización (para EBITDA) — completar a mano.
};

// Empresa en blanco (todos los inputs en 0, 3 años).
export function emptyData() {
  const D = {};
  INPUT_KEYS.forEach((k) => (D[k] = [0, 0, 0]));
  D.dna = [0, 0, 0];
  return D;
}

export const DEFAULT_CTRL = [
  { g: 0, div: 0, cap: 0 },
  { g: 5, div: 0, cap: 0 },
  { g: 5, div: 0, cap: 0 },
];

// Parámetros editables (requieren validación humana — ver normativa).
export const DEFAULT_PARAMS = {
  empresa: "SIGMANSERVICES S.A.", // razón social
  ruc: "", // RUC del contribuyente
  repLegal: "", // representante legal (para dirigir el informe)
  fechaCorte: "", // fecha de corte del análisis (ISO yyyy-mm-dd)
  fechaAnalisis: "", // fecha del cálculo (ISO); vacío => fecha de hoy
  costoR: 60.6, // costo / ventas (%)
  gastoR: 34.6, // gastos op. / ventas (%)
  irR: 25, // tasa Impuesto a la Renta (%)
  retDiv: 12, // retención impuesto único dividendos (%) — verificar normativa
};

export const EXAMPLE_PARAMS = { ...DEFAULT_PARAMS };
