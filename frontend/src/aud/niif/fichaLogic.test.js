import { describe, expect, it } from "vitest";
import {
  ESTADO_EN_DISENO,
  ESTADO_ENVIADA,
  ESTADO_PROBADA,
  esEditable,
  fichaParaEditar,
  fichaVacia,
  gruposAlternativos,
  idCatalogo,
  itemVacio,
  moduloCatalogo,
  nombreArchivoEncargo,
  nombreCamel,
  nombrePascal,
  prepararParaGuardar,
  puedeGenerarCodigo,
  textoEncargo,
  upsertFicha,
  validarFicha,
} from "./fichaLogic.js";

function fichaCompleta() {
  return {
    nombre: "Valor neto de realización de inventarios",
    rubro: "INVENTARIOS",
    norma: "NIC 2",
    parrafo: "§ 9, 28-33",
    items: [
      { ...itemVacio(), que_se_pide: "Kárdex valorado al corte", formatos: ["xlsx"], componentes: 12 },
    ],
    salidas: [{ nombre: "Cédula de VNR", formatos: ["excel", "html"] }],
  };
}

describe("validarFicha", () => {
  it("la ficha vacía reporta identificación, ítems y salidas incompletos", () => {
    const errores = validarFicha(fichaVacia());
    expect(errores.length).toBeGreaterThan(0);
    expect(errores.join(" ")).toContain("nombre de la prueba");
    expect(errores.join(" ")).toContain("al menos un ítem");
    expect(errores.join(" ")).toContain("al menos una cédula");
  });

  it("una ficha completa no tiene errores", () => {
    expect(validarFicha(fichaCompleta())).toEqual([]);
  });

  it("exige formatos aceptados en cada ítem", () => {
    const f = fichaCompleta();
    f.items[0].formatos = [];
    expect(validarFicha(f).join(" ")).toContain("formato aceptado");
  });

  it("rechaza un grupo de fuentes alternativas con un solo ítem", () => {
    const f = fichaCompleta();
    f.items[0].grupo_alternativas = "Saldo de inventario";
    expect(validarFicha(f).join(" ")).toContain("fuentes alternativas");
  });

  it("acepta el grupo cuando hay dos fuentes", () => {
    const f = fichaCompleta();
    f.items[0].grupo_alternativas = "Saldo de inventario";
    f.items.push({
      ...itemVacio(),
      que_se_pide: "Mayor de inventarios",
      formatos: ["pdf"],
      grupo_alternativas: "Saldo de inventario",
    });
    expect(validarFicha(f)).toEqual([]);
  });

  it("exige al menos un componente por ítem", () => {
    const f = fichaCompleta();
    f.items[0].componentes = 0;
    expect(validarFicha(f).join(" ")).toContain("1 componente");
  });

  it("ignora las filas en blanco al contar ítems y salidas", () => {
    const f = fichaCompleta();
    f.items.push(itemVacio());
    f.salidas.push({ nombre: "   ", formatos: [] });
    expect(validarFicha(f)).toEqual([]);
  });
});

describe("gruposAlternativos", () => {
  it("agrupa solo los ítems que declaran grupo y recorta espacios", () => {
    const grupos = gruposAlternativos([
      { que_se_pide: "a", grupo_alternativas: " Saldo " },
      { que_se_pide: "b", grupo_alternativas: "Saldo" },
      { que_se_pide: "c", grupo_alternativas: "" },
    ]);
    expect(Object.keys(grupos)).toEqual(["Saldo"]);
    expect(grupos.Saldo).toHaveLength(2);
  });
});

describe("prepararParaGuardar", () => {
  it("deja la herramienta en estado «en diseño» y descarta filas vacías", () => {
    const f = fichaCompleta();
    f.items.push(itemVacio());
    const g = prepararParaGuardar(f, "2026-09-19T10:00:00.000Z");
    expect(g.estado).toBe(ESTADO_EN_DISENO);
    expect(g.id).toBeTruthy();
    expect(g.items).toHaveLength(1);
    expect(g.items[0].componentes).toBe(12);
    expect(g.salidas[0].formatos).toEqual(["excel", "html"]);
  });

  it("conserva el id si la ficha ya lo tenía", () => {
    const g = prepararParaGuardar({ ...fichaCompleta(), id: "niif-1" }, "2026-09-19T10:00:00.000Z");
    expect(g.id).toBe("niif-1");
  });

  it("ida y vuelta: lo guardado se puede volver a editar", () => {
    const g = prepararParaGuardar(fichaCompleta(), "2026-09-19T10:00:00.000Z");
    const editable = fichaParaEditar(g);
    expect(editable.items[0].key).toBeTruthy();
    expect(editable.items[0].que_se_pide).toBe("Kárdex valorado al corte");
    expect(validarFicha(editable)).toEqual([]);
  });
});

describe("upsertFicha", () => {
  it("reemplaza por id y deja lo más reciente primero", () => {
    const vieja = { id: "a", actualizado: "2026-01-01T00:00:00.000Z" };
    const otra = { id: "b", actualizado: "2026-02-01T00:00:00.000Z" };
    const nueva = { id: "a", actualizado: "2026-03-01T00:00:00.000Z" };
    const lista = upsertFicha([vieja, otra], nueva);
    expect(lista.map((f) => f.id)).toEqual(["a", "b"]);
    expect(lista).toHaveLength(2);
    expect(lista[0].actualizado).toBe("2026-03-01T00:00:00.000Z");
  });
});

