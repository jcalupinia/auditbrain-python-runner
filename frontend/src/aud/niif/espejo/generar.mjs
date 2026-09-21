// Genera backend/app/aud/niif/ciclo/espejo.json: lo que responden las reglas del
// sitio (copia intacta de domain.mjs) ante casos fijos.
//
//   node frontend/src/aud/niif/espejo/generar.mjs
//
// El backend del portal es Python y porta esas reglas a mano. Para que el
// puerto no dependa de la buena fe de nadie:
//   - pytest exige que Python dé exactamente lo que dice espejo.json;
//   - vitest (espejo.test.js) vuelve a generar el contenido y falla si el
//     archivo guardado ya no coincide con el JavaScript del sitio.
// Si el sitio cambia una regla y se vuelve a copiar domain.mjs, vitest se
// pone rojo hasta regenerar; y al regenerar, pytest se pone rojo hasta portar
// el cambio a Python.
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { CAN_APPROVE, STATES, catalog, createProgram, transition } from "../sitio/tools/domain.mjs";

export const DESTINO = fileURLToPath(new URL("../../../../../backend/app/aud/niif/ciclo/espejo.json", import.meta.url));
// El catálogo lo usa el servidor en funcionamiento, no solo las pruebas: va aparte.
export const CATALOGO = fileURLToPath(new URL("../../../../../backend/app/aud/niif/ciclo/catalogo.json", import.meta.url));
export const catalogoJson = () => JSON.stringify(catalog, null, 1) + "\n";

const intentar = (fn) => {
  try {
    return { ok: fn() };
  } catch (e) {
    return { error: e.message };
  }
};

// Una definición «custom» sin `description`, como las que salen del Diseñador.
const CUSTOM = {
  id: "custom",
  name: "Arrendamientos NIIF 16",
  area: "Arrendamientos",
  fields: [{ key: "id", label: "Contrato", type: "text" }, { key: "pago", label: "Pago", type: "number" }],
  rules: [{ key: "x", label: "x", op: "add", a: "pago", b: "#0", precision: 2 }],
  control: "pago",
  primary: "x",
};

const PROGRAMA_OK = [{ code: "VNR-01" }];

// Cada caso: estado de partida, acción, rol y lo que la regla exige mirar.
function casosTransicion() {
  const base = { state: "PRUEBA_SELECCIONADA" };
  const casos = [];
  const acciones = [
    ["generate_program", "PRUEBA_SELECCIONADA"],
    ["approve_program", "PROGRAMA_PROPUESTO"],
    ["generate_request", "PROGRAMA_APROBADO"],
    ["approve_request", "REQUERIMIENTO_GENERADO"],
    ["validate", "DOCUMENTACION_RECIBIDA"],
    ["configure", "DOCUMENTACION_VALIDADA"],
    ["approve_methodology", "PRUEBA_CONFIGURADA"],
    ["execute", "METODOLOGIA_APROBADA"],
    ["analyze", "PRUEBA_EJECUTADA"],
    ["submit", "RESULTADOS_ANALIZADOS"],
    ["approve", "EN_REVISION"],
  ];
  const listo = {
    program: PROGRAMA_OK,
    sourcesVerified: true,
    validation: { ok: true },
    reconciliation: { resolved: true },
    run: { rows: [] },
    analysis: "a",
    conclusion: "c",
    conclusionReviewed: true,
    notes: [],
  };
  for (const [accion, desde] of acciones) {
    for (const rol of ["ADMIN", "PREPARADOR"]) {
      casos.push({ t: { ...listo, state: desde }, accion, rol });
    }
    // Desde un estado que no le corresponde.
    casos.push({ t: { ...listo, state: desde === "PRUEBA_SELECCIONADA" ? "PROGRAMA_APROBADO" : "PRUEBA_SELECCIONADA" }, accion, rol: "ADMIN" });
  }
  // Requisitos de cada acción, uno por uno.
  casos.push({ t: { ...listo, state: "PROGRAMA_PROPUESTO", program: [] }, accion: "approve_program", rol: "ADMIN" });
  casos.push({ t: { ...listo, state: "PROGRAMA_PROPUESTO", sourcesVerified: false }, accion: "approve_program", rol: "ADMIN" });
  casos.push({ t: { ...listo, state: "DOCUMENTACION_RECIBIDA", validation: { ok: false } }, accion: "validate", rol: "ADMIN" });
  casos.push({ t: { ...listo, state: "DOCUMENTACION_RECIBIDA", reconciliation: { resolved: false } }, accion: "validate", rol: "ADMIN" });
  casos.push({ t: { ...listo, state: "METODOLOGIA_APROBADA", validation: null }, accion: "execute", rol: "ADMIN" });
  for (const falta of ["run", "analysis", "conclusion", "conclusionReviewed", "validation", "reconciliation"]) {
    const t = { ...listo, state: "EN_REVISION" };
    t[falta] = falta === "conclusionReviewed" ? false : falta === "validation" ? { ok: false } : falta === "reconciliation" ? { resolved: false } : falta === "run" ? null : " ";
    casos.push({ t, accion: "approve", rol: "ADMIN" });
  }
  casos.push({ t: { ...listo, state: "EN_REVISION", notes: [{ status: "ABIERTO", response: "" }] }, accion: "approve", rol: "ADMIN" });
  casos.push({ t: { ...listo, state: "EN_REVISION", notes: [{ status: "RESUELTO", response: " " }] }, accion: "approve", rol: "ADMIN" });
  casos.push({ t: { ...listo, state: "APROBADO" }, accion: "approve", rol: "ADMIN" });
  casos.push({ t: { ...base }, accion: "inventada", rol: "ADMIN" });
  return casos.map((c) => ({ ...c, esperado: intentar(() => transition(c.t, c.accion, c.rol)) }));
}

export function contenido() {
  return {
    _origen: "Generado por frontend/src/aud/niif/espejo/generar.mjs desde la copia intacta de domain.mjs. No editar a mano.",
    estados: STATES,
    pueden_aprobar: CAN_APPROVE,
    catalogo: catalog,
    programas: [
      { definicion: "vnr", marco: "NIIF completas", esperado: createProgram(catalog.vnr, { framework: "NIIF completas" }) },
      { definicion: "vnr", marco: "NIIF para las PYMES", esperado: createProgram(catalog.vnr, { framework: "NIIF para las PYMES" }) },
      { definicion: "pce", marco: "NIIF completas", esperado: createProgram(catalog.pce, { framework: "NIIF completas" }) },
      { definicion: CUSTOM, marco: "NIIF completas", esperado: createProgram(CUSTOM, { framework: "NIIF completas" }) },
    ],
    transiciones: casosTransicion(),
  };
}

export const serializar = (c) => JSON.stringify(c, null, 1) + "\n";

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const c = contenido();
  writeFileSync(DESTINO, serializar(c));
  writeFileSync(CATALOGO, catalogoJson());
  console.log(`espejo.json: ${c.programas.length} programas, ${c.transiciones.length} transiciones`);
}
