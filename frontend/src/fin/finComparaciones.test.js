import { describe, it, expect } from "vitest";
import { pctVar, comparacionFilas, construirParesEri } from "./finComparaciones.js";

describe("construirParesEri — anualización de respaldo", () => {
  it("con may-25 presente: compara parcial vs parcial (sin prorratear)", () => {
    const per = [
      { label: "may-26", tipo: "parcial", meses: 5, anio: 2026 },
      { label: "may-25", tipo: "parcial", meses: 5, anio: 2025 },
      { label: "2025", tipo: "anual", meses: 12, anio: 2025 },
      { label: "2024", tipo: "anual", meses: 12, anio: 2024 },
    ];
    const pares = construirParesEri(per);
    expect(pares[0]).toEqual(["may-26", "may-25"]); // sin factor
    expect(pares).toContainEqual(["2025", "2024"]);
    expect(pares.some((p) => p[2])).toBe(false); // ningún factor de prorrateo
  });

  it("sin may-25: anualiza el cierre anterior ×(meses/12) para comparar con may-26", () => {
    const per = [
      { label: "may-26", tipo: "parcial", meses: 5, anio: 2026 },
      { label: "2025", tipo: "anual", meses: 12, anio: 2025 },
      { label: "2024", tipo: "anual", meses: 12, anio: 2024 },
    ];
    const pares = construirParesEri(per);
    expect(pares[0][0]).toBe("may-26");
    expect(pares[0][1]).toBe("2025");
    expect(pares[0][2]).toBeCloseTo(5 / 12); // factor de anualización
    expect(pares[0][3]).toMatch(/anualizado/);
    expect(pares).toContainEqual(["2025", "2024"]);
  });

  it("el factor escala el valor anterior en comparacionFilas", () => {
    const data = { ventas: [500, 1200, 1500] }; // may-26, 2025, 2024
    const labels = ["may-26", "2025", "2024"];
    const pares = [["may-26", "2025", 5 / 12]];
    const [fila] = comparacionFilas(data, labels, pares, [["ventas", "Ingresos"]]);
    // may-26(500) - 2025(1200×5/12=500) = 0
    expect(fila.celdas[0].delta).toBeCloseTo(0);
  });
});

describe("pctVar", () => {
  it("calcula variación porcentual", () => {
    expect(pctVar(110, 100)).toBeCloseTo(10);
    expect(pctVar(90, 100)).toBeCloseTo(-10);
  });
  it("devuelve null si la base es 0 o falta un valor", () => {
    expect(pctVar(100, 0)).toBeNull();
    expect(pctVar(null, 100)).toBeNull();
    expect(pctVar(100, null)).toBeNull();
  });
});

describe("comparacionFilas — ESF encadenado", () => {
  // Estructura tipo SIGMAN: labels_esf = [may-26, 2025, 2024, 2023]
  const labels = ["may-26", "2025", "2024", "2023"];
  const pares = [["may-26", "2025"], ["2025", "2024"], ["2024", "2023"]];
  const data = {
    efectivo: [1033, 1080, 1352, 1950],
    inventario: [2693, 2824, 2036, 1995],
    vacio: [0, 0, 0, 0],
  };
  const rubros = [["efectivo", "Efectivo"], ["inventario", "Inventario"], ["vacio", "Vacío"]];

  it("omite rubros todo-cero", () => {
    const filas = comparacionFilas(data, labels, pares, rubros);
    expect(filas.map((f) => f.key)).toEqual(["efectivo", "inventario"]);
  });

  it("calcula delta encadenado actual vs anterior", () => {
    const [efectivo] = comparacionFilas(data, labels, pares, rubros);
    // may-26 vs 2025
    expect(efectivo.celdas[0].delta).toBe(1033 - 1080);
    // 2025 vs 2024
    expect(efectivo.celdas[1].delta).toBe(1080 - 1352);
    // 2024 vs 2023
    expect(efectivo.celdas[2].delta).toBe(1352 - 1950);
  });
});

describe("comparacionFilas — ERI parcial vs parcial + anual", () => {
  // labels_er = [may-26, may-25, 2025, 2024, 2023]; los rubros ERI tienen 5 valores
  const labels = ["may-26", "may-25", "2025", "2024", "2023"];
  const pares = [["may-26", "may-25"], ["2025", "2024"], ["2024", "2023"]];
  const data = { ventas: [2930, 2573, 7599, 9788, 9776] };
  const rubros = [["ventas", "Ingresos"]];

  it("compara parcial vs parcial (like-for-like) y anual vs anual, sin cruzar", () => {
    const [ventas] = comparacionFilas(data, labels, pares, rubros);
    expect(ventas.celdas[0].par).toEqual(["may-26", "may-25"]);
    expect(ventas.celdas[0].delta).toBe(2930 - 2573); // parcial 5m
    expect(ventas.celdas[1].par).toEqual(["2025", "2024"]);
    expect(ventas.celdas[1].delta).toBe(7599 - 9788); // anual
  });

  it("una etiqueta ausente produce celda nula, no un cruce erróneo", () => {
    const filas = comparacionFilas({ ventas: [10, 20, 30, 40, 50] }, labels, [["may-26", "inexistente"]], rubros);
    expect(filas[0].celdas[0].delta).toBeNull();
  });
});
