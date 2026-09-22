import { describe, expect, it } from "vitest";
import { ErrorMotor } from "./clienteMotor.js";
import {
  dinero, filasBandeja, mensajeError, montoVisible, paginas, resumenSeveridad, terminado,
} from "./bandeja.js";

// Forma real de motor/nucleo.py::Excepcion.a_dict() (repo motor-auditoria-analitica@sp2a-trabajos).
const excepcionReal = {
  regla_id: "GAS-006",
  severidad: "P0",
  entidad_tipo: "asiento",
  entidad_id: "AST-000123",
  descripcion: "Asiento manual contra cuenta de ingreso fuera de patrón",
  evidencia: { cuenta: "4101001", monto: "1500.00" },
  monto_expuesto: "1500.00",
  reglas_concurrentes: ["GAS-006", "GAS-010"],
  nia: "NIA 240",
  hash: "a1b2c3d4e5f6",
};

// Forma real de GET /trabajos/{id}/excepciones (servicio/trabajos.py::paginar()).
const respuestaReal = {
  total: 1,
  pagina: 1,
  tam: 50,
  excepciones: [excepcionReal, { ...excepcionReal, regla_id: "GAS-010", monto_expuesto: "0.00", hash: "z9y8" }],
};

describe("bandeja", () => {
  it("sabe cuándo dejar de consultar", () => {
    expect(terminado("en_cola")).toBe(false);
    expect(terminado("procesando")).toBe(false);
    expect(terminado("listo")).toBe(true);
    expect(terminado("error")).toBe(true);
  });
  it("ordena el resumen P0→INFO y completa ceros", () => {
    expect(resumenSeveridad({ P2: 402, P0: 17, P1: 22 }))
      .toEqual([["P0", 17], ["P1", 22], ["P2", 402], ["INFO", 0]]);
  });
  it("cuenta páginas", () => {
    expect(paginas(0, 50)).toBe(1);
    expect(paginas(402, 50)).toBe(9);
  });
  it("formatea dinero en es-EC desde texto", () => {
    expect(dinero("420000.00")).toBe("420.000,00");
    expect(dinero("0.00")).toBe("0,00");
  });
  it("dinero devuelve null si está vacío o no es numérico (nunca inventa 0,00)", () => {
    expect(dinero(null)).toBe(null);
    expect(dinero(undefined)).toBe(null);
    expect(dinero("")).toBe(null);
    expect(dinero("  ")).toBe(null);
    expect(dinero("no-es-un-monto")).toBe(null);
  });
  it("montoVisible marca sin datos cuando dinero() es null", () => {
    expect(montoVisible("1500.00")).toEqual({ sinDatos: false, texto: "1.500,00" });
    expect(montoVisible(null)).toEqual({ sinDatos: true, texto: "sin datos" });
    expect(montoVisible(undefined)).toEqual({ sinDatos: true, texto: "sin datos" });
  });

  it("filasBandeja lee `excepciones` (no `items`) y arma las columnas reales", () => {
    const filas = filasBandeja(respuestaReal);
    expect(filas).toHaveLength(2);
    expect(filas[0]).toEqual({
      hash: "a1b2c3d4e5f6",
      severidad: "P0",
      reglaId: "GAS-006",
      nia: "NIA 240",
      entidad: "asiento AST-000123",
      descripcion: "Asiento manual contra cuenta de ingreso fuera de patrón",
      monto: { sinDatos: false, texto: "1.500,00" },
      reglasConcurrentes: ["GAS-006", "GAS-010"],
      evidencia: { cuenta: "4101001", monto: "1500.00" },
    });
  });
  it("filasBandeja no inventa un monto cuando monto_expuesto es 0.00: lo muestra igual (es numérico)", () => {
    expect(filasBandeja(respuestaReal)[1].monto).toEqual({ sinDatos: false, texto: "0,00" });
  });
  it("filasBandeja tolera una respuesta vacía o sin campo excepciones", () => {
    expect(filasBandeja({ total: 0, excepciones: [] })).toEqual([]);
    expect(filasBandeja({})).toEqual([]);
  });

  it("mensajeError distingue el 429 de cupo del 429 de ritmo por el texto del backend", () => {
    expect(mensajeError(new ErrorMotor(429, "ya tienes 3 trabajos en curso")))
      .toBe("Ya tienes 3 trabajos en curso: espera a que terminen.");
    expect(mensajeError(new ErrorMotor(429, "demasiadas solicitudes")))
      .toBe("Demasiadas consultas seguidas: espera un minuto.");
  });
  it("mensajeError informa el AbortError y cae al mensaje del backend en otros casos", () => {
    const abortado = new DOMException("abortado", "AbortError");
    expect(mensajeError(abortado)).toBe("El motor no respondió a tiempo.");
    expect(mensajeError(new ErrorMotor(404, "trabajo no encontrado"))).toBe("trabajo no encontrado");
    expect(mensajeError(new Error("boom"))).toBe("boom");
  });
});
