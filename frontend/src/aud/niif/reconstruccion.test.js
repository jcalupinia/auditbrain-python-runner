import { unzipSync, strFromU8 } from "fflate";
import { beforeAll, describe, expect, it } from "vitest";

import {
  adjuntarExterno,
  confirmarDiseno,
  importarDiagnostico,
  nuevoCaso,
  paquete,
  papelReconstruido,
} from "./reconstruccion";
import { EJEMPLO_NIIF16 } from "./estudioLogic";
import { herramientaDeEstudio } from "./contraste";
import { extractFile } from "./sitio/console/extract.mjs";
import { presentationExample } from "./sitio/tools/example.mjs";
import { calculate } from "./sitio/tools/domain.mjs";
import { buildWorkbook } from "./sitio/tools/exports.mjs";

const CONTEXTO = {
  framework: "NIIF completas", edition: "2025", country: "Ecuador", year: "2025",
  cutoff: "2025-12-31", currency: "USD", visit: "Final",
};

let original, extraction, caso;
beforeAll(async () => {
  // El «original» es un Excel real: el que arma el Estudio para NIIF 16.
  const { definicion, filas } = EJEMPLO_NIIF16;
  const bytes = buildWorkbook(herramientaDeEstudio({ definicion, filas, run: calculate(definicion, filas, {}, []) }));
  extraction = await extractFile(bytes, "original.xlsx");
  original = { name: "original.xlsx", sha256: "a".repeat(64) };
  caso = nuevoCaso({ context: CONTEXTO, tax: false, model: "Otro modelo", original, extraction, actor: "qa" });
});

// Un diagnóstico válido, como lo devolvería la IA siguiendo las instrucciones.
function diagnostico(cambios = {}) {
  const vnr = presentationExample();
  const review = {
    context: { framework: "NIIF completas", edition: "2025", country: "Ecuador", year: "2025", cutoff: "2025-12-31" },
    summary: "Libro de arrendamiento revisado hoja por hoja.",
    coverage: caso.original.sheets.map((s) => ({ sheet: s.name, reviewed: true, notes: "Revisada" })),
    sources: [
      { id: "S1", category: "NIIF", organization: "IFRS Foundation", document: "NIC 2", section: "§ 9", edition: "2025", date: "vigente", url: "https://www.ifrs.org/" },
      { id: "S2", category: "NIA", organization: "IAASB", document: "NIA 540", section: "§ 13", edition: "2025", date: "vigente", url: "https://www.iaasb.org/" },
    ],
    findings: [{ id: "F1", category: "NIIF", status: "Parcial", location: "07_Calculos!B5", observation: "x", correction: "y", sourceIds: ["S1"] }],
    changes: [{ schedule: "07_Calculos", action: "Conservar", reason: "Correcta" }],
    limitations: ["Sin recálculo del original."],
    methodology: "Revisión de fórmulas contra la norma.",
    design: { kind: "vnr", parameters: { basis: "Catálogo VNR" }, rows: vnr.rows.map(({ _file, _sheet, _row, ...r }) => r) },
    ...cambios,
  };
  return JSON.stringify({ caseId: caso.id, sourceSha256: original.sha256, review });
}

describe("expediente", () => {
  it("se abre con el original leído, hoja por hoja", () => {
    expect(caso.state).toBe("EN_REVISION");
    expect(caso.original.sheets).toHaveLength(13);
  });

  it("solo acepta un XLSX", () => {
    expect(() => nuevoCaso({ context: CONTEXTO, original: { name: "x.pdf", sha256: "b" }, extraction, actor: "qa" })).toThrow(/XLSX/);
  });

  it("el paquete para la IA lleva las instrucciones del sitio y marca la extracción como no confiable", () => {
    const p = paquete(caso, extraction);
    expect(p.instructions).toMatch(/REVISAR Y RECONSTRUIR UNA PRUEBA EXCEL/);
    expect(p.instructions).toContain(original.sha256);
    expect(p.contentIsUntrusted).toBe(true);
  });
});

