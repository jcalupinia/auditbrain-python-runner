import { describe, it, expect } from "vitest";

import { esPlanificacion, resumen, hayContenido, formatoMonto } from "./pruebasSugeridasLogic.js";

describe("esPlanificacion", () => {
  it("detecta el procesador de planificación", () => {
    expect(esPlanificacion({ definicion: { processor: "planificacion_nia" } })).toBe(true);
    expect(esPlanificacion({ definicion: { processor: "arrendamientos" } })).toBe(false);
    expect(esPlanificacion({ definicion: {} })).toBe(false);
    expect(esPlanificacion(null)).toBe(false);
  });
});

const DATA = {
  pruebas: [
    { prueba_id: "ingresos_contratos", con_riesgo: true, n_cuentas: 2, saldo: 4878900 },
    { prueba_id: "arrendamientos", con_riesgo: false, n_cuentas: 3, saldo: 194900 },
  ],
  sin_prueba: [{ herramienta: "Motor de auditoría analítica", n_cuentas: 1 }],
  cuentas_a_revisar: 6,
};

describe("resumen", () => {
  it("cuenta pruebas, riesgo, cuentas y áreas sin prueba", () => {
    expect(resumen(DATA)).toEqual({ nPruebas: 2, nConRiesgo: 1, cuentas: 6, nSinPrueba: 1 });
  });
  it("tolera data vacía", () => {
    expect(resumen({})).toEqual({ nPruebas: 0, nConRiesgo: 0, cuentas: 0, nSinPrueba: 0 });
  });
});

describe("hayContenido", () => {
  it("true si hay pruebas o áreas sin prueba", () => {
    expect(hayContenido(DATA)).toBe(true);
    expect(hayContenido({ pruebas: [], sin_prueba: [] })).toBe(false);
  });
});

describe("formatoMonto", () => {
  it("agrupa miles y fija dos decimales", () => {
    expect(formatoMonto(4878900)).toBe("4,878,900.00");
    expect(formatoMonto(194900.5)).toBe("194,900.50");
    expect(formatoMonto(-1234.5)).toBe("-1,234.50");
    expect(formatoMonto(0)).toBe("0.00");
  });
  it("no numérico → guion", () => {
    expect(formatoMonto(null)).toBe("—");
    expect(formatoMonto("x")).toBe("—");
  });
});
