import { strFromU8, unzipSync } from "fflate";
import { describe, expect, it } from "vitest";

import { herramientaDeEstudio } from "./contraste";
import { EJEMPLO_NIIF16 } from "./estudioLogic";
import { bytesPowerPoint, bytesWord, htmlConAdjuntos, modeloPapel, papelDeclarativo, texto } from "./papelDeclarativo";
import { calculate } from "./sitio/tools/domain.mjs";
import { presentationExample } from "./sitio/tools/example.mjs";
import { buildWorkbook, sheetLabels, sheetNames } from "./sitio/tools/exports.mjs";

// Una herramienta del catálogo (VNR, con programa y fuentes) y una ficha con serie (NIIF 16).
const vnr = presentationExample();
const { definicion, filas } = EJEMPLO_NIIF16;
const niif16 = herramientaDeEstudio({ ficha: { nombre: "Arrendamientos" }, definicion, filas, run: calculate(definicion, filas, {}, []) });

const xml = (u8, prefijo) => {
  const z = unzipSync(u8);
  return Object.keys(z).filter((k) => k.startsWith(prefijo) && k.endsWith(".xml")).sort().map((k) => strFromU8(z[k])).join("\n");
};

describe("valores de celda en es-EC", () => {
  it("números, fechas y resultados de fórmula", () => {
    expect(texto("Costo")).toBe("Costo");
    expect(texto({ n: "1234.5" })).toBe("1.234,50");
    expect(texto({ n: "10" })).toBe("10");
    expect(texto({ n: 46022, date: true })).toBe("31/12/2025");
    expect(texto({ f: "SUM(A1:A3)", v: "470", type: "auto" })).toBe("470");
    expect(texto({ f: "A1*B1", v: "88.5", type: "auto" })).toBe("88,50");
    expect(texto({ f: "IF(A1=\"\",\"\",A1)", v: "0001", type: "text" })).toBe("0001");
    expect(texto({ f: "X", v: "", type: "auto" })).toBe("");
  });
});

describe("modelo del papel", () => {
  for (const [nombre, t] of [["VNR", vnr], ["NIIF 16", niif16]]) {
    it(`${nombre}: una cédula por hoja del Excel, sin repetir el encabezado como dato`, () => {
      const m = modeloPapel(t);
      expect(m.cedulas.map((c) => c.nombre)).toEqual(sheetNames(t.definition));
      expect(m.cedulas.map((c) => c.etiqueta)).toEqual(sheetLabels(t.definition));
      for (const c of m.cedulas.filter((x) => !x.portada && x.filas.length)) {
        expect(c.filas[0].celdas.map((x) => x.t)).not.toEqual(c.encabezado);
      }
      expect(m.kpis).toHaveLength(4);
    });
  }
});

describe("Word del papel declarativo", () => {
  it("es un .docx válido con todas las cédulas y los importes calculados en es-EC", async () => {
    const u8 = await bytesWord(vnr);
    expect(strFromU8(u8.subarray(0, 2))).toBe("PK");
    const doc = xml(u8, "word/document");
    expect(doc).toContain(vnr.definition.name);
    for (const etq of sheetLabels(vnr.definition).slice(1)) expect(doc).toContain(etq);
    expect(doc).toContain("470,00"); // costo total de la sumaria
    expect(doc).toContain("Cómo se prepara y calcula");
  });
});

describe("PowerPoint del papel declarativo", () => {
  it("es un .pptx válido con portada, resumen, cédulas clave y el detalle en el Excel", async () => {
    const u8 = await bytesPowerPoint(vnr);
    expect(strFromU8(u8.subarray(0, 2))).toBe("PK");
    const z = unzipSync(u8);
    const diapositivas = Object.keys(z).filter((k) => /^ppt\/slides\/slide\d+\.xml$/.test(k));
    expect(diapositivas.length).toBeGreaterThanOrEqual(8);
    const todo = xml(u8, "ppt/slides/slide");
    for (const txt of ["Resumen de la prueba", "Controles y conciliación", "Excepciones", "Sumaria de resultados", "Conclusión profesional", "Detalle completo en el Excel con fórmulas"]) {
      expect(todo).toContain(txt);
    }
  });

  it("también con una ficha con serie (cuadro de períodos)", async () => {
    const u8 = await bytesPowerPoint(niif16);
    expect(xml(u8, "ppt/slides/slide")).toContain("Cuadro de períodos");
  });
});

describe("HTML sin conexión con los demás formatos dentro", () => {
  it("lleva el Excel, el Word y el PowerPoint descargables y «Guardar como PDF», sin recursos remotos", async () => {
    const p = await papelDeclarativo(vnr);
    expect(Object.keys(p).sort()).toEqual(["docx", "html", "pptx", "xlsx"]);
    const h = p.html;
    expect(h).not.toMatch(/<(script|link|img)[^>]+(src|href)=["']https?:/i);
    expect(h).toContain("Guardar como PDF");
    for (const ext of ["xlsx", "docx", "pptx"]) expect(h).toMatch(new RegExp(`download="[^"]+\\.${ext}" href="data:application/`));
    // El Excel que viaja dentro es el mismo libro con fórmulas del exportador.
    const b64 = h.match(/download="[^"]+\.xlsx" href="data:[^;]+;base64,([^"]+)"/)[1];
    const dentro = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    expect(dentro).toEqual(buildWorkbook(vnr));
    expect(strFromU8(unzipSync(dentro)["xl/worksheets/sheet1.xml"])).toContain("<f>");
  });

  it("si el HTML del sitio cambia de botón, las descargas igual quedan dentro", () => {
    const h = htmlConAdjuntos({ ...vnr }, [["xlsx", "Excel", new Uint8Array([80, 75])]]);
    expect(h).toContain('href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,UEs="');
  });
});
