import { describe, expect, it } from "vitest";

import { ETAPAS, alternarProcedimiento, etapaDe, nombreEstado, procedimientosSinFuente } from "./cicloLogic";
import { STATES } from "./sitio/tools/domain.mjs";

describe("etapas de una prueba", () => {
  it("son las 9 del sitio", () => {
    expect(ETAPAS).toHaveLength(9);
  });

  it("cada uno de los 13 estados del sitio cae en una etapa, en orden", () => {
    const etapas = STATES.map(etapaDe);
    expect(etapas.every((e) => e >= 1 && e <= 8)).toBe(true);
    expect([...etapas].sort((a, b) => a - b)).toEqual(etapas);
    expect(etapaDe("APROBADO")).toBe(8);
  });

  it("nombra el estado en español legible", () => {
    expect(nombreEstado("PROGRAMA_PROPUESTO")).toBe("Programa propuesto");
    expect(nombreEstado("DOCUMENTACION_RECIBIDA")).toBe("Documentación recibida");
    expect(nombreEstado("METODOLOGIA_APROBADA")).toBe("Metodología aprobada");
    expect(nombreEstado("EN_REVISION")).toBe("En revisión");
  });
});

describe("fuentes y procedimientos", () => {
  const programa = [{ code: "VNR-01" }, { code: "VNR-02" }];
  const fuentes = [
    { category: "NIIF", verified: true, procedures: ["VNR-01"] },
    { category: "NIA", verified: false, procedures: [] },
  ];

  it("marca y desmarca un procedimiento solo en la fuente indicada", () => {
    const una = alternarProcedimiento(fuentes, 1, "VNR-02");
    expect(una[1].procedures).toEqual(["VNR-02"]);
    expect(una[0]).toBe(fuentes[0]);
    expect(alternarProcedimiento(una, 1, "VNR-02")[1].procedures).toEqual([]);
  });

  it("señala los procedimientos sin fuente verificada", () => {
    expect(procedimientosSinFuente(programa, fuentes)).toEqual(["VNR-02"]);
    // Una fuente sin verificar no cuenta aunque tenga el procedimiento.
    const conNia = alternarProcedimiento(fuentes, 1, "VNR-02");
    expect(procedimientosSinFuente(programa, conNia)).toEqual(["VNR-02"]);
    expect(procedimientosSinFuente(programa, [{ ...conNia[0] }, { ...conNia[1], verified: true }])).toEqual([]);
  });
});

import { componentesDeTexto, detalleRequerimiento, erroresLegibles, esTabular, mapeoSugerido } from "./cicloLogic";

describe("requerimiento y documentación", () => {
  it("convierte el texto de componentes en una lista limpia", () => {
    expect(componentesDeTexto(" Quito, Guayaquil ;Quito\n\n Cuenca")).toEqual(["Quito", "Guayaquil", "Cuenca"]);
    expect(componentesDeTexto("")).toEqual([]);
  });

  it("solo XLSX y CSV sirven como población", () => {
    expect(esTabular("mayor.XLSX")).toBe(true);
    expect(esTabular("mayor.csv")).toBe(true);
    expect(esTabular("mayor.pdf")).toBe(false);
  });

  it("sugiere el mapeo por etiqueta o código, sin tildes ni mayúsculas", () => {
    const campos = [{ key: "id", label: "Código" }, { key: "quantity", label: "Cantidad" }, { key: "unit_cost", label: "Costo unitario" }];
    expect(mapeoSugerido(["CODIGO", "Descripción", "cantidad", "Costo Unitario"], campos)).toEqual({ id: 0, quantity: 2, unit_cost: 3 });
    expect(mapeoSugerido(["x"], campos)).toEqual({});
  });

  it("resume los errores de validación con su fila", () => {
    expect(erroresLegibles({ errors: [{ row: 8, message: "Cantidad: número inválido." }] })).toEqual(["Fila 8 · Cantidad: número inválido."]);
  });
});

describe("detalleRequerimiento", () => {
  it("muestra uso, reporte, período y contenido cuando la ficha los trae", () => {
    expect(detalleRequerimiento({ use: "calculo", report: "Cartera por vencimiento", timing: "Al cierre", content: "Una fila por factura" }))
      .toEqual(["Alimenta el cálculo", "Reporte: Cartera por vencimiento", "Período: Al cierre", "Contenido mínimo: Una fila por factura"]);
  });
  it("no muestra nada en un requerimiento genérico", () => {
    expect(detalleRequerimiento({ id: "RQ-001", document: "Mayor", format: "XLSX / CSV" })).toEqual([]);
  });
});

import { herramientaDePrueba, tramosDeTexto } from "./cicloLogic";

