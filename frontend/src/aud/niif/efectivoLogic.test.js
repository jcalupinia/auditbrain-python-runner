import { describe, expect, it } from "vitest";

import {
  EJECUCIONES,
  PRINCIPALES,
  avanceCarga,
  estaProcesada,
  estadoRequerimiento,
  puedeEncerar,
  puedeSubir,
  separarRequerimientos,
} from "./efectivoLogic";

// Requerimientos como los devuelve el procesador efectivo_equivalentes.
const REQUESTS = [
  { id: "RQ-001", document: "Anexo de cuentas de caja, bancos e inversiones al corte", dataset: "cuentas", required: true },
  { id: "RQ-002", document: "Partidas conciliatorias de cada cuenta al corte", dataset: "partidas", required: false },
  { id: "RQ-003", document: "Conciliaciones y estados bancarios del mes de corte", use: "soporte" },
  { id: "RQ-008", document: "Política contable de efectivo y equivalentes y actas de arqueo", use: "soporte" },
  { id: "RQ-009", document: "Libro mayor (auxiliar de bancos) del período", dataset: "libro_mayor", required: false },
  { id: "RQ-010", document: "Estado de cuenta bancario del mes (movimientos)", dataset: "estado_cuenta", required: false },
  { id: "RQ-012", document: "Arqueo de caja (recuento por denominación)", dataset: "arqueo", required: false },
];

describe("separarRequerimientos", () => {
  it("las 4 tarjetas primarias van en el orden del mockup y el resto a soporte", () => {
    const { principales, soporte } = separarRequerimientos(REQUESTS);
    expect(principales.map((p) => p.id)).toEqual(["RQ-001", "RQ-002", "RQ-010", "RQ-009"]);
    expect(principales.map((p) => p.titulo)).toEqual([
      "Anexo de Caja y Bancos",
      "Conciliaciones Bancarias",
      "Estados de Cuenta Bancarios",
      "Mayores Contables",
    ]);
    // Cada principal trae su requerimiento canónico.
    expect(principales[0].req.document).toContain("Anexo de cuentas");
    // El resto (soporte) conserva su orden original.
    expect(soporte.map((r) => r.id)).toEqual(["RQ-003", "RQ-008", "RQ-012"]);
  });

  it("solo incluye las tarjetas primarias cuya request existe", () => {
    const { principales } = separarRequerimientos([REQUESTS[0]]);
    expect(principales.map((p) => p.id)).toEqual(["RQ-001"]);
  });

  it("tolera una lista vacía o nula", () => {
    expect(separarRequerimientos([])).toEqual({ principales: [], soporte: [] });
    expect(separarRequerimientos(null)).toEqual({ principales: [], soporte: [] });
  });
});

describe("estaProcesada y habilitación del paso 3", () => {
  it("las cédulas existen a partir de PRUEBA_EJECUTADA", () => {
    for (const e of ["PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS", "EN_REVISION", "APROBADO"]) {
      expect(estaProcesada(e)).toBe(true);
    }
  });
  it("antes de procesar el paso 3 está deshabilitado", () => {
    for (const e of ["REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA", "DOCUMENTACION_VALIDADA", "PRUEBA_CONFIGURADA"]) {
      expect(estaProcesada(e)).toBe(false);
    }
  });
});

describe("puedeSubir y puedeEncerar", () => {
  it("se sube con requerimiento aprobado o documentación recibida", () => {
    expect(puedeSubir("REQUERIMIENTO_APROBADO")).toBe(true);
    expect(puedeSubir("DOCUMENTACION_RECIBIDA")).toBe(true);
    expect(puedeSubir("PROGRAMA_APROBADO")).toBe(false);
  });
  it("una versión aprobada no se puede encerar", () => {
    expect(puedeEncerar("APROBADO")).toBe(false);
    expect(puedeEncerar("RESULTADOS_ANALIZADOS")).toBe(true);
  });
});

describe("estado y avance de la carga", () => {
  const cobertura = [{ id: "RQ-001", complete: true }, { id: "RQ-009", complete: false }];
  it("marca Cargado/Pendiente según la cobertura", () => {
    const map = Object.fromEntries(cobertura.map((c) => [c.id, c]));
    expect(estadoRequerimiento("RQ-001", map)).toBe("Cargado");
    expect(estadoRequerimiento("RQ-009", map)).toBe("Pendiente");
    expect(estadoRequerimiento("RQ-010", map)).toBe("Pendiente");
  });
  it("cuenta solo los obligatorios completos", () => {
    // Obligatorios (required !== false): RQ-001, RQ-003, RQ-008. Solo RQ-001 está completo.
    expect(avanceCarga(REQUESTS, cobertura)).toEqual({ completos: 1, total: 3, pct: 33 });
  });
  it("sin obligatorios el avance es 0/0 y 0%", () => {
    expect(avanceCarga([{ id: "RQ-002", required: false }], [])).toEqual({ completos: 0, total: 0, pct: 0 });
  });
});

describe("catálogos del mockup", () => {
  it("las 11 tarjetas de ejecución están en el orden aprobado", () => {
    expect(EJECUCIONES).toHaveLength(11);
    expect(EJECUCIONES[0].titulo).toBe("Procedimiento de Efectivo y Equivalentes de Efectivo");
    expect(EJECUCIONES.find((e) => e.reproceso).clave).toBe("reproceso");
    expect(EJECUCIONES[EJECUCIONES.length - 1].titulo).toBe("Arqueo de Caja");
  });
  it("hay exactamente 4 tarjetas primarias", () => {
    expect(PRINCIPALES).toHaveLength(4);
  });
});
