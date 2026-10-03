import { describe, expect, it } from "vitest";
import {
  evidenciaTexto,
  formatValor,
  metodoEtiqueta,
  nivelClase,
  nivelEtiqueta,
  nivelNormalizado,
  qualityPct,
  resumenCampos,
  tipoEtiqueta,
} from "./logic.js";

describe("Motor de ingesta · niveles de confianza", () => {
  it("un nivel ausente o desconocido escala al más conservador (nunca oculta la duda)", () => {
    expect(nivelNormalizado("HIGH")).toBe("HIGH");
    expect(nivelNormalizado(undefined)).toBe("REVIEW_REQUIRED");
    expect(nivelNormalizado("OTRO")).toBe("REVIEW_REQUIRED");
    expect(nivelEtiqueta(undefined)).toBe("Revisar");
    expect(nivelEtiqueta("MEDIUM")).toBe("Media");
    expect(nivelClase("LOW")).toBe("ing-nivel-baja");
    expect(nivelClase("HIGH")).toBe("ing-nivel-alta");
  });
});

describe("Motor de ingesta · etiquetas", () => {
  it("traduce método de extracción y tipo de documento", () => {
    expect(metodoEtiqueta("parser")).toBe("Parser SRI");
    expect(metodoEtiqueta("ia")).toBe("IA");
    expect(metodoEtiqueta("")).toBe("—");
    expect(tipoEtiqueta("f104")).toBe("Formulario 104 · IVA");
    expect(tipoEtiqueta("mayor")).toBe("Libro Mayor");
    expect(tipoEtiqueta("")).toBe("Desconocido");
  });
});

describe("Motor de ingesta · evidencia (trazabilidad al origen)", () => {
  it("arma archivo · página · hoja · fila · celda, omitiendo lo vacío", () => {
    expect(
      evidenciaTexto({
        source_file: "f104.xlsx",
        source_page: 3,
        source_sheet: "1 Disenio",
        source_row: 12,
        source_cell: "B4",
      })
    ).toBe("f104.xlsx · p. 3 · hoja 1 Disenio · fila 12 · celda B4");
    expect(evidenciaTexto({ source_file: "doc.pdf" })).toBe("doc.pdf");
    // fila 0 es válida (ge=0 en el contrato): no debe desaparecer.
    expect(evidenciaTexto({ source_file: "d.csv", source_row: 0 })).toBe("d.csv · fila 0");
    expect(evidenciaTexto(null)).toBe("");
  });
});

describe("Motor de ingesta · valor a mostrar", () => {
  it("prefiere el normalizado y cae al crudo cuando falta", () => {
    expect(formatValor({ normalized_value: 178259.63, raw_value: "178,259.63" })).toBe("178259.63");
    expect(formatValor({ normalized_value: null, raw_value: "n/d" })).toBe("n/d");
    expect(formatValor({ normalized_value: "", raw_value: "crudo" })).toBe("crudo");
    expect(formatValor({ normalized_value: 0 })).toBe("0"); // 0 es un valor, no "vacío"
    expect(formatValor(null)).toBe("");
  });
});

describe("Motor de ingesta · resumen de campos", () => {
  it("cuenta por nivel y calcula dudosos (LOW + REVIEW_REQUIRED)", () => {
    const campos = [
      { confidence: "HIGH" },
      { confidence: "HIGH" },
      { confidence: "MEDIUM" },
      { confidence: "LOW" },
      { confidence: "REVIEW_REQUIRED" },
      { confidence: "???" }, // escala a REVIEW_REQUIRED
    ];
    const r = resumenCampos(campos);
    expect(r.total).toBe(6);
    expect(r.por.HIGH).toBe(2);
    expect(r.por.MEDIUM).toBe(1);
    expect(r.por.LOW).toBe(1);
    expect(r.por.REVIEW_REQUIRED).toBe(2);
    expect(r.dudosos).toBe(3);
    expect(r.pct_dudosos).toBeCloseTo(0.5, 5);
  });
  it("no revienta con lista vacía o indefinida", () => {
    expect(resumenCampos([]).total).toBe(0);
    expect(resumenCampos(undefined).pct_dudosos).toBe(0);
  });
});

describe("Motor de ingesta · calidad", () => {
  it("convierte quality_score 0..1 a porcentaje y acota fuera de rango", () => {
    expect(qualityPct(0.87)).toBe(87);
    expect(qualityPct(1.4)).toBe(100);
    expect(qualityPct(-0.2)).toBe(0);
    expect(qualityPct("x")).toBe(0);
  });
});