describe("herramientaDePrueba", () => {
  const prueba = {
    id: 7, version: 2, estado: "PRUEBA_EJECUTADA", definicion: { id: "vnr", name: "VNR" },
    registro: { engagement: { client: "X" }, run: { totals: {} }, analysis: "" },
    eventos: [{ accion: "execute", actor: "a@b.ec", fecha: "2026-09-21T10:00:00", estado_anterior: "METODOLOGIA_APROBADA", estado_nuevo: "PRUEBA_EJECUTADA", comentario: null }],
  };
  it("lleva registro, definición, estado y bitácora con los nombres del sitio", () => {
    const t = herramientaDePrueba(prueba);
    expect(t.definition.name).toBe("VNR");
    expect(t.state).toBe("PRUEBA_EJECUTADA");
    expect(t.draft).toBe(false);
    expect(t.engagement.client).toBe("X");
    expect(t.events[0]).toEqual({ action: "execute", actor: "a@b.ec", at: "2026-09-21T10:00:00", previous: "METODOLOGIA_APROBADA", next: "PRUEBA_EJECUTADA", comment: "", version: 2 });
  });
  it("el estado del papel sale del estado de la prueba", () => {
    expect(herramientaDePrueba({ ...prueba, estado: "APROBADO" }).state).toBe("APROBADO");
  });
});

describe("tramosDeTexto", () => {
  it("convierte a números y deja sin límite solo el último vacío", () => {
    expect(tramosDeTexto([{ min: "0", max: "30", rate: "0.01" }, { min: "31", max: "", rate: " 0.2 " }]))
      .toEqual([{ min: 0, max: 30, rate: "0.01" }, { min: 31, max: null, rate: "0.2" }]);
  });
});

import { archivosDe, formulasLegibles, fuentesConfirmadas, mejorEncabezado, pasoPreparar, problemasDe } from "./cicloLogic";

describe("E10 · mejorEncabezado", () => {
  const campos = [
    { key: "id", label: "Código" }, { key: "quantity", label: "Cantidad", aliases: ["Cant."] },
    { key: "unit_cost", label: "Costo unitario" }, { key: "nota", label: "Nota", required: false },
  ];
  it("encuentra la fila de encabezados aunque haya títulos arriba, y prefiere la hoja Datos", () => {
    const sheets = [
      { name: "Resumen", rows: [["Código", "x"]] },
      { name: "Datos", rows: [["REPORTE DE INVENTARIO"], [], ["Código", "Cant.", "Costo unitario"], ["A", "1", "2"]] },
    ];
    expect(mejorEncabezado(sheets, campos)).toEqual({ sheet: "Datos", header: 3, mapping: { id: 0, quantity: 1, unit_cost: 2 }, faltan: [] });
  });
  it("dice qué columnas obligatorias no reconoce", () => {
    expect(mejorEncabezado([{ name: "H", rows: [["Código", "Otra"]] }], campos).faltan).toEqual(["Cantidad", "Costo unitario"]);
  });
});

describe("E10 · formulasLegibles", () => {
  it("escribe cada cálculo en lenguaje contable y marca el principal", () => {
    const d = {
      fields: [{ key: "quantity", label: "Cantidad" }, { key: "unit_cost", label: "Costo unitario" }, { key: "due", label: "Vencimiento" }],
      rules: [
        { key: "cost", label: "Costo total", op: "multiply", a: "quantity", b: "unit_cost" },
        { key: "piso", label: "Piso", op: "max", a: "cost", b: "#0" },
        { key: "dias", label: "Días", op: "days", a: "due", b: "corte" },
        { key: "tasa", label: "Tasa", op: "band", a: "dias", table: [{ from: "0", value: "0.01" }, { from: "31", value: "0.05" }] },
        { key: "aj", label: "Ajuste", op: "if", a: "piso", b: "cost", c: "#0" },
      ],
      primary: "aj",
    };
    expect(formulasLegibles(d).map((x) => x.texto)).toEqual([
      "Costo total = Cantidad × Costo unitario",
      "Piso = el mayor entre Costo total y 0",
      "Días = días desde Vencimiento hasta fecha de corte",
      "Tasa = tramo de Días: desde 0 → 0.01; desde 31 → 0.05",
      "Ajuste = si Piso no es cero, Costo total; si no, 0",
    ]);
    expect(formulasLegibles(d).at(-1).principal).toBe(true);
  });
});

