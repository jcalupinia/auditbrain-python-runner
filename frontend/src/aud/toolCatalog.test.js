import { describe, expect, it } from "vitest";
import { abrePruebasEncargo } from "./ToolCatalog.jsx";
import { CATEGORIES } from "./catalog.js";
import { PAGINAS } from "./motorAnalitico/paginas.js";

describe("catálogo AUD", () => {
  it("abre en Pruebas del encargo las fichas y las herramientas del catálogo", () => {
    expect(abrePruebasEncargo("ficha:12")).toBe(true);
    expect(abrePruebasEncargo("proc:efectivo_equivalentes")).toBe(true);
    expect(abrePruebasEncargo("AUD.MOTOR_BALANCES")).toBe(false);
    expect(abrePruebasEncargo(null)).toBe(false);
  });
});

describe("Motor de auditoría analítica", () => {
  it("está en el catálogo junto al Motor de balances", () => {
    const ids = CATEGORIES.map((c) => c.id);
    expect(ids.indexOf("MOTOR_ANALITICO")).toBe(ids.indexOf("MOTOR_BALANCES") + 1);
    expect(CATEGORIES.find((c) => c.id === "MOTOR_ANALITICO").tools[0].id).toBe("AUD.MOTOR_ANALITICO");
    expect(abrePruebasEncargo("AUD.MOTOR_ANALITICO")).toBe(false);
  });

  it("tiene las 10 páginas del lienzo y solo Mayores es operativa", () => {
    expect(PAGINAS.map((p) => p.id)).toEqual(
      ["portada", "mayores", "estados", "bases", "sri", "niif", "muestras", "reportes", "agentes", "ruta"]);
    expect(PAGINAS.filter((p) => p.operativa).map((p) => p.id)).toEqual(["mayores"]);
  });
});

import { saldoMayor } from "./niif/CicloVista.jsx";
describe("saldo según el mayor", () => {
  it("acepta coma decimal y separador de miles", () => {
    expect(saldoMayor("125.000,50")).toBe("125000.50");
    expect(saldoMayor("125000.50")).toBe("125000.50");
    expect(saldoMayor(" 470,00 ")).toBe("470.00");
    expect(saldoMayor("")).toBe("");
  });
});
