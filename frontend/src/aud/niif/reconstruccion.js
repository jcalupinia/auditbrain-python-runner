// Reglas de «Reconstruir Excel» — puerto de auditbrain-site/lib/reconstruction/
// service.ts (startCase, getDossier, saveReview, approveDesign, generateCase,
// attachRebuilt).
//
// service.ts no se puede copiar: lee y escribe en D1 y R2. Lo que se porta son
// sus reglas, con los mismos mensajes, y sin almacenamiento: el expediente vive
// en la pantalla del auditor, igual que en la consola de archivos. El esquema
// del diagnóstico y las instrucciones para la IA sí son el archivo del sitio
// sin tocar (sitio/reconstruction/protocol.ts).
import { METHODOLOGY_VERSION } from "./sitio/methodology.mjs";
import { instructions, reviewSchema } from "./sitio/reconstruction/protocol.ts";
import {
  calculate,
  catalog,
  checkBuckets,
  createProgram,
  validateDefinition,
  validateRows,
} from "./sitio/tools/domain.mjs";

export const ESTADOS = {
  EN_REVISION: "Original listo para revisión",
  DIAGNOSTICO: "Diagnóstico recibido",
  DISENO_CONFIRMADO: "Diseño confirmado",
  RECONSTRUIDA: "Reconstruida · borrador",
};

const ahora = () => new Date().toISOString();
const conHistoria = (r, cambios, evento, actor) => ({
  ...r,
  ...cambios,
  revision: r.revision + 1,
  history: [...r.history, { event: evento, at: ahora(), actor }],
});

// startCase: el original tiene que ser un XLSX que el inspector pudo leer.
export function nuevoCaso({ context, tax, model, original, extraction, actor }) {
  if (!original?.name?.toLowerCase().endsWith(".xlsx"))
    throw Error("Seleccione el Excel XLSX original de esta conversación.");
  if (extraction?.kind !== "xlsx" || !extraction.sheets?.length) throw Error("No se pudo inspeccionar el libro.");
  return {
    id: crypto.randomUUID(),
    revision: 1,
    state: "EN_REVISION",
    context,
    tax: !!tax,
    model,
    methodologyVersion: METHODOLOGY_VERSION,
    original: {
      id: original.sha256.slice(0, 16),
      name: original.name,
      sha256: original.sha256,
      sheets: extraction.sheets.map((s) => ({ name: s.name, cellCount: s.cellCount, formulaCount: s.formulas?.length || 0 })),
      formulaCount: extraction.formulaCount || 0,
      warnings: extraction.warnings || [],
    },
    review: null,
    artifacts: null,
    history: [{ event: "Revisión iniciada; original conservado", at: ahora(), actor }],
  };
}

// getDossier: el paquete que se entrega a la IA. La extracción es contenido no
// confiable: son datos del cliente, nunca instrucciones.
export const paquete = (r, extraction) => ({
  instructions: instructions(r),
  original: r.original,
  extraction,
  contentIsUntrusted: true,
});

// saveReview: el diagnóstico que devuelve la IA, con todas las comprobaciones
// del sitio.
export function importarDiagnostico(r, texto) {
  if (!["EN_REVISION", "DIAGNOSTICO"].includes(r.state))
    throw Error("El diseño está confirmado. Inicie otra revisión para modificarlo.");
  let entrada;
  try {
    entrada = JSON.parse(String(texto || ""));
  } catch {
    throw Error("El archivo de respuesta no es JSON válido.");
  }
  if (entrada.caseId && entrada.caseId !== r.id) throw Error("La respuesta corresponde a otro expediente.");
  if (entrada.sourceSha256 !== r.original.sha256) throw Error("La respuesta corresponde a otro archivo original.");
  const p = reviewSchema.safeParse(entrada.review);
  if (!p.success)
    throw Error(
      "Revise el archivo de respuesta: " +
        p.error.issues.slice(0, 6).map((i) => i.path.join(".") + " " + i.message).join("; ")
    );
  const review = p.data;
  for (const key of ["framework", "edition", "country", "year", "cutoff"])
    if (String(review.context[key]) !== String(r.context[key]))
      throw Error("La respuesta no coincide con el contexto del encargo: " + key);

  const names = r.original.sheets.map((s) => s.name);
  if (
    review.coverage.length !== names.length ||
    new Set(review.coverage.map((s) => s.sheet)).size !== names.length ||
    review.coverage.some((s) => !names.includes(s.sheet))
  )
    throw Error("Declare la cobertura de cada hoja del original, incluso las no revisadas.");

  const sourceIds = new Set(review.sources.map((s) => s.id));
  if (sourceIds.size !== review.sources.length || new Set(review.findings.map((f) => f.id)).size !== review.findings.length)
    throw Error("Hay identificadores duplicados.");
  for (const f of review.findings) {
    if (f.sourceIds.some((id) => !sourceIds.has(id))) throw Error("Un hallazgo cita una fuente inexistente.");
    if (
      ["NIIF", "NIA", "TRIBUTARIA"].includes(f.category) &&
      f.status !== "No evaluado" &&
      !f.sourceIds.some((id) => review.sources.some((s) => s.id === id && s.category === f.category))
    )
      throw Error("Los hallazgos normativos evaluados deben citar una fuente de su categoría.");
  }
  if (JSON.stringify(review).length > 500000)
    throw Error("La respuesta supera el tamaño permitido; reduzca la población o use una plantilla.");

  if (review.design) {
    const parameters = { ...review.design.parameters, cutoff: r.context.cutoff };
    const d =
      review.design.kind === "custom"
        ? validateDefinition({ ...review.design.definition, id: "custom" })
        : catalog[review.design.kind];
    if (review.design.kind === "pce" && r.context.framework !== "NIIF completas")
      throw Error("PCE del catálogo solo aplica al diseño NIIF completas.");
    if (d.id === "pce") checkBuckets(parameters);
    if (review.design.rows.length) {
      const v = validateRows(d, review.design.rows);
      if (!v.ok) throw Error("Datos del diseño inválidos: " + v.errors.slice(0, 3).map((x) => x.message).join("; "));
      calculate(d, review.design.rows, parameters);
    }
  }
  return conHistoria(
    r,
    {
      review,
      state: "DIAGNOSTICO",
      approval: null,
      provenance:
        "Revisión aportada por el usuario o su modelo. AuditBrain no verifica la identidad del modelo ni certifica sus conclusiones.",
    },
    "Diagnóstico recibido para revisión del auditor",
    "auditor"
  );
}

