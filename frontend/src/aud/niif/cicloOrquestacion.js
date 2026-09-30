// Orquestación del ciclo de una prueba: encadena las acciones del servidor (cada
// una queda en la bitácora) para preparar la base técnica, producir la prueba,
// enviarla a revisión y aprobarla. La usa la consola-chat del piloto (y sirve de
// única fuente para el flujo de un procesador). No trae reglas nuevas: mira el
// estado y hace solo lo que falta, igual que la vista de trabajo.
//
// El `mapear` de un procesador arma los datasets de TODOS los anexos entregados y
// deja que el servidor valide cuál es el principal (a diferencia del guard fijo de
// cartera de la vista de trabajo, que no servía para planificación).

import * as api from "../../api";

import { archivosDe, erroresLegibles, mapeoConManual, mejorEncabezado, pasoPreparar } from "./cicloLogic";

// Se devuelve en vez de la prueba cuando el reconocimiento por alias no cubre las
// columnas obligatorias de algún archivo y hay quien atienda el mapeo manual
// (onPendientes): corta el flujo sin error para que la vista abra el modal.
export const PENDIENTE_MAPEO = Symbol("pendiente-mapeo");

const CON_SUBIDA = ["REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA"];
const PROCESADA = ["PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS"];
const ANTES_DEL_REQUERIMIENTO = ["PRUEBA_SELECCIONADA", "PROGRAMA_PROPUESTO", "PROGRAMA_APROBADO", "REQUERIMIENTO_GENERADO"];
const FLOW_FIELDS = [
  { key: "id", label: "Contrato", type: "text" },
  { key: "fecha", label: "Fecha del pago", type: "date" },
  { key: "importe", label: "Importe", type: "number" },
];

const cargarFiles = () => import("./sitio/tools/files.mjs");

// Saldo escrito por el auditor al formato del servidor (punto decimal, sin miles).
const saldoMayor = (t) => {
  const x = String(t || "").trim().replace(/\s/g, "");
  return x.includes(",") ? x.replace(/\./g, "").replace(",", ".") : x;
};

// Aplica una acción sobre la revisión vigente y devuelve la prueba fresca.
async function paso(prueba, accion, datos = {}) {
  const fresca = await api.cicloLeerPrueba(prueba.id);
  await api.cicloAccion(prueba.id, accion, fresca.revision, datos);
  return api.cicloLeerPrueba(prueba.id);
}

// Programa, fuentes y requerimiento (encadena research → generate_program → approve_program → generate_request → approve_request).
export async function prepararBaseTecnica(prueba, { taxScope = "", taxConforme = false } = {}) {
  let p = await api.cicloLeerPrueba(prueba.id);
  for (let i = 0; i < 8; i++) {
    const siguiente = pasoPreparar(p, taxScope, taxConforme);
    if (!siguiente) return p;
    p = await paso(p, ...siguiente);
  }
  return p;
}

