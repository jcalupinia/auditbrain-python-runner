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
