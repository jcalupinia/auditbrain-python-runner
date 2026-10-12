import { describe, expect, it } from "vitest";
import { PAGINAS } from "./paginas.js";

// Coherencia del HITO 0: una página se marca `operativa` solo si tiene UI
// real cableada a un endpoint que el motor expone hoy. El bug que esto
// previene: `bases`, `sri` y `muestras` figuraban `operativa:false` pese a
// tener UI+lógica real y endpoints vivos en el motor (/muestreo,
// /trabajos/{id}/papel, /sri/*), mientras la portada anunciaba el tool como
// más incompleto de lo que estaba.
describe("paginas del motor analítico", () => {
  const operativas = PAGINAS.filter((p) => p.operativa).map((p) => p.id).sort();

  it("marca operativas exactamente las secciones con endpoint vivo", () => {
    expect(operativas).toEqual(["bases", "mayores", "muestras", "sri"]);
  });

  it("deja no operativas las secciones todavía en construcción", () => {
    const noOperativas = PAGINAS.filter((p) => !p.operativa).map((p) => p.id);
    for (const id of ["estados", "niif", "reportes", "agentes"]) {
      expect(noOperativas).toContain(id);
    }
  });

  it("cada página declara un id y un título", () => {
    for (const p of PAGINAS) {
      expect(typeof p.id).toBe("string");
      expect(p.id.length).toBeGreaterThan(0);
      expect(typeof p.titulo).toBe("string");
      expect(p.titulo.length).toBeGreaterThan(0);
    }
  });
});
