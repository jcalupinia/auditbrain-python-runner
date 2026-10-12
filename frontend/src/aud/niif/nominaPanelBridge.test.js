// Puente postMessage del panel de nómina → VistaProceso (el Command Center). Verifica que cada
// acción del panel (descargar / procesar / encerar) se despacha a su handler real, que encerar
// NO borra en silencio (solo dispara la confirmación) y que un mensaje ajeno no hace nada.
import { describe, expect, it, vi } from "vitest";

import { MENSAJES_NOMINA, despacharMensajeNomina } from "./nominaPanelBridge";

describe("nominaPanelBridge · despacho de acciones del panel", () => {
  const handlers = () => ({ descargar: vi.fn(), procesar: vi.fn(), encerar: vi.fn() });

  it("procesar: llama al flujo de procesar (y solo a ese)", () => {
    const h = handlers();
    expect(despacharMensajeNomina({ type: MENSAJES_NOMINA.PROCESAR }, h)).toBe("procesar");
    expect(h.procesar).toHaveBeenCalledTimes(1);
    expect(h.encerar).not.toHaveBeenCalled();
    expect(h.descargar).not.toHaveBeenCalled();
  });

  it("encerar: dispara la confirmación (handler encerar), NO borra directo", () => {
    const h = handlers();
    expect(despacharMensajeNomina({ type: MENSAJES_NOMINA.ENCERAR }, h)).toBe("encerar");
    expect(h.encerar).toHaveBeenCalledTimes(1);
    // No se procesa ni se descarga nada como efecto colateral del encerado.
    expect(h.procesar).not.toHaveBeenCalled();
    expect(h.descargar).not.toHaveBeenCalled();
  });

  it("descargar: pasa el nombre de la cédula como string", () => {
    const h = handlers();
    expect(despacharMensajeNomina({ type: MENSAJES_NOMINA.DESCARGAR, cedula: "DO-0_Programa.xlsx" }, h)).toBe("descargar");
    expect(h.descargar).toHaveBeenCalledWith("DO-0_Programa.xlsx");
    expect(h.procesar).not.toHaveBeenCalled();
    expect(h.encerar).not.toHaveBeenCalled();
  });

  it("descargar sin cédula no hace nada", () => {
    const h = handlers();
    expect(despacharMensajeNomina({ type: MENSAJES_NOMINA.DESCARGAR }, h)).toBeNull();
    expect(h.descargar).not.toHaveBeenCalled();
  });

  it("mensaje ajeno o sin type: null, ningún handler", () => {
    const h = handlers();
    expect(despacharMensajeNomina({ type: "otro:mensaje" }, h)).toBeNull();
    expect(despacharMensajeNomina({ cedula: "x" }, h)).toBeNull();
    expect(despacharMensajeNomina(null, h)).toBeNull();
    expect(despacharMensajeNomina(undefined, h)).toBeNull();
    expect(h.descargar).not.toHaveBeenCalled();
    expect(h.procesar).not.toHaveBeenCalled();
    expect(h.encerar).not.toHaveBeenCalled();
  });

  it("handlers opcionales: no revienta si falta uno", () => {
    expect(despacharMensajeNomina({ type: MENSAJES_NOMINA.PROCESAR }, {})).toBe("procesar");
    expect(despacharMensajeNomina({ type: MENSAJES_NOMINA.ENCERAR })).toBe("encerar");
  });
});
