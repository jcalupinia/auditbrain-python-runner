import { describe, expect, it } from "vitest";
import {
  EJEMPLO_NIIF16,
  RECHAZADO,
  RECIBIDO,
  claveMarca,
  columnas,
  documentosDesdeMarcas,
  parsearJson,
  siguienteMarca,
} from "./estudioLogic";

describe("marcas del auditor → documentos del backend", () => {
  it("un componente recibido viaja con su componente", () => {
    const docs = documentosDesdeMarcas({ [claveMarca("i1", "Componente 3")]: RECIBIDO });
    expect(docs).toEqual([{ kind: "source", itemId: "i1", component: "Componente 3" }]);
  });

  it("un ítem sin componentes no manda componente", () => {
    const docs = documentosDesdeMarcas({ [claveMarca("i2")]: RECIBIDO });
    expect(docs).toEqual([{ kind: "source", itemId: "i2" }]);
  });

  it("un rechazado viaja marcado para que no tape el hueco", () => {
    const docs = documentosDesdeMarcas({ [claveMarca("i1", "Componente 1")]: RECHAZADO });
    expect(docs[0].state).toBe("rechazado");
  });

  it("lo desmarcado no se envía", () => {
    expect(documentosDesdeMarcas({ [claveMarca("i1")]: undefined })).toEqual([]);
  });
});

describe("ciclo de una marca", () => {
  it("nada → recibido → rechazado → nada", () => {
    expect(siguienteMarca(undefined)).toBe(RECIBIDO);
    expect(siguienteMarca(RECIBIDO)).toBe(RECHAZADO);
    expect(siguienteMarca(RECHAZADO)).toBeUndefined();
  });
});

describe("JSON escrito a mano", () => {
  it("dice en qué recuadro está el error", () => {
    expect(() => parsearJson("{mal", "Definición")).toThrow(/Definición/);
    expect(() => parsearJson("  ", "Filas")).toThrow(/vacío/);
  });

  it("devuelve el objeto cuando es válido", () => {
    expect(parsearJson('{"a":1}', "x")).toEqual({ a: 1 });
  });
});

describe("columnas de una tabla de resultados", () => {
  it("une las claves de todas las filas en orden de aparición", () => {
    expect(columnas([{ a: 1, b: 2 }, { b: 3, c: 4 }])).toEqual(["a", "b", "c"]);
  });
});

describe("el ejemplo NIIF 16", () => {
  it("es el mismo caso que contrasta el backend", () => {
    // Si alguien lo edita aquí sin tocar tests/test_aud_niif_motor.py, el
    // auditor vería un ejemplo que ya nadie verifica.
    expect(EJEMPLO_NIIF16.filas[0]).toEqual({ id: "L-001", pago: "10000", tasa: "0.06", n: "5", directos: "1200" });
    expect(EJEMPLO_NIIF16.definicion.series.count).toBe("n");
  });
});
