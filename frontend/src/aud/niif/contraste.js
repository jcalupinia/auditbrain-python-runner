// Contraste entre el motor autoridad (domain.mjs, en el navegador) y el motor
// Python del backend. Es la misma regla de app/api/tools/route.ts del sitio:
//
// - se recorre la UNIÓN de claves, así una clave que Python añada de más
//   tampoco pasa;
// - se contrastan filas y totales (los totales alimentan la sumaria);
// - el motivo nombra qué discrepó —clave y posición—, nunca importes del
//   cliente. Cuando faltaban las series, el mensaje mudo costó horas.
//
// Devuelve "" si coinciden; si no, el motivo.

const distintas = (x, y) =>
  [...new Set([...Object.keys(x || {}), ...Object.keys(y || {})])].filter(
    (k) => String(x?.[k]) !== String(y?.[k])
  );

export function motivoDiscrepancia(run, python) {
  if (!python) return "no llegó el resultado de Python";
  if (python.engine !== run.engine) return `versión del motor: el verificador usa ${run.engine}`;
  if (python.rows?.length !== run.rows.length)
    return `número de filas: ${run.rows.length} en el verificador y ${python.rows?.length ?? 0} en Python`;
  for (let i = 0; i < run.rows.length; i++) {
    const k = distintas(run.rows[i], python.rows[i]);
    if (k.length) return `fila ${i + 1}, campos: ${k.slice(0, 8).join(", ")}`;
  }
  const k = distintas(run.totals, python.totals);
  return k.length ? `totales: ${k.slice(0, 8).join(", ")}` : "";
}

// Objeto «herramienta» que esperan buildWorkbook/buildHtml del sitio. Sale
// siempre como BORRADOR: una corrida del estudio no es un papel aprobado.
export function herramientaDeEstudio({ ficha, definicion, filas, run, encargo = {} }) {
  const nombre = definicion.name || ficha?.nombre || "Prueba NIIF";
  return {
    definition: { ...definicion, name: nombre, area: definicion.area || ficha?.rubro || "" },
    version: 1,
    draft: true,
    state: "BORRADOR",
    country: "Ecuador",
    engagement: {
      firm: "Audit Consulting Group",
      client: encargo.client || "Cliente pendiente",
      year: encargo.year || "",
      cutoff: encargo.cutoff || "",
      preparer: encargo.preparer || "",
      reviewer: "",
    },
    parameters: {},
    reconciliation: { ledger: "0", tolerance: "0", difference: "0", within: true, acceptance: "" },
    program: [],
    sources: [],
    events: [],
    notes: [],
    rows: filas,
    run,
  };
}
