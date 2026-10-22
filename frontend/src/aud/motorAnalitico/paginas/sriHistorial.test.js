import { describe, expect, it } from "vitest";
import { COLUMNAS_HISTORIAL, filtrarHistorial, normalizarFila, opcionesDe } from "./sriHistorial.js";

const crudo = [
  { timestamp: "2026-10-21 10:00:00", ruc: "1791859596001", origen: "Recibidos", anio: 2026, mes: 3, dia: 0, tipo: "Facturas", estado: "ok", n_xml: 12, n_pdf: 12, n_registros: 12 },
  { timestamp: "2026-10-20 09:00:00", ruc: "0999999999001", origen: "Emitidos", anio: 2025, mes: 12, dia: 15, tipo: "Retenciones", tipo_visible: "Comprobante de Retencion", estado: "sin_resultados", estado_autorizacion: "Autorizados", establecimiento: "001", punto_emision: "002", fecha_filtro: "15/12/2025", n_xml: 0, n_pdf: 0, n_registros: 0 },
];

describe("historial de descargas SRI", () => {
  it("normaliza período, tipo visible y conteos como la app de escritorio", () => {
    const [a, b] = crudo.map(normalizarFila);
    expect(a.periodo).toBe("Marzo 2026");
    expect(a.conteo).toBe("12 comprobantes · 12 XML · 12 PDF");
    expect(a.tipo).toBe("Facturas");
    expect(b.periodo).toBe("15/12/2025");          // fecha_filtro manda
    expect(b.tipo).toBe("Comprobante de Retencion");
    expect(b.estado_autorizacion).toBe("Autorizados");
    expect(b.conteo).toBe("0 comprobantes");
    expect(COLUMNAS_HISTORIAL.map(([k]) => k)).toContain("estado_autorizacion");
  });

  it("filtra por columna exacta y por búsqueda libre", () => {
    const filas = crudo.map(normalizarFila);
    expect(filtrarHistorial(filas, { ruc: "0999999999001" })).toHaveLength(1);
    expect(filtrarHistorial(filas, { origen: "Recibidos", anio: "2026" })).toHaveLength(1);
    expect(filtrarHistorial(filas, { origen: "Recibidos", anio: "2025" })).toHaveLength(0);
    expect(filtrarHistorial(filas, { busqueda: "retencion" })).toHaveLength(1);
    expect(filtrarHistorial(filas, {})).toHaveLength(2);
    expect(opcionesDe(filas, "anio")).toEqual(["Todos", "2026", "2025"]);
    expect(opcionesDe(filas, "origen")).toEqual(["Todos", "Emitidos", "Recibidos"]);
  });
});
