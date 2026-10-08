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
