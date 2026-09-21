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
