// Lógica pura del workspace de Obligaciones Fiscales.
//
// Se aísla deliberadamente de React/DOM para poder testearla con vitest
// (vitest.config.js corre en environment: "node"): ordenamiento de la tabla
// de revisión, cálculo de qué correcciones enviar, conteo de documentos
// subidos, y detección del job activo a retomar al montar el workspace.

// Orden de atención de la pantalla de revisión: lo dudoso primero, para que
// el auditor no tenga que buscar las cuentas de baja confianza entre las
// que el motor ya resolvió con seguridad.
const ORDEN_CONFIANZA = { baja: 0, media: 1, alta: 2 };

export function ordenarPorConfianza(cuentas) {
  return [...(cuentas || [])].sort((a, b) => {
    const oa = ORDEN_CONFIANZA[a.confianza] ?? 99;
    const ob = ORDEN_CONFIANZA[b.confianza] ?? 99;
    if (oa !== ob) return oa - ob;
    return String(a.codigo_cuenta || "").localeCompare(String(b.codigo_cuenta || ""));
  });
}

// "Requiere revisión" = todo lo que no sea confianza alta (media y baja).
export function contarRequierenRevision(cuentas) {
  return (cuentas || []).filter((c) => c.confianza !== "alta").length;
}

// `edits` es el mapa local { codigo_cuenta: categoriaElegida } que arma la
// pantalla de revisión mientras el auditor toca los selects. Esta función
// devuelve SOLO las que de verdad cambiaron respecto a categoria_final (lo
// que ya está guardado en el backend) — evita mandar correcciones inertes.
export function calcularCorrecciones(cuentas, edits) {
  const porCodigo = new Map((cuentas || []).map((c) => [c.codigo_cuenta, c]));
  return Object.entries(edits || {})
    .filter(([codigo, categoria]) => {
      const original = porCodigo.get(codigo);
      return original && categoria !== original.categoria_final;
    })
    .map(([codigo_cuenta, categoria]) => ({ codigo_cuenta, categoria }));
}

// Cuántos de los slots dados (por defecto los 6 del workspace) ya tienen
// al menos un archivo, según el objeto que devuelve estadoSlotsOF.
export function contarSubidos(estadoSlots, slotKeys) {
  return (slotKeys || []).filter((k) => (estadoSlots?.[k]?.n_archivos || 0) > 0).length;
}

// Job a retomar al montar el workspace: el más reciente en 'borrador' o
// 'revision' (los únicos estados donde "seguir trabajando" tiene sentido).
// null si no hay ninguno — ahí el workspace ofrece crear un encargo nuevo.
export function encontrarJobActivo(jobs) {
  const activos = (jobs || []).filter(
    (j) => j.status === "borrador" || j.status === "revision"
  );
  if (activos.length === 0) return null;
  return activos.reduce((mejor, j) => (j.id > mejor.id ? j : mejor));
}

// Estado visual de un tile del grid (clases pc-tile / pc-tile-n): "dim"
// (pendiente), "" (parcial/en curso) o "done" (completado). Se deriva SOLO
// del estado del job — no hay API de estado por cédula individual.
export function estadoTile(jobStatus, esClasificacion) {
  if (jobStatus === "done") return "done";
  if (jobStatus === "revision" && esClasificacion) return "";
  return "dim";
}

// Normaliza el form del modal "Editar datos del encargo" al payload que
// esperan crearJobOF / actualizarJobOF: recorta espacios y convierte
// campos opcionales vacíos a null. Se usa tanto al crear como al editar
// (editar además envía el project_id por separado, no aquí).
export function datosEncargoParaGuardar(form) {
  return {
    cliente_name: (form.cliente_name || "").trim(),
    period_label: (form.period_label || "").trim(),
    period_end: form.period_end || null,
    prepared_by_name: (form.prepared_by_name || "").trim() || null,
    reviewed_by_name: (form.reviewed_by_name || "").trim() || null,
    firma_auditora: form.firma_auditora,
  };
}

export function etiquetaEstadoTile(clase) {
  if (clase === "done") return "Completado";
  if (clase === "") return "Parcial";
  return "Pendiente";
}
