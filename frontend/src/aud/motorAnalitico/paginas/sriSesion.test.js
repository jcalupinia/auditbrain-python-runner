import { describe, expect, it } from "vitest";
import { MARGEN_RENOVACION_MS, SONDEO_MS, debeRenovar, formatosValidos, sesionDesdePermiso } from "./sriSesion.js";

describe("sesión de un trabajo SRI", () => {
  it("el sondeo respeta el límite de 30 peticiones por minuto del motor", () => {
    expect(60000 / SONDEO_MS).toBeLessThanOrEqual(30);
  });

  it("calcula el vencimiento desde expira_en y renueva con margen", () => {
    const s = sesionDesdePermiso({ url: "u", token: "t", expira_en: 300 }, 1000);
    expect(s).toEqual({ url: "u", token: "t", vence: 301000 });
    expect(debeRenovar(s.vence, 1000)).toBe(false);
    expect(debeRenovar(s.vence, 301000 - MARGEN_RENOVACION_MS)).toBe(true);
    expect(debeRenovar(undefined, 0)).toBe(true);
    expect(sesionDesdePermiso({ url: "u", token: "t" }, 0).vence).toBe(300000);
  });

  it("exige un formato salvo en modo rápido", () => {
    expect(formatosValidos([], false)).toBe(false);
    expect(formatosValidos([], true)).toBe(true);
    expect(formatosValidos(["XML"], false)).toBe(true);
  });
});
