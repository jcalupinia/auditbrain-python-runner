import { describe, expect, it } from "vitest";
import { ESTADOS_EMITIDOS, TIPOS_POR_ORIGEN, tipoValido, tiposDe } from "./sriOpciones.js";

// Paridad con la app de escritorio (aplicacion.py): el portal del SRI no tiene
// la opción "Todos" ni en tipo ni en estado; ofrecerla hacía fallar Recibidos.
describe("opciones del robot SRI", () => {
  it("replica las listas de tipo por origen de la app de escritorio", () => {
    expect(TIPOS_POR_ORIGEN.Recibidos).toEqual([
      "Facturas", "Retenciones", "Notas de crédito", "Notas de débito", "Liquidación de compra",
    ]);
    expect(TIPOS_POR_ORIGEN.Emitidos).toEqual([
      "Facturas", "Liquidación de compra", "Retenciones", "Notas de crédito", "Notas de débito", "Guía de remisión",
    ]);
  });

  it("no ofrece 'Todos' ni 'Liquidaciones' (no existen en el portal)", () => {
    for (const lista of Object.values(TIPOS_POR_ORIGEN)) {
      expect(lista).not.toContain("Todos");
      expect(lista).not.toContain("Liquidaciones");
    }
    expect(ESTADOS_EMITIDOS).toEqual(["Autorizados", "No autorizados"]);
  });

  it("al cambiar de origen conserva el tipo si sigue siendo válido", () => {
    expect(tipoValido("Emitidos", "Retenciones")).toBe("Retenciones");
    expect(tipoValido("Recibidos", "Guía de remisión")).toBe("Facturas");
    expect(tiposDe("otro")).toBe(TIPOS_POR_ORIGEN.Recibidos);
  });
});
