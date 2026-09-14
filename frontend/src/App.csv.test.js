// Tests de _csvEsc: escapa celdas CSV y neutraliza CSV injection (fórmulas)
// en datos que vienen de formularios públicos (registros de recursos, inscritos).

import { describe, expect, it } from "vitest";
import { _csvEsc } from "./App.jsx";

describe("_csvEsc", () => {
  it("antepone comilla a valores que empiezan con =", () => {
    expect(_csvEsc("=1+1")).toBe("'=1+1");
  });
  it("antepone comilla a valores que empiezan con +", () => {
    expect(_csvEsc("+593987")).toBe("'+593987");
  });
  it("antepone comilla a valores que empiezan con -", () => {
    expect(_csvEsc("-x")).toBe("'-x");
  });
  it("antepone comilla a valores que empiezan con @", () => {
    expect(_csvEsc("@SUM(A1)")).toBe("'@SUM(A1)");
  });
  it("escapa comillas dobles duplicándolas y envolviendo en comillas", () => {
    expect(_csvEsc('a"b')).toBe('"a""b"');
  });
  it("envuelve en comillas cuando hay coma", () => {
    expect(_csvEsc("a,b")).toBe('"a,b"');
  });
  it("convierte null a cadena vacía", () => {
    expect(_csvEsc(null)).toBe("");
  });
  it("deja intacto texto normal con acentos", () => {
    expect(_csvEsc("María")).toBe("María");
  });
});
