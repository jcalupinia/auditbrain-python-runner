import { describe, expect, it } from "vitest";

import { EJEMPLOS_REQUERIMIENTOS, ejemploDe, formatosTexto } from "./ejemplosRequerimientos";

describe("ejemploDe · qué ofrece la flecha del requerimiento", () => {
  const req = (extra) => ({ id: "RQ-001", formats: ["xlsx", "csv"], required: true, ...extra });

  it("descarga el ejemplo estático cuando el manifiesto lo tiene", () => {
    const r = ejemploDe("perdidas_incurridas_s11", req(), undefined, "/");
    expect(r.tipo).toBe("ejemplo");
    expect(r.archivo).toBe("RQ-001_cartera_2025.xlsx");
    expect(r.url).toBe("/ejemplos/perdidas_incurridas_s11/RQ-001_cartera_2025.xlsx");
  });

  it("cae al modelo en blanco cuando no hay ejemplo pero el requerimiento alimenta el cálculo", () => {
    const r = ejemploDe("otra_herramienta", req({ dataset: "a3" }));
    expect(r).toEqual({ tipo: "modelo" });
  });

  it("no muestra flecha (null) cuando no hay ejemplo ni dataset", () => {
    expect(ejemploDe("otra_herramienta", req({ id: "RQ-009" }))).toBeNull();
    expect(ejemploDe(undefined, req())).toBeNull();
    expect(ejemploDe("x", null)).toBeNull();
  });

  it("respeta el prefijo público (base) al armar la URL", () => {
    const r = ejemploDe("perdidas_incurridas_s11", req(), undefined, "/app/");
    expect(r.url).toBe("/app/ejemplos/perdidas_incurridas_s11/RQ-001_cartera_2025.xlsx");
  });
});

describe("formatosTexto", () => {
  it("pone los formatos en mayúsculas separados por · ", () => {
    expect(formatosTexto({ formats: ["xlsx", "csv"] })).toBe("XLSX · CSV");
    expect(formatosTexto({ formats: ["pdf", "docx"] })).toBe("PDF · DOCX");
  });
  it("tolera requerimientos sin formatos", () => {
    expect(formatosTexto({})).toBe("");
    expect(formatosTexto(null)).toBe("");
  });
});

describe("manifiesto de pérdidas incurridas", () => {
  it("mapea los 8 requerimientos (RQ-001..RQ-008)", () => {
    const m = EJEMPLOS_REQUERIMIENTOS.perdidas_incurridas_s11;
    for (let i = 1; i <= 8; i++) expect(m[`RQ-00${i}`]).toBeTruthy();
    expect(m["RQ-007"]).toMatch(/\.docx$/);
    expect(m["RQ-001"]).toMatch(/\.xlsx$/);
  });
});
