import { describe, expect, it } from "vitest";
import { abrePruebasEncargo } from "./ToolCatalog.jsx";

describe("catálogo AUD", () => {
  it("abre en Pruebas del encargo las fichas y las herramientas del catálogo", () => {
    expect(abrePruebasEncargo("ficha:12")).toBe(true);
    expect(abrePruebasEncargo("proc:efectivo_equivalentes")).toBe(true);
    expect(abrePruebasEncargo("AUD.MOTOR_BALANCES")).toBe(false);
    expect(abrePruebasEncargo(null)).toBe(false);
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
