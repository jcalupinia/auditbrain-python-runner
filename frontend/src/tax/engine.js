// Motor de planificación tributaria sobre utilidades no distribuidas (Ecuador).
// Portado 1:1 desde app/index.html del proyecto AuditBrain_TaxAnalisis.
// IMPORTANTE: no alterar la lógica tributaria sin validación humana.
//   - Tarifa única por tramo (no progresiva).
//   - Base = utilidades acumuladas − dividendos − capitalización (corte 31 jul).
//   - Crédito: 1) retención dividendos, 2) Impuesto a la Renta, 3) devolución.
//   - Roll-forward: Patrimonio_t = Patrimonio_{t-1} + neta − dividendos.

// Tramos de tarifa única: [límite superior, tarifa]. La tarifa del tramo se
// aplica a TODA la base (no es progresiva).
export const BR = [
  [100000, 0],
  [1000000, 0.0075],
  [10000000, 0.0125],
  [100000000, 0.0175],
  [500000000, 0.0225],
  [Infinity, 0.025],
];

export const tarifa = (b) => {
  for (const [lim, t] of BR) if (b <= lim) return t;
  return 0.025;
};

/* ===================== TOTALES EEFF ===================== */
// c = índice de año (0,1,2)
export const tAC = (D, c) =>
  ["efectivo", "inversiones", "cxc", "cxcRel", "impRec", "otrasCxc", "inventario"].reduce(
    (s, k) => s + D[k][c],
    0,
  );
export const tActivo = (D, c) => tAC(D, c) + D.ppe[c] + D.actImpDif[c];
export const tPC = (D, c) =>
  ["cxp", "impPagar", "benef", "anticipos", "provisiones", "otrasCxp"].reduce(
    (s, k) => s + D[k][c],
    0,
  );
export const tPasivo = (D, c) => tPC(D, c) + D.benefPost[c] + D.cxpRel[c] + D.pasImpDif[c];
export const tPat = (D, c) => D.capital[c] + D.reservas[c] + D.ori[c] + D.resAcum[c];
export const ub = (D, c) => D.ventas[c] + D.otrosIng[c] + D.otrosIngFin[c] - D.costo[c];
export const ebit = (D, c) => ub(D, c) - D.gAdmin[c];
export const uai = (D, c) => ebit(D, c) - D.gFin[c];
export const neta = (D, c) => uai(D, c) - D.partTrab[c] - D.irCausado[c] - D.impDif[c];

// EBITDA = EBIT + Depreciación y amortización (D&A se ingresa a mano si el
// estado de resultados no la desglosa).
export const ebitda = (D, c) => ebit(D, c) + (D.dna ? D.dna[c] || 0 : 0);

export function ind(D, c) {
  const AC = tAC(D, c),
    PC = tPC(D, c),
    A = tActivo(D, c),
    P = tPasivo(D, c),
    PT = tPat(D, c),
    inv = D.inventario[c],
    V = D.ventas[c],
    C = D.costo[c],
    n = neta(D, c),
    e = ebit(D, c);
  return {
    liq: AC / PC,
    acid: (AC - inv) / PC,
    ct: AC - PC,
    end: P / A,
    apal: A / PT,
    mb: ub(D, c) / V,
    mo: e / V,
    mn: n / V,
    roe: n / PT,
    roa: n / A,
    rot: V / A,
    dCart: (D.cxc[c] / V) * 365,
    dInv: (inv / C) * 365,
    dProv: (D.cxp[c] / C) * 365,
    A,
    P,
    PT,
    V,
    n,
    e,
  };
}

export const cce = (D, c) => {
  const i = ind(D, c);
  return i.dCart + i.dInv - i.dProv;
};