// `manualMaps` = { fileId: { campo.key: colIndex } } — lo que el auditor asignó a
// mano; pisa el reconocimiento por alias. `onPendientes` recibe los archivos cuyas
// columnas obligatorias siguen sin resolverse: si está, se juntan y se devuelve
// PENDIENTE_MAPEO (para abrir el modal) en vez de lanzar el error clásico.
async function mapear(p, files, { manualMaps = {}, onPendientes = null } = {}) {
  const d = p.definicion;
  const pendientes = [];
  const armar = async (reqId, campos, dataset) => {
    const partes = [];
    for (const a of archivosDe(p, reqId)) {
      const bytes = await api.cicloBajarArchivo(p.id, a.id);
      const { sheets } = files.readSpreadsheet(bytes, a.nombre);
      const elegido = mejorEncabezado(sheets, campos);
      if (!elegido) throw new Error(`${a.nombre}: no se pudo leer ninguna hoja.`);
      // El mapeo manual del auditor pisa lo que detectó el reconocimiento por alias.
      const combinado = mapeoConManual(elegido, manualMaps[a.id], campos);
      if (combinado.faltan.length) {
        if (!onPendientes)
          throw new Error(`${a.nombre}: no se reconocen las columnas ${combinado.faltan.join(", ")}.`);
        const hoja = (sheets || []).find((s) => s.name === combinado.sheet);
        const filaEnc = ((hoja && hoja.rows) || [])[combinado.header - 1] || [];
        pendientes.push({
          req: reqId, dataset, fileId: a.id, nombre: a.nombre,
          sheet: combinado.sheet, header: combinado.header,
          columnas: filaEnc.map((c) => String(c ?? "")),
          campos, mapping: combinado.mapping,
        });
        continue;
      }
      partes.push({ fileId: a.id, sheet: combinado.sheet, header: combinado.header, mapping: combinado.mapping });
    }
    return partes;
  };
  if (d.processor) {
    const datasets = {};
    for (const r of (p.registro.requests || []).filter((x) => x.dataset)) {
      const tipo = (d.tipos && d.tipos[r.dataset]) || (["a1", "a2", "a3"].includes(r.dataset) ? "cartera" : r.dataset);
      const partes = await armar(r.id, d.campos[tipo], r.dataset);
      if (partes.length) datasets[r.dataset] = partes;
    }
    if (pendientes.length && onPendientes) { onPendientes(pendientes); return PENDIENTE_MAPEO; }
    if (!Object.keys(datasets).length)
      throw new Error("Sube al menos el balance de comprobación del corte antes de producir la planificación.");
    return paso(p, "map_validate", { datasets });
  }
  const [poblacion, flujos] = p.modelos || [];
  const files_ = await armar(poblacion, d.fields, poblacion);
  let flowsParte = null;
  if (d.flows && flujos) flowsParte = (await armar(flujos, FLOW_FIELDS, flujos))[0] || null;
  if (pendientes.length && onPendientes) { onPendientes(pendientes); return PENDIENTE_MAPEO; }
  if (!files_.length) throw new Error("Sube el reporte de cálculo antes de producir.");
  const datos = { files: files_ };
  if (d.flows && flujos) {
    if (!flowsParte) throw new Error("Sube el calendario de pagos antes de producir.");
    Object.assign(datos, { flowsFile: flowsParte.fileId, flowsSheet: flowsParte.sheet, flowsHeader: flowsParte.header, flowsMapping: flowsParte.mapping });
  }
  return paso(p, "map_validate", datos);
}

// Revisa —sin procesar ni cambiar el estado— si las columnas obligatorias de los
// anexos ya subidos se reconocen (por alias o con el mapeo manual guardado).
// Devuelve la lista de archivos con columnas pendientes, en el MISMO formato que
// consume el modal de mapeo manual. Sirve para avisar al auditor apenas carga el
// anexo si hace falta mapear a mano, en vez de esperar a pulsar «Procesar».
export async function revisarColumnas(prueba, { manualMaps = {} } = {}) {
  const files = await cargarFiles();
  const p = await api.cicloLeerPrueba(prueba.id);
  const d = p.definicion;
  const pendientes = [];
  const revisar = async (reqId, campos, dataset) => {
    for (const a of archivosDe(p, reqId)) {
      const bytes = await api.cicloBajarArchivo(p.id, a.id);
      const { sheets } = files.readSpreadsheet(bytes, a.nombre);
      const elegido = mejorEncabezado(sheets, campos);
      if (!elegido) {
        pendientes.push({ req: reqId, dataset, fileId: a.id, nombre: a.nombre, sheet: null, header: 1, columnas: [], campos, mapping: {} });
        continue;
      }
      const combinado = mapeoConManual(elegido, manualMaps[a.id], campos);
      if (combinado.faltan.length) {
        const hoja = (sheets || []).find((s) => s.name === combinado.sheet);
        const filaEnc = ((hoja && hoja.rows) || [])[combinado.header - 1] || [];
        pendientes.push({
          req: reqId, dataset, fileId: a.id, nombre: a.nombre,
          sheet: combinado.sheet, header: combinado.header,
          columnas: filaEnc.map((c) => String(c ?? "")),
          campos, mapping: combinado.mapping,
        });
      }
    }
  };
  if (d.processor) {
    for (const r of (p.registro.requests || []).filter((x) => x.dataset)) {
      const tipo = (d.tipos && d.tipos[r.dataset]) || (["a1", "a2", "a3"].includes(r.dataset) ? "cartera" : r.dataset);
      await revisar(r.id, d.campos[tipo], r.dataset);
    }
  } else {
    const [poblacion, flujos] = p.modelos || [];
    if (poblacion) await revisar(poblacion, d.fields, poblacion);
    if (d.flows && flujos) await revisar(flujos, FLOW_FIELDS, flujos);
  }
  return pendientes;
}

