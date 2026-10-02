import { describe, it, expect } from "vitest";

import {
  etiquetaSistema,
  comentarioValido,
  puedePreguntar,
  lineasDeConversacion,
  cuentaComentarios,
} from "./consolaLogic.js";

describe("etiquetaSistema", () => {
  it("traduce acciones conocidas y agrega el estado nuevo", () => {
    expect(etiquetaSistema({ accion: "execute", estado_nuevo: "PRUEBA_EJECUTADA" }))
      .toBe("Prueba ejecutada → PRUEBA_EJECUTADA");
    expect(etiquetaSistema({ accion: "create" })).toBe("Prueba creada");
  });
  it("acción desconocida cae a la acción cruda", () => {
    expect(etiquetaSistema({ accion: "algo_raro" })).toBe("algo_raro");
    expect(etiquetaSistema({})).toBe("Evento");
  });
});

describe("comentarioValido", () => {
  it("rechaza vacío y acepta texto normal", () => {
    expect(comentarioValido("   ")).toBe(false);
    expect(comentarioValido("")).toBe(false);
    expect(comentarioValido("hola")).toBe(true);
  });
  it("rechaza texto sobre el límite de 8000", () => {
    expect(comentarioValido("a".repeat(8001))).toBe(false);
    expect(comentarioValido("a".repeat(8000))).toBe(true);
  });
});

describe("puedePreguntar", () => {
  it("requiere proveedor disponible y texto válido", () => {
    expect(puedePreguntar(true, "algo")).toBe(true);
    expect(puedePreguntar(false, "algo")).toBe(false);
    expect(puedePreguntar(true, "  ")).toBe(false);
  });
});

describe("lineasDeConversacion", () => {
  const conv = [
    { id: 1, tipo: "sistema", accion: "create", estado_nuevo: "PRUEBA_SELECCIONADA", actor: "ana@x" },
    { id: 2, tipo: "comentario", es_asistente: false, actor: "ana@x", texto: "¿por qué?" },
    { id: 3, tipo: "comentario", es_asistente: true, actor: "AUDIT-IA · modelo", texto: "porque…" },
  ];
  it("resuelve tipo, autor y texto de cada evento", () => {
    const l = lineasDeConversacion(conv);
    expect(l[0]).toMatchObject({ tipo: "sistema", texto: "Prueba creada → PRUEBA_SELECCIONADA" });
    expect(l[1]).toMatchObject({ tipo: "comentario", esAsistente: false, texto: "¿por qué?" });
    expect(l[2]).toMatchObject({ tipo: "comentario", esAsistente: true, texto: "porque…" });
  });
  it("tolera lista vacía o nula", () => {
    expect(lineasDeConversacion(null)).toEqual([]);
  });
});

describe("cuentaComentarios", () => {
  it("cuenta solo los comentarios", () => {
    expect(cuentaComentarios([
      { tipo: "sistema" }, { tipo: "comentario" }, { tipo: "comentario" },
    ])).toBe(2);
  });
});
