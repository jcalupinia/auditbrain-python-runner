import { readFileSync, readdirSync } from "node:fs";
import { sep } from "node:path";
import { fileURLToPath } from "node:url";
import { unzipSync, strFromU8 } from "fflate";
import { describe, expect, it } from "vitest";

import { herramientaDeEstudio, motivoDiscrepancia } from "./contraste";
import { EJEMPLO_NIIF16 } from "./estudioLogic";
import { calculate } from "./sitio/tools/domain.mjs";
import { buildHtml, buildWorkbook, sheetNames } from "./sitio/tools/exports.mjs";
import { huella } from "./sitio/huella.js";

const DIR = fileURLToPath(new URL("./sitio/", import.meta.url));
const MANIFIESTO = JSON.parse(readFileSync(DIR + "MANIFIESTO.json", "utf8"));

describe("la copia del exportador del sitio", () => {
  it("no se editó en el portal: cada archivo coincide con su huella", () => {
    const archivos = readdirSync(DIR, { recursive: true })
      .map((f) => String(f).split(sep).join("/"))
      .filter((f) => f.endsWith(".mjs") && f !== "manifiesto.mjs")
      .sort();
    expect(archivos).toEqual(Object.keys(MANIFIESTO.sha256).sort());
    for (const f of archivos) {
      expect(huella(readFileSync(DIR + f, "utf8")), `${f} fue editado aquí; se cambia en el sitio`).toBe(
        MANIFIESTO.sha256[f]
      );
    }
  });
});

const { definicion, filas } = EJEMPLO_NIIF16;
const run = calculate(definicion, filas, {}, []);
const t = herramientaDeEstudio({ ficha: { nombre: "Arrendamientos" }, definicion, filas, run });

describe("cédulas del estudio", () => {
  it("con serie salen las trece, incluido el cuadro de períodos", () => {
    expect(sheetNames(definicion)).toHaveLength(13);
    expect(sheetNames(definicion)).toContain("13_Cuadro");
  });

  it("el Excel es un libro válido con una hoja por cédula", () => {
    const zip = unzipSync(buildWorkbook(t));
    const libro = strFromU8(zip["xl/workbook.xml"]);
    for (const n of sheetNames(definicion)) expect(libro).toContain(`name="${n}"`);
    expect(Object.keys(zip).filter((k) => k.startsWith("xl/worksheets/sheet"))).toHaveLength(13);
  });

  it("el libro sale marcado como borrador, nunca como papel aprobado", () => {
    const caratula = strFromU8(unzipSync(buildWorkbook(t))["xl/worksheets/sheet1.xml"]);
    expect(caratula).toMatch(/Borrador/i);
  });

  it("el HTML funciona sin internet: ningún script, hoja de estilo ni imagen remota", () => {
    const html = buildHtml(t);
    expect(html).not.toMatch(/<(script|link|img)[^>]+(src|href)=["']https?:/i);
  });
});

describe("contraste contra el motor Python", () => {
  const python = {
    engine: run.engine,
    rows: run.rows.map((r) => ({ ...r })),
    totals: { ...run.totals },
  };

  it("coinciden cuando los dos dan lo mismo", () => {
    expect(motivoDiscrepancia(run, python)).toBe("");
  });

  it("nombra la fila y el campo que difieren, sin importes", () => {
    const mal = structuredClone(python);
    mal.rows[0].pasivo_inicial = "1";
    const motivo = motivoDiscrepancia(run, mal);
    expect(motivo).toBe("fila 1, campos: pasivo_inicial");
    expect(motivo).not.toMatch(/\d{3}/);
  });

  it("una clave que Python añada de más tampoco pasa", () => {
    const extra = structuredClone(python);
    extra.totals.inventada = "0";
    expect(motivoDiscrepancia(run, extra)).toBe("totales: inventada");
  });

  it("detecta versiones distintas del motor", () => {
    expect(motivoDiscrepancia(run, { ...python, engine: "2.0.0" })).toMatch(/versión del motor/);
  });
});

describe("inspector de la consola de archivos", () => {
  it("lee el Excel que arma el propio exportador: hojas, fórmulas y valores guardados", async () => {
    const { extractFile, brief } = await import("./sitio/console/extract.mjs");
    const r = await extractFile(buildWorkbook(t), "estudio.xlsx");
    expect(brief(r).status).toBe("extracted");
    expect(r.sheets.map((s) => s.name)).toEqual(sheetNames(definicion));
    const calculos = r.sheets.find((s) => s.name === "07_Calculos");
    const b5 = calculos.formulas.find((f) => f.cell === "B5");
    expect(b5.formula).toMatch(/^IF\(COUNTA/);
    expect(b5.cached).toBe(run.rows[0].pasivo_inicial);
  });

  it("rechaza un ZIP con rutas que salen de la carpeta", async () => {
    const { zipSync, strToU8 } = await import("fflate");
    const { unpack } = await import("./sitio/console/extract.mjs");
    expect(() => unpack(zipSync({ "../fuera.txt": strToU8("x") }))).toThrow(/ruta no permitida/);
  });
});
