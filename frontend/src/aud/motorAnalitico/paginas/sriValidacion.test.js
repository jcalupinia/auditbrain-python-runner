import { describe, expect, it } from "vitest";
import { avisoXmlEmitidos, fechaFinPeriodo, validarEstablecimiento, validarPuntoEmision } from "./sriValidacion.js";

describe("validaciones de descarga (paridad con la app de escritorio)", () => {
  it("establecimiento: Todos o tres dígitos", () => {
    expect(validarEstablecimiento("")).toEqual({ ok: true, valor: "Todos" });
    expect(validarEstablecimiento(" todos ")).toEqual({ ok: true, valor: "Todos" });
    expect(validarEstablecimiento("001")).toEqual({ ok: true, valor: "001" });
    expect(validarEstablecimiento("1").ok).toBe(false);
    expect(validarEstablecimiento("00a").ok).toBe(false);
  });

  it("punto de emisión: dígitos, obligatorio con establecimiento concreto", () => {
    expect(validarPuntoEmision("", "Todos")).toEqual({ ok: true, valor: "" });
    expect(validarPuntoEmision("0a1", "Todos")).toEqual({ ok: true, valor: "01" });
    expect(validarPuntoEmision("", "001").ok).toBe(false);
    expect(validarPuntoEmision("002", "001")).toEqual({ ok: true, valor: "002" });
  });

  it("fecha fin del período según el modo", () => {
    expect(fechaFinPeriodo({ modo_fecha: "Mes", anio: 2026, mes: 2, dia: 0 })).toEqual(new Date(2026, 1, 28));
    expect(fechaFinPeriodo({ modo_fecha: "Mes", anio: 2026, mes: 2, dia: 10 })).toEqual(new Date(2026, 1, 10));
    expect(fechaFinPeriodo({ modo_fecha: "Rango de meses", anio: 2026, mes: 1, mes_fin: 4 })).toEqual(new Date(2026, 3, 30));
    expect(fechaFinPeriodo({ modo_fecha: "Año completo", anio: 2025 })).toEqual(new Date(2025, 11, 31));
  });

  it("aviso de 30 días para XML de Emitidos autorizados", () => {
    const hoy = new Date(2026, 9, 21);
    const viejo = { modo_fecha: "Mes", anio: 2026, mes: 3, dia: 0 };
    const reciente = { modo_fecha: "Mes", anio: 2026, mes: 10, dia: 0 };
    const base = { origen: "Emitidos", estado_emitidos: "Autorizados", modo_rapido: false };

    const conPdf = avisoXmlEmitidos({ ...base, formatos: ["XML", "PDF"], periodo: viejo }, hoy);
    expect(conPdf.continuar).toBe(true);
    expect(conPdf.formatos).toEqual(["PDF"]);
    expect(conPdf.mensaje).toContain("solo con PDF");

    const soloXml = avisoXmlEmitidos({ ...base, formatos: ["XML"], periodo: viejo }, hoy);
    expect(soloXml.continuar).toBe(false);

    expect(avisoXmlEmitidos({ ...base, formatos: ["XML"], periodo: reciente }, hoy)).toBeNull();
    expect(avisoXmlEmitidos({ ...base, origen: "Recibidos", formatos: ["XML"], periodo: viejo }, hoy)).toBeNull();
    expect(avisoXmlEmitidos({ ...base, estado_emitidos: "No autorizados", formatos: ["XML"], periodo: viejo }, hoy)).toBeNull();
    expect(avisoXmlEmitidos({ ...base, formatos: ["PDF"], periodo: viejo }, hoy)).toBeNull();
    expect(avisoXmlEmitidos({ ...base, formatos: ["XML"], modo_rapido: true, periodo: viejo }, hoy)).toBeNull();
  });
});