describe("importar el diagnóstico", () => {
  it("acepta uno válido y pasa a DIAGNOSTICO", () => {
    const r = importarDiagnostico(caso, diagnostico());
    expect(r.state).toBe("DIAGNOSTICO");
    expect(r.revision).toBe(2);
  });

  it("rechaza la respuesta de otro archivo original", () => {
    const otro = JSON.parse(diagnostico());
    otro.sourceSha256 = "b".repeat(64);
    expect(() => importarDiagnostico(caso, JSON.stringify(otro))).toThrow(/otro archivo original/);
  });

  it("exige la cobertura de cada hoja, incluso las no revisadas", () => {
    const pocas = caso.original.sheets.slice(1).map((s) => ({ sheet: s.name, reviewed: true, notes: "x" }));
    expect(() => importarDiagnostico(caso, diagnostico({ coverage: pocas }))).toThrow(/cobertura de cada hoja/);
  });

  it("un hallazgo no puede citar una fuente inexistente", () => {
    const f = [{ id: "F1", category: "FORMULAS", status: "Cumple", location: "a", observation: "b", correction: "c", sourceIds: ["S9"] }];
    expect(() => importarDiagnostico(caso, diagnostico({ findings: f }))).toThrow(/fuente inexistente/);
  });

  it("un hallazgo normativo evaluado cita una fuente de su categoría", () => {
    const f = [{ id: "F1", category: "NIA", status: "Cumple", location: "a", observation: "b", correction: "c", sourceIds: ["S1"] }];
    expect(() => importarDiagnostico(caso, diagnostico({ findings: f }))).toThrow(/fuente de su categoría/);
  });

  it("el contexto tiene que ser el del encargo", () => {
    const ctx = { framework: "NIIF para las PYMES", edition: "2025", country: "Ecuador", year: "2025", cutoff: "2025-12-31" };
    expect(() => importarDiagnostico(caso, diagnostico({ context: ctx }))).toThrow(/framework/);
  });

  it("un JSON con la forma equivocada nombra el campo", () => {
    expect(() => importarDiagnostico(caso, diagnostico({ summary: "" }))).toThrow(/summary/);
  });
});

describe("confirmar el diseño y reconstruir", () => {
  it("exige confirmación y un comentario de al menos 15 caracteres", () => {
    const r = importarDiagnostico(caso, diagnostico());
    expect(() => confirmarDiseno(r, { confirmed: true, comment: "corto", actor: "qa" })).toThrow(/documente/);
    expect(() => confirmarDiseno(r, { confirmed: false, comment: "Revisado y conforme con el plan", actor: "qa" })).toThrow();
  });

  it("con impuestos exige también sustento TRIBUTARIO", () => {
    const conTributos = { ...caso, tax: true };
    const r = importarDiagnostico(conTributos, diagnostico());
    expect(() => confirmarDiseno(r, { confirmed: true, comment: "Revisado y conforme con el plan", actor: "qa" })).toThrow(/TRIBUTARIA/);
  });

  it("genera el papel VNR como borrador, con el cálculo del motor", () => {
    const r = confirmarDiseno(importarDiagnostico(caso, diagnostico()), { confirmed: true, comment: "Revisado y conforme con el plan", actor: "qa" });
    const { snapshot, plantilla, run } = papelReconstruido(r);
    expect(plantilla).toBe(false);
    expect(run.totals.impairment).toBe("82.00");
    const zip = unzipSync(buildWorkbook(snapshot, plantilla));
    expect(strFromU8(zip["xl/worksheets/sheet1.xml"])).toMatch(/Borrador/i);
  });

  it("sin diseño determinista exige adjuntar un Excel externo, distinto del original", () => {
    const r = confirmarDiseno(importarDiagnostico(caso, diagnostico({ design: null })), { confirmed: true, comment: "Revisado y conforme con el plan", actor: "qa" });
    expect(() => papelReconstruido(r)).toThrow(/externamente/);
    expect(() => adjuntarExterno(r, { name: "nuevo.xlsx", sha256: original.sha256, extraction })).toThrow(/distinta del original/);
    const hecho = adjuntarExterno(r, { name: "nuevo.xlsx", sha256: "c".repeat(64), extraction });
    expect(hecho.state).toBe("RECONSTRUIDA");
    expect(hecho.result.formulaCount).toBe(extraction.formulaCount);
  });
});