/* ===================== PROYECCIÓN ===================== */
// params: { costoR, gastoR, irR, retDiv } en PORCENTAJE (ej. 60.6, 25, 10).
export function computeER(D, CTRL, params) {
  const cR = params.costoR / 100,
    gR = params.gastoR / 100,
    irR = params.irR / 100;
  let pv = D.ventas[2],
    po = D.otrosIng[2] + D.otrosIngFin[2],
    out = [];
  CTRL.forEach((c) => {
    const ventas = pv * (1 + c.g / 100),
      otros = po,
      costo = ventas * cR,
      ubx = ventas + otros - costo,
      gAdmin = ventas * gR,
      e = ubx - gAdmin,
      uaix = e,
      part = uaix * 0.15,
      baseIR = uaix - part,
      irC = Math.max(0, baseIR * irR),
      n = uaix - part - irC;
    out.push({
      ventas,
      otros,
      costo,
      ub: ubx,
      gAdmin,
      ebit: e,
      uai: uaix,
      part,
      irCausado: irC,
      neta: n,
    });
    pv = ventas;
    po = otros;
  });
  return out;
}

export function computeModel(D, CTRL, params) {
  const er = computeER(D, CTRL, params),
    rd = params.retDiv / 100;
  let resAcum = D.resAcum[2],
    capital = D.capital[2],
    patrimonio = tPat(D, 2),
    pasivo = tPasivo(D, 2),
    riesgo = 0,
    rows = [];
  er.forEach((e, i) => {
    const div = CTRL[i].div,
      cap = CTRL[i].cap,
      base = Math.max(0, resAcum - div - cap),
      tar = tarifa(base),
      pago = base * tar,
      ret = div * rd, // retención impuesto único dividendos
      cRet = Math.min(pago, ret); // crédito usado vs. retención
    let resto = pago - cRet;
    const cIR = Math.min(resto, e.irCausado); // crédito que REDUCE el IR
    resto -= cIR;
    const dev = div > 0 || cap > 0 ? resto : 0, // excedente a devolución
      enR = div <= 0 && cap <= 0 ? pago : 0, // en riesgo de costo muerto
      irAP = e.irCausado - cIR; // IR a pagar (neto del crédito)
    // roll-forward patrimonial
    resAcum += e.neta - div - cap;
    capital += cap;
    patrimonio += e.neta - div;
    pasivo *= 1 + CTRL[i].g / 100;
    riesgo += enR;
    rows.push({
      ...e,
      div,
      cap,
      base,
      tar,
      pago,
      ret,
      cRet,
      cIR,
      dev,
      enR,
      irAP,
      resAcum,
      capital,
      patrimonio,
      pasivo,
      activo: pasivo + patrimonio,
      riesgo,
    });
  });
  return rows;
}

// Pago a cuenta total bajo el escenario "sin acción" (para comparar).
export function scenarioCompare(D, CTRL, params) {
  const er = computeER(D, CTRL, params);
  const run = (d, c) => {
    const tmp = er.map((e, i) => ({ g: CTRL[i].g, div: d(i), cap: c(i) }));
    return computeModel(D, tmp, params).reduce((a, r) => a + r.pago, 0);
  };
  const sin = run(
    () => 0,
    () => 0,
  );
  return { sin };
}

// Devuelve un nuevo CTRL con dividendos/capitalización según el escenario.
// piso = excedente sobre el tramo exento (100.000) que se puede sacar de base.
export function applyScenario(scn, D, CTRL, params) {
  const er = computeER(D, CTRL, params);
  let r = D.resAcum[2];
  return CTRL.map((c, i) => {
    const piso = Math.max(0, r - 100000);
    let div = 0,
      cap = 0;
    if (scn === "sin") {
      div = 0;
      cap = 0;
    } else if (scn === "cap") {
      div = 0;
      cap = piso;
    } else if (scn === "div") {
      div = piso;
      cap = 0;
    } else {
      // mixto
      div = Math.round(piso * 0.4);
      cap = Math.round(piso * 0.6);
    }
    r += er[i].neta - div - cap;
    return { g: c.g, div, cap };
  });
}

export const SCENARIO_NAMES = {
  sin: "Sin acción",
  cap: "Capitalización",
  div: "Distribución",
  mix: "Mixto",
};
