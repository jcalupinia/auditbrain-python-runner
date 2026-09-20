import { describe, expect, it } from "vitest";
import {
  ESTADO_EN_DISENO,
  fichaParaEditar,
  fichaVacia,
  gruposAlternativos,
  itemVacio,
  prepararParaGuardar,
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
