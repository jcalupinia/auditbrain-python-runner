import { describe, expect, it } from "vitest";
import { CATEGORIES } from "./catalog.js";
import {
  archivosQueSuperanElLimite,
  carteraMedida,
  bandasDeLaPolitica,
  carteraMedidaDe,
  coberturaDe,
  controlDeLaCohorte,
  cotasDeLaCorrida,
  evaluacionesIndividualesDeclaradas,
  factorProspectivoDeclarado,
  fechaEmision,
  filasIncompletas,
  parametrosDeLaCorrida,
  tasaSustitutaCompleta,
  tasasSustitutasDeclaradas,
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
  // Mismos importes que RESULTADO_SIN_MEDIR en tests/test_pce_exporter.py, y
  // las mismas cifras que esa prueba comprueba recalculando 08-Conciliacion.
  // Antes aquí se hacía aritmética sobre las constantes del propio test
  // (`estratificada + sinEstratificar === total`), que pasa con cualquier
  // código: no tocaba ninguna función del producto.
  const exposicion = {
    colectiva: 100000,
    individual: 50000,
    sin_estratificar: 20000,
    sin_medir: 35000,
    total: 170000,
  };

  it("da la misma cifra que 08-Conciliacion B9 (=B5-B8): 115.000", () => {
    expect(carteraMedida(170000, 35000, 20000)).toBe(115000);
  });

  it("carteraMedidaDe la reconstruye desde la exposición de la corrida", () => {
    expect(carteraMedidaDe({ exposicion })).toBe(115000);
  });

  it("y prefiere `exposicion.medida`, que es la que calculó el motor", () => {
    expect(carteraMedidaDe({ exposicion: { ...exposicion, medida: 114999.5 } })).toBe(114999.5);
  });

  it("la cobertura se mide sobre lo medido, no sobre el total", () => {
    expect(coberturaDe({ exposicion, ecl_total: 23000 })).toBe(23000 / 115000);
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

describe("bandasDeLaPolitica (C2)", () => {
  it("con el umbral de 730 días desdobla la banda abierta: ocho bandas", () => {
    const bandas = bandasDeLaPolitica(730);
    expect(bandas).toHaveLength(8);
    expect(bandas[0]).toBe("Por vencer");
    expect(bandas[6]).toBe("361 a 730 días");
    expect(bandas[7]).toBe("Más de 730 días");
  });

  it("con un umbral que no supera el inicio de la banda abierta, no desdobla", () => {
    const bandas = bandasDeLaPolitica(361);
    expect(bandas).toHaveLength(7);
    expect(bandas[6]).toBe("Más de 360 días");
  });

  it("sin umbral válido cae al del plan (730)", () => {
    expect(bandasDeLaPolitica("")).toEqual(bandasDeLaPolitica(730));
  });
});

describe("la política del cliente viaja con la corrida (C2)", () => {
  const base = {
    entidad: "ARCOLANDS S.A.",
    materialidad: "12000",
    umbral_individual: "100000",
    eeff_nr: "195000",
    eeff_r: "25000",
    umbral_dias: 730,
    mayor_provision: "",
  };
  const fechas = ["2022-12-31", "2023-12-31", "2024-12-31"];

  it("manda cada banda declarada como fracción, no como porcentaje", () => {
    const p = parametrosDeLaCorrida(
      { ...base, politica: { "Por vencer": "0", "0 a 30 días": "2", "31 a 60 días": "12,5" } },
      fechas,
      null
    );
    expect(p.politica["Por vencer"]).toBe(0);
    expect(p.politica["0 a 30 días"]).toBeCloseTo(0.02, 10);
    expect(p.politica["31 a 60 días"]).toBeCloseTo(0.125, 10);
  });

  it("no manda las bandas que el auditor dejó en blanco: quedan sin comparar", () => {
    const p = parametrosDeLaCorrida(
      { ...base, politica: { "Por vencer": "", "0 a 30 días": "   ", "31 a 60 días": "3" } },
      fechas,
      null
    );
    expect(Object.keys(p.politica)).toEqual(["31 a 60 días"]);
  });

  it("sin política declarada manda un objeto vacío, no ceros", () => {
    const p = parametrosDeLaCorrida(base, fechas, null);
    expect(p.politica).toEqual({});
  });
});

describe("controlDeLaCohorte (I5)", () => {
  it("resume el control cuando la cohorte es coherente", () => {
    const c = controlDeLaCohorte({
      control_corte_intermedio: {
        documentos_cohorte: 120,
        vivos_en_intermedio: 80,
        permanencia_intermedia: 0.6666666666666666,
        inconsistencias: [],
        inconsistencias_total: 0,
        inconsistencias_importe: 0,
        consistente: true,
      },
    });
    expect(c.consistente).toBe(true);
    expect(c.total).toBe(0);
    expect(c.permanencia).toBeCloseTo(0.6667, 4);
  });

  it("lista los documentos con trayectoria imposible", () => {
    const c = controlDeLaCohorte({
      control_corte_intermedio: {
        documentos_cohorte: 3,
        vivos_en_intermedio: 1,
        permanencia_intermedia: 0.3333333333333333,
        inconsistencias: [
          { documento: "F-77", tipo: "reaparece_tras_desaparecer" },
          { documento: "F-88", tipo: "remanente_mayor_que_intermedio" },
        ],
        inconsistencias_total: 2,
        inconsistencias_importe: 6500,
        consistente: false,
      },
    });
    expect(c.consistente).toBe(false);
    expect(c.total).toBe(2);
    expect(c.importe).toBe(6500);
    expect(c.ejemplos).toBe("F-77, F-88");
  });

  it("una corrida sin el control no inventa uno", () => {
    expect(controlDeLaCohorte({})).toBeNull();
    expect(controlDeLaCohorte(null)).toBeNull();
  });
});

describe("el formulario manda lo que promete (T12)", () => {
  const fechas = ["2023-12-31", "2024-12-31", "2025-12-31"];
  const base = {
    entidad: "ARCOLANDS S.A.",
    ruc: "1791240154001",
    materialidad: "50000",
    umbral_individual: "200000",
    eeff_nr: "1000000",
    eeff_r: "135300",
    umbral_dias: 730,
    mayor_provision: "PT B-2",
    politica: {},
    factor_nr: "1.10",
    factor_r: "1.05",
    justificacion_prospectivo: "Contracción del sector prevista por el BCE para 2026.",
    tasas_sustitutas: [
      { segmento: "RELACIONADOS", banda: "361 a 730 días", tasa: "42", justificacion: "Analogía con terceros de la misma banda (PT C-4)." },
    ],
    evaluaciones_individuales: [
      { segmento: "NO-RELACIONADOS", cliente: "GRANDES ALMACENES", ecl: "93600", justificacion: "Concurso preventivo; acuerdo de pago al 72 % (PT D-1)." },
    ],
  };

  it("envía el RUC de la entidad: 00-Caratula B7 quedaba en blanco", () => {
    expect(parametrosDeLaCorrida(base, fechas, null).ruc).toBe("1791240154001");
  });

  it("envía el factor prospectivo por segmento", () => {
    expect(parametrosDeLaCorrida(base, fechas, null).factor_prospectivo).toEqual({
      "NO-RELACIONADOS": 1.1,
      RELACIONADOS: 1.05,
    });
  });

  it("envía la justificación del ajuste prospectivo", () => {
    expect(parametrosDeLaCorrida(base, fechas, null).justificacion_prospectivo).toMatch(/BCE/);
  });

  it("envía las tasas sustitutas como fracción, con su justificación", () => {
    expect(parametrosDeLaCorrida(base, fechas, null).tasas_sustitutas).toEqual({
      "RELACIONADOS|361 a 730 días": {
        tasa: 0.42,
        justificacion: "Analogía con terceros de la misma banda (PT C-4).",
      },
    });
  });

  it("envía las evaluaciones individuales con su importe y su justificación", () => {
    expect(parametrosDeLaCorrida(base, fechas, null).evaluaciones_individuales).toEqual({
      "NO-RELACIONADOS|GRANDES ALMACENES": {
        ecl: 93600,
        justificacion: "Concurso preventivo; acuerdo de pago al 72 % (PT D-1).",
      },
    });
  });

  it("sin factor declarado manda 1,000 en los dos segmentos: sin ajuste, no cero", () => {
    const vacio = { ...base, factor_nr: "", factor_r: "" };
    expect(parametrosDeLaCorrida(vacio, fechas, null).factor_prospectivo).toEqual({
      "NO-RELACIONADOS": 1,
      RELACIONADOS: 1,
    });
  });
});

describe("factorProspectivoDeclarado", () => {
  it("acepta la coma decimal que escribe el usuario", () => {
    expect(factorProspectivoDeclarado({ factor_nr: "1,25", factor_r: "" })).toEqual({
      "NO-RELACIONADOS": 1.25,
      RELACIONADOS: 1,
    });
  });

  it("lo que no es un número no se convierte en cero: queda en 1,000", () => {
    expect(factorProspectivoDeclarado({ factor_nr: "mucho", factor_r: "1.1" })).toEqual({
      "NO-RELACIONADOS": 1,
      RELACIONADOS: 1.1,
    });
  });
});

describe("tasasSustitutasDeclaradas", () => {
  it("descarta la fila sin justificación escrita: el backend la ignoraría igual", () => {
    const filas = [{ segmento: "RELACIONADOS", banda: "Por vencer", tasa: "10", justificacion: "  " }];
    expect(tasasSustitutasDeclaradas(filas)).toEqual({});
  });

  it("descarta la fila sin banda o sin tasa", () => {
    expect(
      tasasSustitutasDeclaradas([
        { segmento: "RELACIONADOS", banda: "", tasa: "10", justificacion: "x" },
        { segmento: "RELACIONADOS", banda: "Por vencer", tasa: "", justificacion: "x" },
      ])
    ).toEqual({});
  });

  it("cuenta cuántas filas quedaron incompletas para poder declararlo", () => {
    const filas = [
      { segmento: "RELACIONADOS", banda: "Por vencer", tasa: "10", justificacion: "" },
      { segmento: "RELACIONADOS", banda: "0 a 30 días", tasa: "20", justificacion: "ok" },
    ];
    expect(filasIncompletas(filas, tasaSustitutaCompleta)).toBe(1);
  });
});

describe("evaluacionesIndividualesDeclaradas", () => {
  it("descarta la fila sin cliente o sin justificación", () => {
    expect(
      evaluacionesIndividualesDeclaradas([
        { segmento: "NO-RELACIONADOS", cliente: "", ecl: "100", justificacion: "x" },
        { segmento: "NO-RELACIONADOS", cliente: "ALFA", ecl: "100", justificacion: "" },
      ])
    ).toEqual({});
  });

  it("conserva un importe de cero declarado: 0,00 medido no es un dato ausente", () => {
    const filas = [{ segmento: "NO-RELACIONADOS", cliente: "ALFA", ecl: "0", justificacion: "Garantía bancaria por el 100 % (PT D-2)." }];
    expect(evaluacionesIndividualesDeclaradas(filas)["NO-RELACIONADOS|ALFA"].ecl).toBe(0);
  });
});

describe("cotasDeLaCorrida", () => {
  it("sin cotas que hayan actuado, no dice nada", () => {
    const res = {
      exposicion: { medida_acotada: null, sin_medir_recortado: 0 },
      matriz: { ecl_acotada_por_piso: 0, ecl_acotada_por_techo: 0 },
      individual: { ecl_acotada_por_piso: 0, ecl_acotada_por_techo: 0 },
    };
    expect(cotasDeLaCorrida(res)).toEqual([]);
  });

  it("declara que la cartera medida se acotó, con la cifra sin acotar", () => {
    const res = {
      exposicion: {
        medida: 0, medida_sin_acotar: -350000, medida_acotada: "piso_cero",
        sin_medir_recortado: 0,
      },
    };
    const cotas = cotasDeLaCorrida(res);
    expect(cotas).toHaveLength(1);
    expect(cotas[0].clave).toBe("cartera_medida");
    expect(cotas[0].texto).toContain("350.000,00");
  });

  it("declara el recorte del saldo sin medir de los casos individuales", () => {
    const res = {
      exposicion: { medida_acotada: null, sin_medir_recortado: 100000 },
    };
    const cotas = cotasDeLaCorrida(res);
    expect(cotas.map((c) => c.clave)).toEqual(["saldo_sin_medir"]);
    expect(cotas[0].texto).toContain("100.000,00");
  });

  it("sin resultado todavía, no revienta", () => {
    expect(cotasDeLaCorrida(null)).toEqual([]);
  });

  it("una corrida antigua sin los campos no inventa que ninguna cota actuó", () => {
    expect(cotasDeLaCorrida({ exposicion: { total: 100 } })).toEqual([]);
  });
});

describe("factorProspectivoDeclarado", () => {
  it("un factor de cero es un error de entrada, no un ajuste", () => {
    expect(() => factorProspectivoDeclarado({ factor_nr: "0" })).toThrow(/0,000/);
  });

  it("un factor negativo también", () => {
    expect(() => factorProspectivoDeclarado({ factor_r: "-1" })).toThrow(/0,000/);
  });

  it("vacío sigue siendo 1,000 (sin ajuste)", () => {
    expect(factorProspectivoDeclarado({})).toEqual({
      "NO-RELACIONADOS": 1,
      RELACIONADOS: 1,
    });
  });
});

describe("archivosQueSuperanElLimite", () => {
  const limites = { max_bytes_por_archivo: 7 * 1024 * 1024, max_mb_por_archivo: 7 };

  it("sin límites consultados todavía, no acusa a ningún archivo", () => {
    expect(archivosQueSuperanElLimite([{ name: "a.xlsx", size: 99e6 }], null)).toEqual([]);
  });

  it("nombra los archivos que superan el límite, con su tamaño", () => {
    const archivos = [
      { name: "cartera_2023.xlsx", size: 1e6 },
      { name: "cartera_2025.xlsx", size: 16 * 1024 * 1024 },
    ];
    const fuera = archivosQueSuperanElLimite(archivos, limites);
    expect(fuera).toHaveLength(1);
    expect(fuera[0].nombre).toBe("cartera_2025.xlsx");
    expect(fuera[0].mb).toBe("16,0");
  });

  it("un archivo exactamente en el límite pasa", () => {
    expect(
      archivosQueSuperanElLimite([{ name: "x.xlsx", size: 7 * 1024 * 1024 }], limites)
    ).toEqual([]);
  });

  it("tolera huecos: un corte sin archivo todavía no es un archivo grande", () => {
    expect(archivosQueSuperanElLimite([null, undefined], limites)).toEqual([]);
  });
});
