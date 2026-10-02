import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { cargaPapel, nombreBase } from "./papelDeclarativo";
import { EJEMPLOS, herramientasEjemplo } from "./papelDeclarativo.ejemplos";
import { sheetLabels, sheetNames, workbookSheets } from "./sitio/tools/exports.mjs";

// El papel declarativo lo arma el servidor con el diseño de los procesadores; el
// navegador solo envía las cédulas con fórmulas del exportador del sitio.
const FIX = resolve(dirname(fileURLToPath(import.meta.url)), "../../../../tests/fixtures/papel_declarativo");

describe("carga del papel declarativo", () => {
  const { vnr, niif16 } = herramientasEjemplo();

  for (const [nombre, t] of [["VNR", vnr], ["NIIF 16", niif16]]) {
    it(`${nombre}: las cédulas del sitio tal cual, con sus nombres y rótulos`, () => {
      const c = cargaPapel(t);
      expect(c.cedulas.nombres).toEqual(sheetNames(t.definition));
      expect(c.cedulas.etiquetas).toEqual(sheetLabels(t.definition));
      expect(c.cedulas.hojas).toEqual(workbookSheets(t));
      // La población y el detalle del motor ya viajan dentro de las cédulas.
      expect(c.herramienta.rows).toBeUndefined();
      expect(Object.keys(c.herramienta.run).sort()).toEqual(["engine", "exceptions", "totals"]);
      expect(c.herramienta.definition).toEqual(t.definition);
      // Se envía como JSON: nada se pierde al serializar.
      expect(JSON.parse(JSON.stringify(c))).toEqual(c);
    });
  }

  it("con serie lleva el cuadro de períodos", () => {
    expect(cargaPapel(niif16).cedulas.nombres).toContain("13_Cuadro");
  });

  it("nombre de archivo sin tildes ni espacios", () => {
    expect(nombreBase({ definition: { name: "Valor neto de realización" }, version: 2 })).toBe("Valor_neto_de_realizacion_v2");
  });
});

describe("datos de ejemplo de las pruebas de Python", () => {
  it("están al día con el exportador del sitio (regenerar con frontend/scripts/fixture_papel_declarativo.mjs)", () => {
    for (const [nombre, carga] of Object.entries(EJEMPLOS())) {
      const archivo = JSON.parse(readFileSync(resolve(FIX, `${nombre}.json`), "utf-8"));
      expect(archivo).toEqual(JSON.parse(JSON.stringify(carga)));
    }
  });
});
