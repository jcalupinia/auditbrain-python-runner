import { describe, expect, it } from "vitest";

import { PROCEDIMIENTOS, SUGERENCIA_CAJA_BANCOS, TEMAS, miIndependencia, resumenRegistros } from "./registroLogic";

describe("resumen de los registros del encargo", () => {
  it("sin registros todo está pendiente", () => {
    const r = resumenRegistros(null);
    expect(r.map((x) => x.hecho)).toEqual([false, false, false, false, false, false, false, true]);
    expect(r[0].detalle).toBe("Nadie ha confirmado todavía");
  });

  it("una amenaza sin salvaguarda y la falta del socio en la discusión quedan a la vista", () => {
    const r = resumenRegistros({
      registros: {
        equipo: [
          { integrante: "A", rol: "Socio", amenazas: "", salvaguardas: "" },
          { integrante: "B", rol: "Asistente", amenazas: "Acciones del cliente", salvaguardas: "" },
        ],
        asistencia: [{ integrante: "B", rol: "Asistente", fecha: "2025-10-10" }],
        carta: { actor: "A", fecha: "2025-09-05", detalle: "Sin acceso a sucursal" },
        comunicacion: { actor: "A", fecha: "2025-10-20", detalle: "Correo" },
      },
    });
    const k = Object.fromEntries(r.map((x) => [x.clave, x]));
    expect(k.independencia).toMatchObject({ hecho: false, detalle: "2 integrante(s) · 1 con amenaza sin salvaguarda" });
    expect(k.asistencia).toMatchObject({ hecho: false, detalle: "1 asistente(s) · falta el socio" });
    expect(k.carta.detalle).toBe("Firmada el 2025-09-05 · con limitaciones");
    expect(k.comunicacion).toMatchObject({ hecho: true, detalle: "Correo · 2025-10-20" });
    expect(k.aceptacion.hecho).toBe(false);
  });

  it("mi independencia es la última vigente del usuario", () => {
    const regs = [
      { tipo: "independencia", actor: "yo", rol: "Senior" },
      { tipo: "independencia", actor: "otro", rol: "Socio" },
      { tipo: "asistencia", actor: "yo", rol: "Senior" },
    ];
    expect(miIndependencia(regs, "yo").rol).toBe("Senior");
    expect(miIndependencia(regs, "nadie")).toBeNull();
  });
});

describe("indagaciones y consultas", () => {
  it("una consulta abierta queda a la vista porque bloquea la aprobación", () => {
    const r = resumenRegistros({
      registros: {
        equipo: [], asistencia: [],
        indagaciones: [{ tema: "Partes relacionadas", resumen: "x" }],
        consultas: [{ tema: "Litigio", estado: "Abierta" }, { tema: "Otra", estado: "Resuelta" }],
      },
    });
    const k = Object.fromEntries(r.map((x) => [x.clave, x]));
    expect(k.indagaciones).toMatchObject({ hecho: true, detalle: "1 registrada(s)" });
    expect(k.consultas).toMatchObject({ hecho: false, detalle: "1 abierta(s): bloquean la aprobación" });
  });
});

describe("sugerencia de indagación de Caja y Bancos", () => {
  it("usa un tema y un procedimiento válidos y referencia el RQ-001", () => {
    expect(TEMAS).toContain(SUGERENCIA_CAJA_BANCOS.tema);
    expect(PROCEDIMIENTOS).toContain(SUGERENCIA_CAJA_BANCOS.procedimiento);
    expect(SUGERENCIA_CAJA_BANCOS.resumen).toContain("RQ-001");
    // La longitud supera el mínimo que exige el botón «Registrar indagación» (>= 10).
    expect(SUGERENCIA_CAJA_BANCOS.resumen.trim().length).toBeGreaterThan(10);
  });
});

describe("enfoque por ciclo", () => {
  it("cuenta los ciclos que el socio confirmó", () => {
    const r = resumenRegistros({ registros: { equipo: [], asistencia: [], enfoque: [{ ciclo: "Inventarios y costo de ventas", decision: "Sustantivo" }] } });
    expect(r.find((x) => x.clave === "enfoque")).toMatchObject({ hecho: false, detalle: "1 de 7 ciclos confirmados" });
  });
});