// Produce la prueba: desde donde esté (preparando la base técnica si hace falta) hasta ejecutarla y dejar el
// análisis preliminar listo. Devuelve la prueba producida (estado RESULTADOS_ANALIZADOS).
export async function producir(prueba, { mayor = "", param = {}, tasas = {}, buckets = [], manualMaps = {}, onPendientes = null } = {}) {
  const files = await cargarFiles();
  let p = await api.cicloLeerPrueba(prueba.id);
  const d = p.definicion;
  if (PROCESADA.includes(p.estado))
    p = await paso(p, "return_to_data", { comment: "Reproceso desde la consola de planificación con la evidencia vigente." });
  if (ANTES_DEL_REQUERIMIENTO.includes(p.estado)) p = await prepararBaseTecnica(p);
  for (let i = 0; i < 10; i++) {
    if (CON_SUBIDA.includes(p.estado)) {
      if ((p.huecos || []).length) throw new Error(`Faltan documentos: ${p.huecos.join(" · ")}`);
      if (!p.registro.validation?.ok || p.estado === "REQUERIMIENTO_APROBADO" || !p.registro.rows?.length) {
        p = await mapear(p, files, { manualMaps, onPendientes });
        if (p === PENDIENTE_MAPEO) return PENDIENTE_MAPEO; // se abrió el modal de mapeo manual: se corta sin error.
        if (!p.registro.validation?.ok)
          throw new Error(`La información tiene errores: ${erroresLegibles(p.registro.validation, 5).join(" · ")}`);
      }
      const nombres = (p.archivos || []).filter((a) => a.estado !== "rechazado").map((a) => a.nombre);
      p = await paso(p, "validate", {
        evidenceReviewed: true,
        evidenceReview: `Producido desde la consola de planificación con ${nombres.length} archivo(s): ${nombres.join(", ")}.`,
        ledger: saldoMayor(mayor) || "0",
        tolerance: "0",
        acceptance: "Diferencia con el mayor pendiente de análisis al producir la planificación.",
      });
    } else if (p.estado === "DOCUMENTACION_VALIDADA") {
      p = await paso(p, "configure", {
        ...(d.processor ? { parametros: { ...param, tasas } } : {}),
        basis: `Parámetros y metodología de la ficha «${d.name}», corte ${p.registro.engagement.cutoff}.`,
        buckets: buckets || [],
      });
    } else if (p.estado === "PRUEBA_CONFIGURADA") {
      p = await paso(p, "approve_methodology");
    } else if (p.estado === "METODOLOGIA_APROBADA") {
      if (d.processor) {
        p = await paso(p, "execute");
      } else {
        const dominio = await import("./sitio/tools/domain.mjs");
        const navegador = dominio.calculate(p.definicion, p.registro.rows, p.registro.parameters, p.registro.flows || []);
        p = await paso(p, "execute", { navegador });
      }
    } else break;
  }
  if (p.estado === "PRUEBA_EJECUTADA") p = await paso(p, "analyze");
  return p;
}

// Envía a revisión del auditor (usa el análisis preliminar que arma el servidor y la conclusión del preparador).
export async function enviar(prueba, { conclusion }) {
  let p = await api.cicloLeerPrueba(prueba.id);
  if (p.estado === "PRUEBA_EJECUTADA") p = await paso(p, "analyze");
  const analysis = p.registro.analysis || "Análisis preliminar de la planificación generado por la plataforma.";
  return paso(p, "submit", { analysis, conclusion });
}

// Aprueba la planificación (compuerta del socio). Evalúa las excepciones con un texto por defecto si el auditor no lo cambió.
export async function aprobar(prueba, { conclusion, conclusionReviewed = true, exceptionReview = "" } = {}) {
  const texto = exceptionReview.trim().length >= 10 ? exceptionReview
    : "Problemas de la planificación revisados; se atienden en el programa y en la matriz de riesgos.";
  return paso(prueba, "approve", { conclusion, conclusionReviewed, exceptionReview: texto });
}

// Devuelve la planificación al preparador.
export async function devolver(prueba, { comment }) {
  return paso(prueba, "return_to_data", { comment });
}
