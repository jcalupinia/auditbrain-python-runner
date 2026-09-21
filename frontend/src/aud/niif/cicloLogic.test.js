import { describe, expect, it } from "vitest";

import { ETAPAS, alternarProcedimiento, etapaDe, nombreEstado, procedimientosSinFuente } from "./cicloLogic";
import { STATES } from "./sitio/tools/domain.mjs";

describe("etapas de una prueba", () => {
  it("son las 9 del sitio", () => {
    expect(ETAPAS).toHaveLength(9);
  });

  it("cada uno de los 13 estados del sitio cae en una etapa, en orden", () => {
    const etapas = STATES.map(etapaDe);
    expect(etapas.every((e) => e >= 1 && e <= 8)).toBe(true);
    expect([...etapas].sort((a, b) => a - b)).toEqual(etapas);
    expect(etapaDe("APROBADO")).toBe(8);
  });

  it("nombra el estado en español legible", () => {
    expect(nombreEstado("PROGRAMA_PROPUESTO")).toBe("Programa propuesto");
    expect(nombreEstado("DOCUMENTACION_RECIBIDA")).toBe("Documentación recibida");
    expect(nombreEstado("METODOLOGIA_APROBADA")).toBe("Metodología aprobada");
    expect(nombreEstado("EN_REVISION")).toBe("En revisión");
  });
});

describe("fuentes y procedimientos", () => {
  const programa = [{ code: "VNR-01" }, { code: "VNR-02" }];
  const fuentes = [
    { category: "NIIF", verified: true, procedures: ["VNR-01"] },
    { category: "NIA", verified: false, procedures: [] },
  ];

  it("marca y desmarca un procedimiento solo en la fuente indicada", () => {
    const una = alternarProcedimiento(fuentes, 1, "VNR-02");
    expect(una[1].procedures).toEqual(["VNR-02"]);
    expect(una[0]).toBe(fuentes[0]);
    expect(alternarProcedimiento(una, 1, "VNR-02")[1].procedures).toEqual([]);
  });

  it("señala los procedimientos sin fuente verificada", () => {
    expect(procedimientosSinFuente(programa, fuentes)).toEqual(["VNR-02"]);
    // Una fuente sin verificar no cuenta aunque tenga el procedimiento.
    const conNia = alternarProcedimiento(fuentes, 1, "VNR-02");
    expect(procedimientosSinFuente(programa, conNia)).toEqual(["VNR-02"]);
    expect(procedimientosSinFuente(programa, [{ ...conNia[0] }, { ...conNia[1], verified: true }])).toEqual([]);
  });
});

import { componentesDeTexto, erroresLegibles, esTabular, mapeoSugerido } from "./cicloLogic";

describe("requerimiento y documentación", () => {
  it("convierte el texto de componentes en una lista limpia", () => {
    expect(componentesDeTexto(" Quito, Guayaquil ;Quito\n\n Cuenca")).toEqual(["Quito", "Guayaquil", "Cuenca"]);
    expect(componentesDeTexto("")).toEqual([]);
  });

  it("solo XLSX y CSV sirven como población", () => {
    expect(esTabular("mayor.XLSX")).toBe(true);
    expect(esTabular("mayor.csv")).toBe(true);
    expect(esTabular("mayor.pdf")).toBe(false);
  });

  it("sugiere el mapeo por etiqueta o código, sin tildes ni mayúsculas", () => {
    const campos = [{ key: "id", label: "Código" }, { key: "quantity", label: "Cantidad" }, { key: "unit_cost", label: "Costo unitario" }];
    expect(mapeoSugerido(["CODIGO", "Descripción", "cantidad", "Costo Unitario"], campos)).toEqual({ id: 0, quantity: 2, unit_cost: 3 });
    expect(mapeoSugerido(["x"], campos)).toEqual({});
  });

  it("resume los errores de validación con su fila", () => {
    expect(erroresLegibles({ errors: [{ row: 8, message: "Cantidad: número inválido." }] })).toEqual(["Fila 8 · Cantidad: número inválido."]);
  });
});
