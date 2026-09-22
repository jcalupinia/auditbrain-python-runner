import { describe, expect, it } from "vitest";
import { dinero, paginas, resumenSeveridad, terminado } from "./bandeja.js";

describe("bandeja", () => {
  it("sabe cuándo dejar de consultar", () => {
    expect(terminado("en_cola")).toBe(false);
    expect(terminado("procesando")).toBe(false);
    expect(terminado("listo")).toBe(true);
    expect(terminado("error")).toBe(true);
  });
  it("ordena el resumen P0→INFO y completa ceros", () => {
    expect(resumenSeveridad({ P2: 402, P0: 17, P1: 22 }))
      .toEqual([["P0", 17], ["P1", 22], ["P2", 402], ["INFO", 0]]);
  });
  it("cuenta páginas", () => {
    expect(paginas(0, 50)).toBe(1);
    expect(paginas(402, 50)).toBe(9);
  });
  it("formatea dinero en es-EC desde texto", () => {
    expect(dinero("420000.00")).toBe("420.000,00");
  });
});
