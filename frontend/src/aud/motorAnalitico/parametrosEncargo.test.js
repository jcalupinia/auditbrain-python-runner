import { describe, expect, it } from "vitest";
import { CAMPOS, INICIALES, aEnvio, validar } from "./parametrosEncargo.js";

const LLENO = {
  ejercicio_inicio: "2026-01-01", ejercicio_fin: "2026-12-31",
  materialidad: "50000.00", materialidad_ejecucion: "37500.00",
  umbral_insignificante: "2500.00", umbral_aprobacion: "5000.00",
  feriados: "2026-01-01, 2026-05-01", hora_inicio: "8", hora_fin: "18",
  error_tolerable: "37500.00", confianza: "95", semilla: "20260531",
  fecha_registro_es_contable: false,
};

describe("parámetros del encargo", () => {
  it("tiene los 13 campos del bloque U y arranca vacío", () => {
    expect(CAMPOS.length).toBe(13);
    expect(INICIALES.materialidad).toBe("");
    expect(INICIALES.fecha_registro_es_contable).toBe(false);
  });

  it("no acepta campos vacíos", () => {
    const errores = validar(INICIALES);
    expect(errores.materialidad).toBe("obligatorio");
    expect(errores.feriados).toBeUndefined();            // puede ir vacío
    expect(errores.fecha_registro_es_contable).toBeUndefined();
  });

  it("rechaza importes con separador de miles", () => {
    expect(validar({ ...LLENO, materialidad: "50.000" }).materialidad)
      .toBe("escríbelo sin separador de miles: 50000 o 50000,50");
  });

  it("aplica las reglas cruzadas de las NIA", () => {
    expect(validar({ ...LLENO, materialidad_ejecucion: "60000.00" }).materialidad_ejecucion)
      .toBe("no puede superar la materialidad global");
    expect(validar({ ...LLENO, umbral_insignificante: "37500.00" }).umbral_insignificante)
      .toBe("debe ser menor que la materialidad de ejecución");
    expect(validar({ ...LLENO, error_tolerable: "40000.00" }).error_tolerable)
      .toBe("no puede superar la materialidad de ejecución");
    expect(validar({ ...LLENO, ejercicio_fin: "2025-12-31" }).ejercicio_fin)
      .toBe("debe ser posterior al inicio del ejercicio");
    expect(validar({ ...LLENO, hora_fin: "8" }).hora_fin)
      .toBe("debe ser mayor que la hora de inicio");
    expect(validar({ ...LLENO, feriados: "2027-01-01" }).feriados)
      .toBe("hay feriados fuera del ejercicio");
    expect(validar({ ...LLENO, confianza: "97" }).confianza).toBe("usa 80, 90, 95 o 99");
    expect(validar({ ...LLENO, semilla: "abc" }).semilla).toBe("debe ser un número entero");
  });

  it("un formulario correcto no tiene errores", () => {
    expect(validar(LLENO)).toEqual({});
  });

  it("serializa al formato que espera el motor", () => {
    expect(aEnvio(LLENO)).toEqual({
      ejercicio_inicio: "2026-01-01", ejercicio_fin: "2026-12-31",
      materialidad: "50000.00", materialidad_ejecucion: "37500.00",
      umbral_insignificante: "2500.00", umbral_aprobacion: "5000.00",
      feriados: ["2026-01-01", "2026-05-01"], hora_inicio: 8, hora_fin: 18,
      error_tolerable: "37500.00", confianza: 95, semilla: 20260531,
      fecha_registro_es_contable: false,
    });
  });
});