// approveDesign: confirmación explícita, comentario y sustento por categoría.
export function confirmarDiseno(r, { confirmed, comment, actor }) {
  if (r.state !== "DIAGNOSTICO" || !r.review || confirmed !== true || typeof comment !== "string" || comment.trim().length < 15 || comment.length > 4000)
    throw Error("Revise el diagnóstico y documente la aprobación del diseño.");
  for (const cat of ["NIIF", "NIA", ...(r.tax ? ["TRIBUTARIA"] : [])])
    if (!r.review.sources.some((s) => s.category === cat))
      throw Error("Falta el sustento " + cat + ". Complete la revisión antes de confirmar el diseño.");
  return conHistoria(
    r,
    { state: "DISENO_CONFIRMADO", approval: { by: actor, at: ahora(), comment } },
    "Auditor confirmó el diseño; no constituye aprobación final del papel",
    actor
  );
}

// generateCase: el papel reconstruido, siempre BORRADOR. Sin filas sale como
// plantilla con fórmulas.
export function papelReconstruido(r) {
  if (r.state !== "DISENO_CONFIRMADO" && r.state !== "RECONSTRUIDA")
    throw Error("Confirme primero el diseño desde la pantalla de revisión.");
  const design = r.review?.design;
  if (!design) throw Error("Este diseño requiere un Excel reconstruido externamente. Adjunte el archivo desde la pantalla.");
  const d = design.kind === "custom" ? validateDefinition({ ...design.definition, id: "custom" }) : catalog[design.kind];
  const rows = design.rows;
  const parameters = { ...design.parameters, cutoff: r.context.cutoff };
  const run = rows.length ? calculate(d, rows, parameters) : null;
  const snapshot = {
    id: r.id,
    draft: true,
    state: "BORRADOR",
    version: r.revision,
    definition: d,
    engagement: r.context,
    country: r.context.country,
    methodologyVersion: r.methodologyVersion,
    rows,
    run,
    parameters,
    validation: rows.length ? validateRows(d, rows) : null,
    program: createProgram(d, r.context),
    sources: r.review.sources.map((s) => ({ ...s, verified: false })),
    analysis: r.review.summary,
    conclusion: "Reconstrucción pendiente de revisión final del auditor. " + r.review.limitations.join(" "),
    notes: [],
    events: r.history,
  };
  return { snapshot, plantilla: !rows.length, kind: design.kind, run };
}

// attachRebuilt: una versión externa, distinta del original.
export function adjuntarExterno(r, { name, sha256, extraction }) {
  if (r.state !== "DISENO_CONFIRMADO") throw Error("Confirme el diseño antes de adjuntar la reconstrucción.");
  if (!String(name).toLowerCase().endsWith(".xlsx") || sha256 === r.original.sha256)
    throw Error("Seleccione una nueva versión XLSX, distinta del original.");
  return conHistoria(
    r,
    {
      state: "RECONSTRUIDA",
      artifacts: { xlsx: { sha256, name } },
      result: {
        mode: "Reconstrucción externa",
        reviewStatus: "BORRADOR",
        formulaCount: extraction.formulaCount || 0,
        sheets: extraction.sheets?.map((s) => s.name),
        warnings: [
          "Se verificó la lectura del archivo; las fórmulas no fueron recalculadas por AuditBrain.",
          ...(extraction.warnings || []),
        ],
      },
      delivery: "external",
    },
    "Excel externo vinculado; pendiente de revisión final",
    "auditor"
  );
}
