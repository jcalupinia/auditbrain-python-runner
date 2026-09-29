import { describe, it, expect } from "vitest";

import {
  bloqueaAprobacion, claseEstado, claseVeredicto, diferencias, resumenRecalculo,
  tieneConsola, tituloVeredicto,
} from "./consolaRevisionVista";

describe("consolaRevisionVista", () => {
  it("solo la planificación NIA tiene consola", () => {
    expect(tieneConsola({ definicion: { processor: "planificacion_nia" } })).toBe(true);
    expect(tieneConsola({ definicion: { processor: "cxc_cartera" } })).toBe(false);
    expect(tieneConsola({ definicion: {} })).toBe(false);
    expect(tieneConsola({})).toBe(false);
  });

  it("el color del veredicto distingue apto, observado y no apto", () => {
    expect(claseVeredicto("APTO PARA REVISIÓN DEL SOCIO")).toBe("nf-ok");
    expect(claseVeredicto("OBSERVADO")).toBe("nf-warn");
    expect(claseVeredicto("NO APTO")).toBe("nf-error");
  });

  it("el título del veredicto es legible", () => {
    expect(tituloVeredicto("APTO PARA REVISIÓN DEL SOCIO")).toBe("Apto para revisión del socio");
    expect(tituloVeredicto("NO APTO")).toBe("No apto");
  });

  it("el color de un estado de la puerta de calidad", () => {
    expect(claseEstado("PASA")).toBe("nf-ok");
    expect(claseEstado("FALLA")).toBe("nf-error");
    expect(claseEstado("PENDIENTE")).toBe("muted");
  });

  it("el resumen del recálculo cuenta coincidencias y diferencias", () => {
    expect(resumenRecalculo({ total: 40, diferencias: 0 })).toBe(
      "40 de 40 coinciden con el recálculo independiente");
    expect(resumenRecalculo({ total: 40, diferencias: 2 })).toBe(
      "38 de 40 coinciden con el recálculo independiente · 2 con diferencia");
  });

  it("diferencias devuelve solo las filas que no coinciden", () => {
    const bloque = { detalle: [{ ok: true }, { ok: false, indice: "roi" }, { ok: false, indice: "roe" }] };
    expect(diferencias(bloque).map((f) => f.indice)).toEqual(["roi", "roe"]);
    expect(diferencias(null)).toEqual([]);
  });

  it("solo NO APTO advierte que no está listo para aprobar", () => {
    expect(bloqueaAprobacion({ veredicto: "NO APTO" })).toBe(true);
    expect(bloqueaAprobacion({ veredicto: "OBSERVADO" })).toBe(false);
    expect(bloqueaAprobacion({ veredicto: "APTO PARA REVISIÓN DEL SOCIO" })).toBe(false);
  });
});
