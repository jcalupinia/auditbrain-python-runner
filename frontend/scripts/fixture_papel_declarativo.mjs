// Genera los datos de ejemplo del papel declarativo que usan las pruebas de
// Python (tests/fixtures/papel_declarativo/*.json): lo mismo que el navegador
// envía al servidor (cargaPapel) para una herramienta del catálogo (VNR) y una
// ficha con serie (NIIF 16). La prueba papelDeclarativo.test.js falla si el
// exportador del sitio cambia y estos archivos quedan desactualizados.
//
//   node frontend/scripts/fixture_papel_declarativo.mjs
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { EJEMPLOS } from "../src/aud/niif/papelDeclarativo.ejemplos.js";

const destino = resolve(dirname(fileURLToPath(import.meta.url)), "../../tests/fixtures/papel_declarativo");
mkdirSync(destino, { recursive: true });
for (const [nombre, carga] of Object.entries(EJEMPLOS())) {
  writeFileSync(resolve(destino, `${nombre}.json`), JSON.stringify(carga, null, 1) + "\n");
  console.log(`${nombre}.json: ${carga.cedulas.nombres.length} cédulas`);
}