describe("idCatalogo", () => {
  it("sigue el molde de los ids existentes del catálogo", () => {
    expect(idCatalogo({ rubro: "IMPUESTOS", nombre: "Obligaciones fiscales" })).toBe(
      "AUD.IMPUESTOS.OBLIGACIONES_FISCALES"
    );
  });

  it("quita tildes y signos del nombre", () => {
    expect(idCatalogo({ rubro: "INVENTARIOS", nombre: "Valor neto de realización (VNR)" })).toBe(
      "AUD.INVENTARIOS.VALOR_NETO_DE_REALIZACION_VNR"
    );
  });

  it("deriva el módulo y el nombre del componente del mismo nombre", () => {
    const f = { nombre: "Valor neto de realización" };
    expect(moduloCatalogo(f)).toBe("valor_neto_de_realizacion");
    expect(nombrePascal(f.nombre)).toBe("ValorNetoDeRealizacion");
    expect(nombreCamel(f.nombre)).toBe("valorNetoDeRealizacion");
  });
});

describe("estados", () => {
  it("solo se edita mientras está en diseño", () => {
    expect(esEditable({ estado: ESTADO_EN_DISENO })).toBe(true);
    expect(esEditable({ estado: ESTADO_PROBADA })).toBe(false);
    expect(esEditable({ estado: ESTADO_ENVIADA })).toBe(false);
  });

  it("el botón de generar código solo existe cuando la ficha está probada", () => {
    expect(puedeGenerarCodigo({ estado: ESTADO_EN_DISENO })).toBe(false);
    expect(puedeGenerarCodigo({ estado: ESTADO_PROBADA })).toBe(true);
    expect(puedeGenerarCodigo({ estado: ESTADO_ENVIADA })).toBe(false);
  });
});

describe("textoEncargo", () => {
  const RUBROS = [{ id: "INVENTARIOS", label: "Inventarios", type: "ciclo" }];

  function fichaGuardada() {
    return {
      id: 7,
      estado: ESTADO_PROBADA,
      nombre: "Valor neto de realización de inventarios",
      rubro: "INVENTARIOS",
      norma: "NIC 2 · Inventarios",
      parrafo: "§ 9, 28-33",
      autor_email: "autor@auditconsulting.ec",
      probada_por_email: "revisor@auditconsulting.ec",
      probada_en: "2026-09-19T10:00:00.000Z",
      items: [
        {
          que_se_pide: "Kárdex valorado al corte",
          formatos: ["xlsx", "csv"],
          obligatorio: true,
          componentes: 12,
          grupo_alternativas: "Saldo de inventario",
        },
        {
          que_se_pide: "Mayor de inventarios",
          formatos: ["pdf"],
          obligatorio: false,
          componentes: 1,
          grupo_alternativas: "Saldo de inventario",
        },
      ],
      salidas: [{ nombre: "Cédula de VNR por ítem", formatos: ["excel", "html"] }],
    };
  }

  it("lleva el ciclo y el identificador de catálogo", () => {
    const t = textoEncargo(fichaGuardada(), RUBROS);
    expect(t).toContain("AUD.INVENTARIOS.VALOR_NETO_DE_REALIZACION_DE_INVENTARIOS");
    expect(t).toContain("Inventarios");
    expect(t).toContain("frontend/src/aud/catalog.js");
  });

  it("lleva la ficha completa: norma, párrafo, ítems y salidas", () => {
    const t = textoEncargo(fichaGuardada(), RUBROS);
    expect(t).toContain("NIC 2 · Inventarios");
    expect(t).toContain("§ 9, 28-33");
    expect(t).toContain("Kárdex valorado al corte");
    expect(t).toContain("Mayor de inventarios");
    expect(t).toContain("Cédula de VNR por ítem");
  });

  it("declara formatos, obligatoriedad, componentes y el grupo de alternativas", () => {
    const t = textoEncargo(fichaGuardada(), RUBROS);
    expect(t).toContain("Excel (.xlsx / .xls)");
    expect(t).toContain("**Obligatorio:** sí");
    expect(t).toContain("**Obligatorio:** no (opcional)");
    expect(t).toContain("**Componentes esperados:** 12");
    expect(t).toContain("Saldo de inventario");
    expect(t).toContain("Grupos de fuentes alternativas");
  });

  it("dice qué archivos crear y cuáles modificar, con rutas reales", () => {
    const t = textoEncargo(fichaGuardada(), RUBROS);
    expect(t).toContain("backend/app/aud/valor_neto_de_realizacion_de_inventarios/router.py");
    expect(t).toContain(
      "frontend/src/aud/valor_neto_de_realizacion_de_inventarios/" +
        "ValorNetoDeRealizacionDeInventariosTool.jsx"
    );
    expect(t).toContain("backend/app/api/__init__.py");
    expect(t).toContain("backend/app/db/session.py");
    expect(t).toContain("require_staff");
  });

  it("referencia el contrato de la estructura", () => {
    expect(textoEncargo(fichaGuardada(), RUBROS)).toContain(
      "docs/pruebas/ESTRUCTURA_HERRAMIENTA.md"
    );
  });

  it("deja constancia de quién diseñó y quién probó la ficha", () => {
    const t = textoEncargo(fichaGuardada(), RUBROS);
    expect(t).toContain("autor@auditconsulting.ec");
    expect(t).toContain("revisor@auditconsulting.ec");
    expect(t).toContain("2026-09-19");
  });

  it("el nombre de archivo sugerido sale del nombre de la prueba", () => {
    expect(nombreArchivoEncargo(fichaGuardada())).toBe(
      "encargo-valor-neto-de-realizacion-de-inventarios.md"
    );
  });
});
