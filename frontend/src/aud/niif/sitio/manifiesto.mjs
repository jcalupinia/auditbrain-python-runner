// Regenera MANIFIESTO.json tras copiar archivos nuevos del sitio:
//   node src/aud/niif/sitio/manifiesto.mjs <commit-del-sitio>
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { sep } from "node:path";
import { fileURLToPath } from "node:url";

import { huella } from "./huella.js";

const DIR = fileURLToPath(new URL("./", import.meta.url));
const commit = process.argv[2] || "desconocido";
const m = {
  origen: `auditbrain-site @ ${commit} · lib/tools/*.mjs -> tools/, lib/*.mjs -> raíz (huellas sobre texto con LF)`,
  sha256: {},
};
for (const f of readdirSync(DIR, { recursive: true })
  .map((f) => String(f).split(sep).join("/"))
  .filter((f) => /\.(mjs|ts)$/.test(f) && f !== "manifiesto.mjs" && f !== "audit-store.ts")
  .sort())
  m.sha256[f] = huella(readFileSync(DIR + f, "utf8"));
writeFileSync(DIR + "MANIFIESTO.json", JSON.stringify(m, null, 2) + "\n");
console.log(Object.keys(m.sha256).length, "huellas:", Object.keys(m.sha256).join(" "));
