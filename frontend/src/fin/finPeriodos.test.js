import { describe, it, expect } from "vitest";
import { identidadPeriodo, alinearPorIdentidad, tienePeriodosTipados } from "./finPeriodos.js";

describe("identidadPeriodo", () => {
  it("parcial usa año*100+mes; anual usa año*100+12", () => {
    expect(identidadPeriodo({ anio: 2026, tipo: "parcial", meses: 5 })).toBe(202605);
    expect(identidadPeriodo({ anio: 2025, tipo: "anual", meses: 12 })).toBe(202512);
    expect(identidadPeriodo({ anio: 2025, tipo: "parcial", meses: 5 })).toBe(202505);
  });
});

describe("alinearPorIdentidad — SIGMAN (ESF 4 / ERI 5)", () => {
  // ESF: may-26, 2025, 2024, 2023 ; ERI: may-26, may-25, 2025, 2024, 2023
  const res = {
    periodos_esf: [
      { label: "may-26", tipo: "parcial", meses: 5, anio: 2026 },
      { label: "2025", tipo: "anual", meses: 12, anio: 2025 },
      { label: "2024", tipo: "anual", meses: 12, anio: 2024 },
      { label: "2023", tipo: "anual", meses: 12, anio: 2023 },
    ],
    periodos_eri: [
      { label: "may-26", tipo: "parcial", meses: 5, anio: 2026 },
      { label: "may-25", tipo: "parcial", meses: 5, anio: 2025 },
      { label: "2025", tipo: "anual", meses: 12, anio: 2025 },
      { label: "2024", tipo: "anual", meses: 12, anio: 2024 },
      { label: "2023", tipo: "anual", meses: 12, anio: 2023 },
    ],
    data: {
      // ESF key: indexado por periodos_esf (4 valores)
      efectivo: [1033, 1080, 1352, 1950],
      // ER key: indexado por periodos_eri (5 valores)
      ventas: [2930, 2573, 7599, 9788, 9776],
    },
  };

  it("el eje son los períodos del BALANCE, orden ascendente, may-25 excluido", () => {
    const { periodos } = alinearPorIdentidad(res);
    expect(periodos.map((p) => p.label)).toEqual(["2023", "2024", "2025", "may-26"]);
    // may-25 (solo ERI) NO entra al eje
    expect(periodos.some((p) => p.label === "may-25")).toBe(false);
  });

  it("meses correctos: may-26 = 5, anuales = 12", () => {
    const { periodos } = alinearPorIdentidad(res);
    const may26 = periodos.find((p) => p.label === "may-26");
    expect(may26.meses).toBe(5);
    expect(periodos.find((p) => p.label === "2025").meses).toBe(12);
  });

  it("ESF alineado: efectivo queda en su período correcto (no corrido)", () => {
    const { D, periodos } = alinearPorIdentidad(res);
    const i26 = periodos.findIndex((p) => p.label === "may-26");
    const i25 = periodos.findIndex((p) => p.label === "2025");
    expect(D.efectivo[i26]).toBe(1033); // may-26
    expect(D.efectivo[i25]).toBe(1080); // 2025
  });

  it("ER alineado por identidad: ventas anuales caen en 2025/2024/2023 (no en may-25)", () => {
    const { D, periodos } = alinearPorIdentidad(res);
    const idx = (l) => periodos.findIndex((p) => p.label === l);
    expect(D.ventas[idx("may-26")]).toBe(2930); // parcial actual
    expect(D.ventas[idx("2025")]).toBe(7599); // anual 2025 (NO el may-25=2573)
    expect(D.ventas[idx("2024")]).toBe(9788);
    expect(D.ventas[idx("2023")]).toBe(9776);
  });
});

describe("tienePeriodosTipados", () => {
  it("detecta metadata de períodos", () => {
    expect(tienePeriodosTipados({ periodos_esf: [{}] })).toBe(true);
    expect(tienePeriodosTipados({})).toBe(false);
    expect(tienePeriodosTipados({ periodos_esf: [] })).toBe(false);
  });
});
