import { describe, it, expect } from "vitest";
import { tarifa, creditAging } from "../engine.js";

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
