import { describe, it, expect } from "vitest";

import {
  agruparPorRubro,
  filtrarPruebas,
  columnasDe,
  filaVacia,
  filaEstaVacia,
  filasDesdeMolde,
  gridInicial,
  cuerpoEjecucion,
  faltantesParaEjecutar,
} from "./pilotoLogic.js";

const PRUEBAS = [
  { id: "efectivo_equivalentes", nombre: "Efectivo y equivalentes", rubro: "CAJA_BANCOS" },
  { id: "cxc_cartera", nombre: "Cuentas por cobrar y deterioro", rubro: "CXC" },
  { id: "arrendamientos", nombre: "Arrendamientos", rubro: "ARRENDAMIENTOS" },
  { id: "perdidas_incurridas_s11", nombre: "Deterioro · pérdidas incurridas", rubro: "" },
];

const REQ = {
  datasets: [
    { dataset: "contratos", es_principal: true, campos: [
      { key: "id", label: "Contrato" }, { key: "pago", label: "Pago" },
    ] },
  ],
};

describe("agruparPorRubro", () => {
  it("agrupa conservando el orden y usa 'General' para rubro vacío", () => {
    const g = agruparPorRubro(PRUEBAS);
    expect(g.map((x) => x.rubro)).toEqual(["CAJA_BANCOS", "CXC", "ARRENDAMIENTOS", "General"]);
    expect(g[3].pruebas[0].id).toBe("perdidas_incurridas_s11");
  });
});

describe("filtrarPruebas", () => {
  it("filtra por id/nombre/rubro sin tildes ni mayúsculas", () => {
    expect(filtrarPruebas(PRUEBAS, "cartera").map((p) => p.id)).toEqual(["cxc_cartera"]);
    expect(filtrarPruebas(PRUEBAS, "PÉRDIDAS").map((p) => p.id)).toEqual(["perdidas_incurridas_s11"]);
    expect(filtrarPruebas(PRUEBAS, "").length).toBe(4);
  });
});

describe("columnas y filas", () => {
  it("columnasDe y filaVacia derivan de los campos", () => {
    expect(columnasDe(REQ.datasets[0])).toEqual(["id", "pago"]);
    expect(filaVacia(REQ.datasets[0])).toEqual({ id: "", pago: "" });
  });
  it("filaEstaVacia detecta filas sin datos", () => {
    expect(filaEstaVacia({ id: "", pago: "  " })).toBe(true);
    expect(filaEstaVacia({ id: "C-01", pago: "" })).toBe(false);
  });
});

describe("filasDesdeMolde", () => {
  it("conserva solo las columnas declaradas e ignora claves extra", () => {
    const molde = { datasets: { contratos: [{ id: "C-01", pago: 1500, extra: "x" }] } };
    const out = filasDesdeMolde(REQ, molde);
    expect(out.contratos).toEqual([{ id: "C-01", pago: 1500 }]);
  });
  it("si el molde no trae filas, deja una vacía", () => {
    expect(filasDesdeMolde(REQ, { datasets: {} }).contratos).toEqual([{ id: "", pago: "" }]);
  });
});

describe("gridInicial", () => {
  it("una fila vacía por dataset", () => {
    expect(gridInicial(REQ)).toEqual({ contratos: [{ id: "", pago: "" }] });
  });
});

describe("cuerpoEjecucion", () => {
  it("descarta filas vacías y parámetros/encargo vacíos", () => {
    const cuerpo = cuerpoEjecucion({
      corte: "2025-12-31 ",
      grid: { contratos: [{ id: "C-01", pago: 1500 }, { id: "", pago: "" }] },
      parametros: { umbralVida: 75, tasa: "" },
      encargo: { client: "ACME", ruc: "" },
    });
    expect(cuerpo.corte).toBe("2025-12-31");
    expect(cuerpo.datasets.contratos).toHaveLength(1);
    expect(cuerpo.parametros).toEqual({ umbralVida: 75 });
    expect(cuerpo.encargo).toEqual({ client: "ACME" });
  });
  it("omite 'encargo' cuando no hay ningún campo", () => {
    const cuerpo = cuerpoEjecucion({ corte: "2025-12-31", grid: {}, parametros: {}, encargo: {} });
    expect(cuerpo.encargo).toBeUndefined();
  });
});

describe("faltantesParaEjecutar", () => {
  it("exige corte y al menos una fila", () => {
    expect(faltantesParaEjecutar({ corte: "", datasets: {} })).toEqual([
      "la fecha de corte", "al menos una fila de datos",
    ]);
    expect(faltantesParaEjecutar({ corte: "2025-12-31", datasets: { c: [{}] } })).toEqual([]);
  });
});