describe("E10 · confirmar base técnica", () => {
  const prueba = (estado, extra = {}) => ({
    estado,
    definicion: { source: { document: "NIC 2 Inventarios", url: "https://www.ifrs.org/x" }, nia: ["NIA 500", "NIA 540"] },
    registro: {
      engagement: { framework: "NIIF completas", cutoff: "2025-12-31" },
      program: [{ code: "P-01", reference: "NIA 500 párr. A49" }, { code: "P-02", reference: "NIC 2 párr. 9" }],
      sources: [
        { category: "NIIF", url: "https://www.ifrs.org/issued-standards/", document: "x", verified: false, procedures: [] },
        { category: "NIA", url: "https://www.iaasb.org/h", document: "Handbook", verified: false, procedures: [] },
      ],
      requests: [{ id: "RQ-001" }],
      ...extra,
    },
  });
  it("verifica las fuentes con la referencia de la ficha y vincula todos los procedimientos", () => {
    const [niif, nia] = fuentesConfirmadas(prueba("PROGRAMA_PROPUESTO"));
    expect(niif).toMatchObject({ verified: true, document: "NIC 2 Inventarios", url: "https://www.ifrs.org/x", section: "NIC 2 párr. 9", date: "Vigente al 2025-12-31", procedures: ["P-01", "P-02"] });
    expect(nia).toMatchObject({ verified: true, document: "NIA 500, NIA 540", section: "NIA 500 párr. A49", procedures: ["P-01", "P-02"] });
  });
  it("encadena investigar, programa, aprobar, requerimiento y aprobar", () => {
    expect(pasoPreparar(prueba("PRUEBA_SELECCIONADA"))[0]).toBe("research");
    expect(pasoPreparar(prueba("PRUEBA_SELECCIONADA", { researchedAt: "x" }))[0]).toBe("generate_program");
    expect(pasoPreparar(prueba("PROGRAMA_PROPUESTO"))[0]).toBe("approve_program");
    expect(pasoPreparar(prueba("PROGRAMA_APROBADO"))[0]).toBe("generate_request");
    expect(pasoPreparar(prueba("REQUERIMIENTO_GENERADO"))).toEqual(["approve_request", { requests: [{ id: "RQ-001" }] }]);
    expect(pasoPreparar(prueba("REQUERIMIENTO_APROBADO"))).toBe(null);
  });
});

describe("E10 · archivos y problemas", () => {
  it("toma los tabulares no rechazados del requerimiento", () => {
    const p = { archivos: [
      { requerimiento: "RQ-001", nombre: "q.xlsx", estado: "recibido" }, { requerimiento: "RQ-001", nombre: "g.csv", estado: "rechazado" },
      { requerimiento: "RQ-001", nombre: "x.pdf", estado: "recibido" }, { requerimiento: "RQ-002", nombre: "p.xlsx", estado: "recibido" }] };
    expect(archivosDe(p, "RQ-001").map((a) => a.nombre)).toEqual(["q.xlsx"]);
  });
  it("señala el mayor pendiente, las advertencias y las excepciones", () => {
    const p = { registro: { controlTotal: "470.00", reconciliation: { within: false, ledger: "0", difference: "470.00" },
      validation: { warnings: [{ row: 3, message: "Identificador repetido" }] }, run: { exceptions: [{}, {}] } } };
    expect(problemasDe(p)).toEqual([
      "Saldo del mayor no ingresado: la población suma 470.00; concilie antes de aprobar.",
      "1 advertencia(s) de validación: fila 3 · Identificador repetido",
      "2 excepción(es) por partida para evaluar.",
    ]);
  });
});

import { marcoAplicable, niasDe } from "./cicloLogic";

describe("marco aplicable y NIA", () => {
  const vnr = { source: { document: "IAS 2" }, source_pymes: { document: "Sección 13" }, frameworks: ["NIIF completas", "NIIF para las PYMES"] };
  it("marca la norma del marco del encargo", () => {
    const m = marcoAplicable(vnr, "NIIF para las PYMES");
    expect(m.sirve).toBe(true);
    expect(m.normas.filter((n) => n.aplica).map((n) => n.texto)).toEqual(["Sección 13"]);
  });
  it("avisa si la herramienta no es para el marco del encargo", () => {
    expect(marcoAplicable({ ...vnr, frameworks: ["NIIF completas"] }, "NIIF para las PYMES").sirve).toBe(false);
  });
  it("sin marcos declarados, sirve para los dos", () => {
    expect(marcoAplicable({}, "NIIF completas").marcos).toEqual(["NIIF completas", "NIIF para las PYMES"]);
  });
  it("las NIA vienen como filas, también desde una lista de nombres", () => {
    expect(niasDe({ nia: ["NIA 500", { document: "NIA 540", section: "párr. 13", requirement: "estimación" }] })).toEqual([
      { document: "NIA 500", section: "", requirement: "" }, { document: "NIA 540", section: "párr. 13", requirement: "estimación" }]);
  });
});
