import { describe, expect, it } from "vitest";
import { CATEGORIES } from "./catalog.js";
import {
  carteraMedida,
  carteraMedidaDe,
  coberturaDe,
  fechaEmision,
  parametrosDeLaCorrida,
  tramosVisibles,
} from "./pceCxc.js";

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

describe("la tarjeta del catálogo promete lo que la pantalla acepta (M9)", () => {
  const descripcion = () =>
    CATEGORIES.find((c) => c.id === "CXC").tools[0].description;

  it("no ofrece subir el movimiento de la provisión: el endpoint exige tres archivos", () => {
    expect(descripcion()).not.toMatch(/sub[ei][^.]*movimiento de la provisi[óo]n/i);
  });

  it("sigue diciendo que se suben los tres análisis de antigüedad", () => {
    expect(descripcion()).toMatch(/tres an[áa]lisis de antig[üu]edad/i);
  });

  it("dice que el movimiento de la provisión se declara en la pantalla", () => {
    expect(descripcion()).toMatch(/movimiento de la provisi[óo]n/i);
    expect(descripcion()).toMatch(/declara/i);
  });
});

describe("parametrosDeLaCorrida", () => {
  const datos = {
    entidad: "ARCOLANDS S.A.",
    materialidad: "12000",
    umbral_individual: "100000",
    eeff_nr: "195000",
    eeff_r: "25000",
    umbral_dias: 730,
    mayor_provision: "  Mayor 2.1.3.01 de los tres ejercicios; castigos por USD 340, inmateriales.  ",
  };
  const fechas = ["2022-12-31", "2023-12-31", "2024-12-31"];

  it("envía el movimiento de la provisión que declara el auditor, sin espacios sobrantes", () => {
    const p = parametrosDeLaCorrida(datos, fechas, 7, new Date(2025, 1, 28));
    expect(p.mayor_provision).toBe(
      "Mayor 2.1.3.01 de los tres ejercicios; castigos por USD 340, inmateriales."
    );
  });

  it("deja vacío el movimiento de la provisión cuando no se declaró: el pendiente debe dispararse", () => {
    const p = parametrosDeLaCorrida({ ...datos, mayor_provision: "   " }, fechas, null);
    expect(p.mayor_provision).toBe("");
  });

  it("guarda la fecha de emisión con la corrida", () => {
    const p = parametrosDeLaCorrida(datos, fechas, null, new Date(2025, 1, 28));
    expect(p.fecha_emision).toBe("2025-02-28");
  });

  it("traslada los umbrales, la materialidad y los EEFF como números", () => {
    const p = parametrosDeLaCorrida(datos, fechas, 7);
    expect(p).toMatchObject({
      project_id: 7,
      entidad: "ARCOLANDS S.A.",
      fechas,
      umbral_dias_incumplimiento: 730,
      umbral_individual: 100000,
      materialidad: 12000,
      eeff: { no_relacionados: 195000, relacionados: 25000 },
    });
  });
});

describe("la pantalla toma la medición del motor (I8)", () => {
  const resultado = {
    ecl_total: 20000,
    porcentaje_sobre_cartera: 0.1,
    medicion_completa: false,
    exposicion: { total: 210000, sin_medir: 10000, sin_estratificar: 0, medida: 200000 },
  };

  it("usa la cartera medida que calculó el motor", () => {
    expect(carteraMedidaDe(resultado)).toBe(200000);
  });

  it("y la cobertura que calculó el motor, sobre lo medido", () => {
    expect(coberturaDe(resultado)).toBe(0.1);
  });

  it("con una corrida antigua sin esos campos, los reconstruye de la exposición", () => {
    const antigua = {
      ecl_total: 20000,
      exposicion: { total: 210000, sin_medir: 10000, sin_estratificar: 0 },
    };
    expect(carteraMedidaDe(antigua)).toBe(200000);
    expect(coberturaDe(antigua)).toBeCloseTo(0.1, 10);
  });

  it("sin resultado todavía, no inventa cifras", () => {
    expect(carteraMedidaDe(null)).toBeNull();
    expect(coberturaDe(null)).toBeNull();
  });
});
