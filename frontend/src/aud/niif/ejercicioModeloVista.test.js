import { describe, it, expect } from "vitest";
import { abrirTodoPorDefecto, anclaPaso, PROCESADORES_ABRIR_TODO } from "./ejercicioModeloVista";

describe("ejercicioModeloVista", () => {
  it("Planificación abre todas las secciones al cargar", () => {
    expect(abrirTodoPorDefecto("planificacion_nia")).toBe(true);
    expect(PROCESADORES_ABRIR_TODO).toContain("planificacion_nia");
  });

  it("las demás herramientas arrancan por pasos", () => {
    expect(abrirTodoPorDefecto("cxc_cartera")).toBe(false);
    expect(abrirTodoPorDefecto(undefined)).toBe(false);
    expect(abrirTodoPorDefecto("")).toBe(false);
  });

  it("el ancla del paso es estable", () => {
    expect(anclaPaso(6)).toBe("em-paso-6");
    expect(anclaPaso(1)).toBe("em-paso-1");
  });
});
