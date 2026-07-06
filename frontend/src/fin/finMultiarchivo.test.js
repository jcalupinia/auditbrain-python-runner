import { describe, it, expect } from "vitest";
import { alinearMultiarchivo } from "./finPeriodos.js";

// Caso real SIGMANSERVICE detallado: ESF y ERI en archivos SEPARADOS.
// ESF: dic-23, dic-24, dic-25, may-26            (4 períodos, sin may-25)
// ERI: dic-23, dic-24, dic-25, may-25, may-26    (5 períodos, con may-25)
// El eje del dashboard lo define el balance -> 4 columnas; may-25 queda fuera
// del eje (se usa en Comparaciones). El detalle por cuenta debe conservarse y
// remapearse por identidad (may-25 no se suma a dic-25).
const P = (label, tipo, meses, anio) => ({ label, tipo, meses, anio });

const esfFile = {
  periodos_esf: [
    P("31-dic-2023", "anual", 12, 2023),
    P("31-dic-2024", "anual", 12, 2024),
    P("31-dic-2025", "anual", 12, 2025),
    P("31-may-2026", "parcial", 5, 2026),
  ],
  periodos_eri: [],
  data: { efectivo: [10, 20, 30, 40] }, // clave ESF, índice periodos_esf
  detalle: [
    { sec: "activo", key: "efectivo", codigo: "1.01.01.02.001", nombre: "Banco X", vals: [10, 20, 30, 40] },
  ],
};

const eriFile = {
  periodos_esf: [],
  periodos_eri: [
    P("31-dic-2023", "anual", 12, 2023),
    P("31-dic-2024", "anual", 12, 2024),
    P("31-dic-2025", "anual", 12, 2025),
    P("31-may-2025", "parcial", 5, 2025),
    P("31-may-2026", "parcial", 5, 2026),
  ],
  data: { ventas: [900, 950, 700, 250, 300], gAdmin: [300, 310, 260, 90, 100] },
  detalle: [
    { sec: "resultado", key: "gAdmin", codigo: "6.01.01.001", nombre: "Sueldos", vals: [300, 310, 260, 90, 100] },
    { sec: "resultado", key: "costo", codigo: "5.1.01.001", nombre: "Costo equipos", vals: [600, 580, 460, 140, 200] },
  ],
};

describe("alinearMultiarchivo — ESF + ERI en archivos separados", () => {
  const { D, periodos, cuentas } = alinearMultiarchivo([esfFile, eriFile]);

  it("el eje toma los 4 períodos del balance (may-25 queda fuera)", () => {
    expect(periodos.map((p) => p.label)).toEqual([
      "31-dic-2023", "31-dic-2024", "31-dic-2025", "31-may-2026",
    ]);
  });

  it("las claves ESF salen del archivo ESF, alineadas al eje", () => {
    expect(D.efectivo).toEqual([10, 20, 30, 40]);
  });

  it("las claves ER salen del archivo ERI; may-26 (no dic-25) en la 4ta col; may-25 NO se mezcla", () => {
    // eje = [dic23, dic24, dic25, may26] -> ventas ERI idx [0,1,2,4]
    expect(D.ventas).toEqual([900, 950, 700, 300]);
    expect(D.gAdmin).toEqual([300, 310, 260, 100]);
  });

  it("conserva el detalle por cuenta (drill-down) para gastos/atípicos", () => {
    const sueldos = cuentas.find((c) => c.nombre === "Sueldos");
    expect(sueldos).toBeTruthy();
    expect(sueldos.key).toBe("gastAdm"); // PARSER_TO_DASH: gAdmin -> gastAdm
    // vals remapeados al eje: [dic23, dic24, dic25, may26] = [300,310,260,100]
    expect(sueldos.vals).toEqual([300, 310, 260, 100]);
    const costo = cuentas.find((c) => c.nombre === "Costo equipos");
    expect(costo.key).toBe("costoVta");
    expect(costo.vals).toEqual([600, 580, 460, 200]);
    // la cuenta de balance también se conserva
    expect(cuentas.find((c) => c.nombre === "Banco X").vals).toEqual([10, 20, 30, 40]);
  });

  it("NO suma may-25 dentro de dic-25 (no hay colapso por año)", () => {
    const sueldos = cuentas.find((c) => c.nombre === "Sueldos");
    // dic-25 debe ser 260 (su valor real), NO 260+90 (may-25).
    expect(sueldos.vals[2]).toBe(260);
  });
});
