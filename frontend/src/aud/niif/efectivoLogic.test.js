import { describe, expect, it } from "vitest";

import {
  avanceCarga,
  estaProcesada,
  estadoPrueba,
  estadoRequerimiento,
  puedeEncerar,
  puedeSubir,
  separarRequerimientos,
} from "./efectivoLogic";
import { CONFIG, configDeProcesador } from "./procesoConfig";

// Catálogos por herramienta (ahora viven en procesoConfig.js; la lógica pura es
// config-driven y se parametriza por la lista de principales).
const PRINCIPALES = CONFIG.efectivo.principales;
const EJECUCIONES = CONFIG.efectivo.ejecuciones;

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
  it("las 4 tarjetas primarias de efectivo van en el orden del mockup y el resto a soporte", () => {
    const { principales, soporte } = separarRequerimientos(REQUESTS, PRINCIPALES);
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
    const { principales } = separarRequerimientos([REQUESTS[0]], PRINCIPALES);
    expect(principales.map((p) => p.id)).toEqual(["RQ-001"]);
  });

  it("sin lista de principales todo cae en soporte", () => {
    const { principales, soporte } = separarRequerimientos(REQUESTS);
    expect(principales).toEqual([]);
    expect(soporte.map((r) => r.id)).toEqual(REQUESTS.map((r) => r.id));
  });

  it("tolera una lista vacía o nula", () => {
    expect(separarRequerimientos([], PRINCIPALES)).toEqual({ principales: [], soporte: [] });
    expect(separarRequerimientos(null, PRINCIPALES)).toEqual({ principales: [], soporte: [] });
  });

  it("agrupa los requerimientos de planificación según su config", () => {
    // Requerimientos como los devuelve el procesador planificacion_nia.
    const REQ_PLAN = [
      { id: "RQ-001", document: "Balance de comprobación al cierre del año anterior", dataset: "balance_anterior" },
      { id: "RQ-002", document: "Balance de comprobación a la fecha de corte", dataset: "balance_actual" },
      { id: "RQ-003", document: "Estado de resultados del año anterior al mismo corte", dataset: "resultados_mismo_corte" },
      { id: "RQ-004", document: "Carta de control interno (hallazgos)", dataset: "carta_control_interno" },
      { id: "RQ-005", document: "Informe de auditoría del año anterior", dataset: "informe_anterior" },
      { id: "RQ-006", document: "Notas a los estados financieros auditados del año anterior", dataset: "notas_estados_financieros" },
      { id: "RQ-009", document: "Composición de las notas a los estados financieros", dataset: "notas_detalle" },
      { id: "RQ-007", document: "Documentos firmados de respaldo", use: "soporte" },
      { id: "RQ-008", document: "RUC actualizado de la entidad", use: "soporte" },
    ];
    const { principales, soporte } = separarRequerimientos(REQ_PLAN, CONFIG.planificacion.principales);
    // Las 6 tarjetas primarias en el orden del mockup de planificación.
    expect(principales.map((p) => p.id)).toEqual(["RQ-002", "RQ-001", "RQ-006", "RQ-005", "RQ-004", "RQ-008"]);
    expect(principales[0].titulo).toBe("Estados Financieros Año Actual");
    // El resto (RQ-003, RQ-009, RQ-007) va a soporte, en su orden original.
    expect(soporte.map((r) => r.id)).toEqual(["RQ-003", "RQ-009", "RQ-007"]);
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

describe("estados del prompt", () => {
  it("estado del requerimiento: Pendiente / Cargado / Validado / Error", () => {
    const map = { "RQ-001": { complete: true }, "RQ-002": { complete: false }, "RQ-003": { complete: true, rejected: true } };
    expect(estadoRequerimiento("RQ-002", map, "DOCUMENTACION_RECIBIDA")).toBe("Pendiente");
    expect(estadoRequerimiento("RQ-001", map, "DOCUMENTACION_RECIBIDA")).toBe("Cargado");
    expect(estadoRequerimiento("RQ-001", map, "PRUEBA_EJECUTADA")).toBe("Validado");
    expect(estadoRequerimiento("RQ-003", map, "PRUEBA_EJECUTADA")).toBe("Error");
  });
  it("estado de la prueba: BLOQUEADA / DISPONIBLE / EJECUTADA / CON EXCEPCIONES / REVISADA", () => {
    expect(estadoPrueba("PRUEBA_SELECCIONADA", false)).toBe("BLOQUEADA");
    expect(estadoPrueba("REQUERIMIENTO_APROBADO", false)).toBe("DISPONIBLE");
    expect(estadoPrueba("PRUEBA_EJECUTADA", false)).toBe("EJECUTADA");
    expect(estadoPrueba("PRUEBA_EJECUTADA", true)).toBe("CON EXCEPCIONES");
    expect(estadoPrueba("EN_REVISION", true)).toBe("REVISADA");
    expect(estadoPrueba("APROBADO", false)).toBe("REVISADA");
  });
});

describe("catálogos de la config (procesoConfig)", () => {
  it("efectivo: 4 tarjetas primarias y 11 de ejecución en el orden aprobado", () => {
    expect(PRINCIPALES).toHaveLength(4);
    expect(EJECUCIONES).toHaveLength(11);
    expect(EJECUCIONES[0].titulo).toBe("Procedimiento de Efectivo y Equivalentes de Efectivo");
    expect(EJECUCIONES.find((e) => e.reproceso).clave).toBe("reproceso");
    expect(EJECUCIONES[EJECUCIONES.length - 1].titulo).toBe("Arqueo de Caja");
  });

  it("planificación: 6 tarjetas primarias y 11 de ejecución, sin reproceso", () => {
    const plan = CONFIG.planificacion;
    expect(plan.eyebrow).toBe("PLANIFICACIÓN DE LA AUDITORÍA");
    expect(plan.principales).toHaveLength(6);
    expect(plan.principales.map((p) => p.id)).toEqual(["RQ-002", "RQ-001", "RQ-006", "RQ-005", "RQ-004", "RQ-008"]);
    expect(plan.ejecuciones).toHaveLength(11);
    expect(plan.ejecuciones[0].titulo).toBe("Tablero Ejecutivo");
    expect(plan.ejecuciones[plan.ejecuciones.length - 1].titulo).toBe("Programa");
    // El reproceso es exclusivo de efectivo.
    expect(plan.ejecuciones.some((e) => e.reproceso)).toBe(false);
  });

  // Íconos válidos del mapa de VistaProceso (si se agrega uno nuevo aquí, hay
  // que definir su SVG en VistaProceso.jsx o la tarjeta sale en blanco).
  const ICONOS_OK = new Set([
    "chart", "doc", "pdf", "shield", "bank", "list", "table", "search",
    "refresh", "calendar", "dashboard", "line", "pie", "calc", "warning", "gears",
  ]);

  it("cada tarjeta de ejecución declara sus requerimientos relacionados (todas las configs)", () => {
    for (const cfg of Object.values(CONFIG)) {
      for (const e of cfg.ejecuciones) {
        const rel = e.relacionados;
        const ok = rel === "todos" || (Array.isArray(rel) && rel.length > 0 && rel.every((id) => /^RQ-\d+$/.test(id)));
        expect(ok, `${cfg.processor} · ${e.clave}`).toBe(true);
      }
    }
    // Ejemplos concretos del mapeo aprobado.
    expect(CONFIG.planificacion.ejecuciones.find((e) => e.clave === "perfil").relacionados).toEqual(["RQ-005", "RQ-008", "RQ-004"]);
    expect(CONFIG.efectivo.ejecuciones.find((e) => e.clave === "partidas").relacionados).toEqual(["RQ-002"]);
    expect(CONFIG.cxc.ejecuciones.find((e) => e.clave === "deterioro").relacionados).toEqual(["RQ-007", "RQ-001"]);
  });

  it("toda config tiene forma válida: processor, primarias, ejecuciones únicas e íconos conocidos", () => {
    for (const cfg of Object.values(CONFIG)) {
      expect(typeof cfg.processor, cfg.processor).toBe("string");
      expect(cfg.principales.length, `${cfg.processor} sin primarias`).toBeGreaterThan(0);
      expect(cfg.ejecuciones.length, `${cfg.processor} sin ejecuciones`).toBeGreaterThan(0);
      // claves de ejecución únicas
      const claves = cfg.ejecuciones.map((e) => e.clave);
      expect(new Set(claves).size, `${cfg.processor} claves duplicadas`).toBe(claves.length);
      // íconos válidos (primarias y ejecuciones)
      for (const p of cfg.principales) {
        expect(ICONOS_OK.has(p.icono), `${cfg.processor} · ${p.id} · ícono ${p.icono}`).toBe(true);
      }
      for (const e of cfg.ejecuciones) {
        expect(ICONOS_OK.has(e.icono), `${cfg.processor} · ${e.clave} · ícono ${e.icono}`).toBe(true);
      }
    }
  });

  it("configDeProcesador enruta cada processor a su config y null para el resto", () => {
    expect(configDeProcesador("efectivo_equivalentes")).toBe(CONFIG.efectivo);
    expect(configDeProcesador("planificacion_nia")).toBe(CONFIG.planificacion);
    expect(configDeProcesador("cxc_cartera")).toBe(CONFIG.cxc);
    expect(configDeProcesador("proveedores_cxp")).toBe(CONFIG.proveedores);
    expect(configDeProcesador("inventarios_costos")).toBe(CONFIG.inventarios);
    expect(configDeProcesador("ingresos_contratos")).toBe(CONFIG.ingresos);
    expect(configDeProcesador("cartera_incobrables")).toBe(null);
    expect(configDeProcesador(undefined)).toBe(null);
  });
});
