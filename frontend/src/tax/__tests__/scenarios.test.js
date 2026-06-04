import { describe, it, expect } from "vitest";
import {
  tarifa,
  creditAging,
  compareScenarios,
  bestScenario,
} from "../engine.js";
import { emptyData } from "../seed.js";

describe("smoke", () => {
  it("tarifa tramo exento", () => {
    expect(tarifa(50000)).toBe(0);
    expect(tarifa(500000)).toBe(0.0075);
  });
});

describe("creditAging (costo muerto 2 años)", () => {
  // 3 años; anticipo 100 cada uno; acción (div/cap) solo en el año índice indicado
  const rows = (accionEn) =>
    [0, 1, 2].map((i) => ({
      pago: 100,
      div: accionEn.includes(i) ? 50 : 0,
      cap: 0,
    }));

  it("sin acción nunca: el anticipo de 2026 es costo muerto (ventana 0..2)", () => {
    const r = creditAging(rows([]));
    expect(r[0].costoMuerto).toBe(100); // 2026: sin acción en 0,1,2
  });

  it("acción en 2028 recupera el anticipo de 2026 (dentro de ventana)", () => {
    const r = creditAging(rows([2]));
    expect(r[0].costoMuerto).toBe(0); // hubo acción en el año 2 (= 2028)
  });

  it("anticipo de 2028 con ventana fuera de horizonte se marca", () => {
    const r = creditAging(rows([]));
    expect(r[2].fueraHorizonte).toBe(true);
  });
});

describe("compareScenarios", () => {
  const D = emptyData();
  // Empresa con utilidades acumuladas altas para que haya impuesto.
  D.resAcum = [0, 0, 5000000];
  D.utilAcum = [0, 0, 4000000];
  D.utilEjercicio = [0, 0, 1000000];
  D.ventas = [0, 0, 8000000];
  D.costo = [0, 0, 5000000];
  D.capital = [0, 0, 100000];
  const params = { costoR: 60, gastoR: 25, irR: 25, retDiv: 12, growth: 0 };

  const r = compareScenarios(D, params);

  it("devuelve los 4 escenarios", () => {
    expect(Object.keys(r).sort()).toEqual(["cap", "div", "mix", "sin"]);
  });

  it("'sin' tiene impuesto > 0 en 2026", () => {
    expect(r.sin.rows[0].impuesto).toBeGreaterThan(0);
  });

  it("'cap' (solo capitalización) lleva el impuesto a ~0", () => {
    const total = r.cap.totales.impuesto;
    expect(total).toBeLessThan(r.sin.totales.impuesto);
    expect(total).toBeLessThan(1);
  });

  it("cada escenario tiene 3 años con costoMuerto definido", () => {
    expect(r.sin.rows).toHaveLength(3);
    expect(typeof r.sin.rows[0].costoMuerto).toBe("number");
  });
});

describe("bestScenario", () => {
  it("elige 'cap' cuando elimina el impuesto", () => {
    const D = emptyData();
    D.resAcum = [0, 0, 5000000];
    D.utilEjercicio = [0, 0, 1000000];
    D.ventas = [0, 0, 8000000];
    D.costo = [0, 0, 5000000];
    D.capital = [0, 0, 100000];
    const params = { costoR: 60, gastoR: 25, irR: 25, retDiv: 12, growth: 0 };
    const r = compareScenarios(D, params);
    expect(bestScenario(r).key).toBe("cap");
  });
});
