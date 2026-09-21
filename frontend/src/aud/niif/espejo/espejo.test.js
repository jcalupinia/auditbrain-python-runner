import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { CATALOGO, DESTINO, catalogoJson, contenido, serializar } from "./generar.mjs";

// Normaliza finales de línea: con core.autocrlf=true el archivo puede salir con
// CRLF según la máquina.
const leer = (ruta) => readFileSync(ruta, "utf8").replace(/\r\n/g, "\n");

describe("espejo de las reglas del sitio para el backend Python", () => {
  it("espejo.json está al día con la copia de domain.mjs", () => {
    expect(leer(DESTINO), "regenere: node frontend/src/aud/niif/espejo/generar.mjs").toBe(serializar(contenido()));
  });

  it("catalogo.json está al día con la copia de domain.mjs", () => {
    expect(leer(CATALOGO), "regenere: node frontend/src/aud/niif/espejo/generar.mjs").toBe(catalogoJson());
  });

  it("cubre todos los mensajes de error de la máquina de estados", () => {
    const errores = new Set(contenido().transiciones.map((c) => c.esperado.error).filter(Boolean));
    expect(errores.size).toBe(7);
  });
});
