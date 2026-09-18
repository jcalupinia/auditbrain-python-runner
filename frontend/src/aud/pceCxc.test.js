import { describe, expect, it } from "vitest";
import { CATEGORIES } from "./catalog.js";
import { carteraMedida, fechaEmision, tramosVisibles } from "./pceCxc.js";

describe("catálogo AUD", () => {
  it("la tarjeta de Cuentas por cobrar ya no está vacía", () => {
    const cxc = CATEGORIES.find((c) => c.id === "CXC");
    expect(cxc.tools).toBeDefined();
    expect(cxc.tools[0].id).toBe("AUD.CXC.PCE");
  });

  it("conserva su identificador, etiqueta y tipo", () => {
    const cxc = CATEGORIES.find((c) => c.id === "CXC");
    expect(cxc.label).toBe("Cuentas por cobrar");
    expect(cxc.type).toBe("ciclo");
  });
});

describe("carteraMedida", () => {
  it("con exposición sin medir y sin estratificar en cero, retorna el total", () => {
    const total = 1000000;
    const resultado = carteraMedida(total, 0, 0);
    expect(resultado).toBe(total);
  });

  it("con exposición sin medir, la resta del total", () => {
    const total = 1000000;
    const sinMedir = 100000;
    const resultado = carteraMedida(total, sinMedir, 0);
    expect(resultado).toBe(total - sinMedir);
  });

  it("con exposición sin estratificar, también la resta del total", () => {
    const total = 1000000;
    const sinEstratificar = 50000;
    const resultado = carteraMedida(total, 0, sinEstratificar);
    expect(resultado).toBe(total - sinEstratificar);
  });

  it("con ambas exposiciones, resta las dos del total", () => {
    const total = 1000000;
    const sinMedir = 100000;
    const sinEstratificar = 50000;
    const resultado = carteraMedida(total, sinMedir, sinEstratificar);
    expect(resultado).toBe(total - sinMedir - sinEstratificar);
  });

  it("retorna null si total es null", () => {
    const resultado = carteraMedida(null, 100000, 50000);
    expect(resultado).toBeNull();
  });
});

describe("fechaEmision", () => {
  it("da la fecha local en formato AAAA-MM-DD, con ceros a la izquierda", () => {
    expect(fechaEmision(new Date(2025, 2, 4, 23, 30))).toBe("2025-03-04");
  });

  it("no se corre de día por la zona horaria (usa la fecha local, no la UTC)", () => {
    const tarde = new Date(2025, 11, 31, 22, 0);
    expect(fechaEmision(tarde)).toBe("2025-12-31");
  });
});

describe("tramosVisibles", () => {
  const ruido = (segmento, banda) => ({
    segmento,
    tramo: banda,
    exposicion: 0,
    tasa_perdida: null,
    ecl: null,
  });

  it("deja fuera las combinaciones sin exposición ni tasa", () => {
    const tramos = [
      { segmento: "NO-RELACIONADOS", tramo: "Por vencer", exposicion: 80000, tasa_perdida: 0.01, ecl: 800 },
      ruido("NO-RELACIONADOS", "31 a 60 días"),
      ruido("RELACIONADOS", "91 a 180 días"),
    ];
    expect(tramosVisibles(tramos).map((t) => t.tramo)).toEqual(["Por vencer"]);
  });

  it("conserva la banda con cartera que no se pudo medir", () => {
    const tramos = [
      { segmento: "NO-RELACIONADOS", tramo: "Más de 730 días", exposicion: 5000, tasa_perdida: null, ecl: null },
      ruido("RELACIONADOS", "Más de 730 días"),
    ];
    expect(tramosVisibles(tramos)).toHaveLength(1);
    expect(tramosVisibles(tramos)[0].exposicion).toBe(5000);
  });

  it("conserva la pérdida cero medida: tiene tasa, no es una banda inexistente", () => {
    const tramos = [{ segmento: "RELACIONADOS", tramo: "Por vencer", exposicion: 0, tasa_perdida: 0.02, ecl: 0 }];
    expect(tramosVisibles(tramos)).toHaveLength(1);
  });

  it("tolera una matriz sin tramos", () => {
    expect(tramosVisibles(undefined)).toEqual([]);
  });
});

describe("la cartera medida de la pantalla y la del papel", () => {
  // Mismos importes que RESULTADO_SIN_MEDIR en tests/test_pce_exporter.py.
  const total = 170000;
  const sinMedir = 35000;
  const sinEstratificar = 20000;
  const estratificada = 100000 + 50000; // 05-Matriz + 06-Individual

  it("dan la misma cifra: 08-Conciliacion B9 es =B5-B8", () => {
    expect(carteraMedida(total, sinMedir, sinEstratificar)).toBe(estratificada - sinMedir);
  });

  it("y la cartera total analizada del papel es el total de la pantalla", () => {
    expect(estratificada + sinEstratificar).toBe(total);
  });
});
