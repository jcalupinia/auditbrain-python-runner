import { describe, it, expect } from "vitest";

import {
  accionInline, claseMensaje, esPlanificacion, nombreDe, puedeSubirInline, requerimientosPendientes,
} from "./consolaChatVista";

describe("consolaChatVista", () => {
  it("solo la planificación NIA tiene consola-chat", () => {
    expect(esPlanificacion({ definicion: { processor: "planificacion_nia" } })).toBe(true);
    expect(esPlanificacion({ definicion: { processor: "cxc_cartera" } })).toBe(false);
    expect(esPlanificacion({ definicion: {} })).toBe(false);
  });

  it("clase y nombre por emisor", () => {
    expect(claseMensaje("agente")).toBe("nf-chat-agente");
    expect(claseMensaje("auditor")).toBe("nf-chat-aud");
    expect(nombreDe("preparador")).toBe("Preparador");
    expect(nombreDe("agente")).toBe("Asistente");
  });

  it("se puede subir inline solo con requerimiento aprobado y requests", () => {
    expect(puedeSubirInline({ estado: "REQUERIMIENTO_APROBADO", registro: { requests: [{ id: "RQ-001" }] } })).toBe(true);
    expect(puedeSubirInline({ estado: "DOCUMENTACION_RECIBIDA", registro: { requests: [{ id: "RQ-001" }] } })).toBe(true);
    expect(puedeSubirInline({ estado: "PRUEBA_SELECCIONADA", registro: { requests: [] } })).toBe(false);
    expect(puedeSubirInline({ estado: "REQUERIMIENTO_APROBADO", registro: {} })).toBe(false);
  });

  it("requerimientos pendientes = obligatorios no completos", () => {
    const prueba = { registro: { requests: [
      { id: "RQ-001", required: true }, { id: "RQ-002", required: true }, { id: "RQ-003", required: false },
    ] } };
    const cobertura = [{ id: "RQ-001", complete: true }, { id: "RQ-002", complete: false }, { id: "RQ-003", complete: false }];
    expect(requerimientosPendientes(prueba, cobertura).map((r) => r.id)).toEqual(["RQ-002"]);
  });

  it("qué acciones se resuelven dentro del chat", () => {
    expect(accionInline("subir")).toBe(true);
    expect(accionInline("revisar")).toBe(true);
    expect(accionInline("aprobar")).toBe(true);
    expect(accionInline("procesar")).toBe(false);
    expect(accionInline("enviar")).toBe(false);
  });
});
