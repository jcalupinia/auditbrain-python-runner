import { describe, expect, it } from "vitest";
import { CAMPOS, INICIALES, aEnvio, resumenErrores, validar } from "./parametrosEncargo.js";

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
    expect(validar({ ...LLENO, hora_fin: "8" }).hora_inicio) // se marca en hora_inicio (espejo del motor)
      .toBe("debe ser anterior a la hora de fin");
    expect(validar({ ...LLENO, feriados: "2027-01-01" }).feriados)
      .toBe("hay feriados fuera del ejercicio");
    expect(validar({ ...LLENO, confianza: "97" }).confianza).toBe("usa 80, 90, 95 o 99");
    expect(validar({ ...LLENO, semilla: "abc" }).semilla).toBe("debe ser un número entero");
  });

  // Espejo de motor/parametros.py::leer_parametros (motor-auditoria-analitica@main).
  it("las horas deben estar en el rango 0-23 (motor/parametros.py)", () => {
    expect(validar({ ...LLENO, hora_inicio: "24" }).hora_inicio).toBe("debe estar entre 0 y 23");
    expect(validar({ ...LLENO, hora_inicio: "-1" }).hora_inicio).toBe("debe estar entre 0 y 23");
    expect(validar({ ...LLENO, hora_fin: "24" }).hora_fin).toBe("debe estar entre 0 y 23");
  });

  it("hora_inicio >= hora_fin se marca en hora_inicio, como el motor", () => {
    const errores = validar({ ...LLENO, hora_fin: "8" }); // hora_inicio también es "8"
    expect(errores.hora_inicio).toBe("debe ser anterior a la hora de fin");
    expect(errores.hora_fin).toBeUndefined();
  });

  it("materialidad y umbral_aprobacion deben ser mayores que cero (motor/parametros.py)", () => {
    expect(validar({ ...LLENO, materialidad: "0" }).materialidad).toBe("debe ser mayor que cero");
    expect(validar({ ...LLENO, materialidad: "-100" }).materialidad).toBe("debe ser mayor que cero");
    expect(validar({ ...LLENO, umbral_aprobacion: "0" }).umbral_aprobacion).toBe("debe ser mayor que cero");
  });

  it("rechaza fechas con formato válido pero de calendario inexistente", () => {
    expect(validar({ ...LLENO, ejercicio_inicio: "2026-02-30" }).ejercicio_inicio).toBe("fecha inválida");
    expect(validar({ ...LLENO, feriados: "2026-02-30" }).feriados).toBe("fecha inválida");
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

  // Un trabajo que falla por parámetros debe decir por qué, no solo
  // «Estado: Con errores»: resumenErrores arma la lista campo → motivo
  // que se muestra fuera del <details> plegado (Task 4, punto 1).
  it("resumenErrores arma campo → motivo, el motor manda sobre la validación local, incluye balance", () => {
    const r = resumenErrores(
      { materialidad: "obligatorio", hora_fin: "debe estar entre 0 y 23" },
      { materialidad: "debe ser mayor que cero" },
      "el balance no se pudo leer",
    );
    expect(r).toEqual([
      { campo: "materialidad", etiqueta: "Materialidad global", motivo: "debe ser mayor que cero" },
      { campo: "hora_fin", etiqueta: "Hora de fin de jornada", motivo: "debe estar entre 0 y 23" },
      { campo: "balance", etiqueta: "Balance", motivo: "el balance no se pudo leer" },
    ]);
  });

  it("resumenErrores no inventa nada cuando no hay errores", () => {
    expect(resumenErrores({}, {}, "")).toEqual([]);
  });
});
