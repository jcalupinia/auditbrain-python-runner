// Cliente del Motor de Ingesta (API v1, Fase 7). Endpoints sin proyecto en la
// ruta: /api/v1/ingesta/{tipos,clasificar,ingerir}. Acceso por JWT de operador
// (admin/user), igual que el runner. Patrón calcado de vnr/api.js.
import { getToken, requireApiBase } from "../../api.js";

// Mismo límite que el backend (_MAX_MB en api/ingesta.py). Se valida también
// aquí para fallar rápido sin subir el archivo.
export const MAX_MB = 25;

async function call(path, options = {}) {
  const base = requireApiBase() + "/api/v1/ingesta/";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120000);
  try {
    const res = await fetch(base + path, {
      ...options,
      signal: controller.signal,
      headers: { Authorization: "Bearer " + getToken(), ...options.headers },
    });
    if (!res.ok) {
      let body;
      try {
        body = await res.json();
      } catch {
        /* sin cuerpo JSON */
      }
      throw Error(
        typeof body?.detail === "string"
          ? body.detail
          : "No se pudo completar la operación (" + res.status + ")."
      );
    }
    return res;
  } catch (e) {
    if (e.name === "AbortError") {
      throw Error(
        "El procesamiento tardó demasiado. Revise el tamaño del archivo y vuelva a intentar."
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

function cuerpo(file, tipoDeclarado, extra = {}) {
  if (file.size > MAX_MB * 1024 * 1024) {
    throw Error("Máximo " + MAX_MB + " MB por archivo.");
  }
  const fd = new FormData();
  fd.append("file", file);
  if (tipoDeclarado) fd.append("tipo_declarado", tipoDeclarado);
  for (const [k, v] of Object.entries(extra)) fd.append(k, String(v));
  return fd; // el navegador fija el boundary multipart
}

export async function tiposDocumento() {
  return (await call("tipos")).json();
}

// Clasifica sin extraer (determinista y barato).
export async function clasificar(file, tipoDeclarado) {
  return (
    await call("clasificar", { method: "POST", body: cuerpo(file, tipoDeclarado) })
  ).json();
}

// Ingiere y devuelve { dataset, cola_revision }. La IA NO se dispara aquí
// (determinístico primero): el OCR solo se intenta si el PDF no tiene texto.
export async function ingerir(file, tipoDeclarado, { ocr = true, consolidar = true } = {}) {
  return (
    await call("ingerir", {
      method: "POST",
      body: cuerpo(file, tipoDeclarado, { ocr, consolidar }),
    })
  ).json();
}

// Extrae datos puntuales de un documento narrativo (contrato/carta/informe) y
// devuelve { dataset, cola_revision }. Determinístico primero: fechas, montos,
// RUCs y porcentajes por regex. `usarIa` (opcional) suma obligaciones/partes/
// cláusulas por IA, solo texto, con disclaimer.
export async function narrativo(file, tipoDeclarado, { usarIa = false } = {}) {
  return (
    await call("narrativo", {
      method: "POST",
      body: cuerpo(file, tipoDeclarado, { usar_ia: usarIa }),
    })
  ).json();
}

// Resolución semántica por IA (Fase 6): ingiere y luego pide que la IA
// desambigüe los campos de TEXTO que quedaron en revisión. Devuelve
// { dataset, cola_revision, resolubles, resueltos }. El LLM no calcula cifras.
export async function resolver(file, tipoDeclarado, { ocr = true } = {}) {
  return (
    await call("resolver", {
      method: "POST",
      body: cuerpo(file, tipoDeclarado, { ocr }),
    })
  ).json();
}

// Capa de Mapeo Universal (Fase A3/B) — flujo en dos tiempos, SIN estado.
// Etapa 1: perfila la tabla y PROPONE el mapeo (la máquina propone, M07).
// Devuelve { perfil, esquema, propuesta, cola_revision }. No normaliza nada.
export async function prepararMapeo(file, tipoDocumento) {
  const fd = cuerpo(file, undefined, { tipo_documento: tipoDocumento });
  return (await call("mapeo/preparar", { method: "POST", body: fd })).json();
}

// Etapa 2: aplica el mapeo CONFIRMADO por el auditor (el auditor dispone).
// Se reenvía el mismo archivo (sin estado en el servidor). `mapeoConfirmado`
// es un objeto { campo_canonico: indice_columna }. Devuelve { dataset,
// cola_revision }. M22: un obligatorio vacío queda None, nunca cero.
export async function aplicarMapeo(file, tipoDocumento, mapeoConfirmado) {
  const fd = cuerpo(file, undefined, {
    tipo_documento: tipoDocumento,
    mapeo_confirmado: JSON.stringify(mapeoConfirmado || {}),
  });
  return (await call("mapeo/aplicar", { method: "POST", body: fd })).json();
}


// Poblaciones masivas: no usa la API historica limitada a 25 MB.
export async function cargarMasiva(file, context) {
  if (!file || file.size > 100 * 1024 * 1024) throw Error("Archivo vacio o mayor a 100 MB.");
  const fd = new FormData();
  fd.append("file", file);
  for (const key of ["cliente_id", "encargo_id", "periodo", "tipo_documento", "formato_mayor"]) {
    fd.append(key, String(context[key] || ""));
  }
  fd.append("mapeo_confirmado", JSON.stringify(context.mapeo_confirmado || {}));
  return (await call("masiva/cargar", { method: "POST", body: fd })).json();
}

export async function consultarMasiva(datasetId, clienteId, encargoId, limite = 20) {
  const p = new URLSearchParams({ cliente_id: clienteId, encargo_id: encargoId, limite: String(limite) });
  return (await call("masiva/" + encodeURIComponent(datasetId) + "/filas?" + p)).json();
}


export async function estadoSharePointPiloto() {
  return (await call("masiva/sharepoint/piloto")).json();
}

export async function cargarSharePointPiloto({ cliente_id, encargo_id, periodo }) {
  const fd = new FormData();
  fd.append("cliente_id", cliente_id);
  fd.append("encargo_id", encargo_id);
  fd.append("periodo", periodo);
  return (await call("masiva/sharepoint/piloto/cargar", { method: "POST", body: fd })).json();
}
