import * as api from "../api.js";

const BASE = import.meta.env.VITE_API_BASE || "https://auditbrain-python-runner.onrender.com";

async function _request(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = api.getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(`${BASE}/api/v1${path}`, {
    ...opts,
    headers,
    credentials: "include",
  });
  let body = null;
  try { body = await resp.json(); } catch { /* ignore */ }
  if (!resp.ok) {
    const err = new Error(body?.detail?.message || body?.detail || `HTTP ${resp.status}`);
    err.status = resp.status;
    err.code = body?.detail?.code;
    err.body = body;
    throw err;
  }
  return body;
}

export async function createSession({ ejercicio_fiscal, ruc, razon_social, numero_adhesivo }) {
  return _request("/client/ict/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ejercicio_fiscal, ruc, razon_social, numero_adhesivo }),
  });
}

export async function getActiveSession() {
  try {
    return await _request("/client/ict/sessions/active");
  } catch (e) {
    if (e.status === 404) return null;
    throw e;
  }
}

export async function getSession(id) {
  return _request(`/client/ict/sessions/${id}`);
}

export async function updateSession(id, payload) {
  return _request(`/client/ict/sessions/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteSession(id) {
  return _request(`/client/ict/sessions/${id}`, { method: "DELETE" });
}

export async function uploadAnexoSlot(sessionId, anexoCode, slotName, fileOrFiles) {
  const fd = new FormData();
  const files = Array.isArray(fileOrFiles) ? fileOrFiles : [fileOrFiles];
  for (const f of files) {
    fd.append("files", f);  // clave "files" coincide con list[UploadFile] en FastAPI
  }
  fd.append("slot_name", slotName);
  return _request(`/client/ict/sessions/${sessionId}/anexos/${anexoCode}/upload`, {
    method: "POST",
    body: fd,
  });
}

export async function resetSlot(sessionId, anexoCode, slotName) {
  return _request(
    `/client/ict/sessions/${sessionId}/anexos/${anexoCode}/upload/${slotName}`,
    { method: "DELETE" }
  );
}

export async function processSession(sessionId) {
  return _request(`/client/ict/sessions/${sessionId}/process`, { method: "POST" });
}

// Helper común para los dos descargadores. Llama al endpoint, extrae el
// filename del Content-Disposition y dispara el download en el navegador.
async function _downloadBlob(url, defaultFilename) {
  const token = api.getToken();
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(url, { headers, credentials: "include" });
  if (!resp.ok) {
    // Mensajes amigables por status code común
    if (resp.status === 401) {
      throw new Error(
        "Tu sesión expiró. Refrescá la página (F5) y volvé a intentar."
      );
    }
    if (resp.status === 403) {
      throw new Error(
        "No tenés permiso para descargar este archivo. Verificá que sos el dueño de la sesión."
      );
    }
    if (resp.status === 404) {
      throw new Error(
        "Archivo no encontrado. Procesá la sesión primero."
      );
    }
    if (resp.status >= 500) {
      throw new Error(
        `Error del servidor (${resp.status}). Esperá unos segundos y reintentá. ` +
        "Si persiste, refrescá la página."
      );
    }
    throw new Error(`HTTP ${resp.status}`);
  }
  const blob = await resp.blob();
  const cd = resp.headers.get("content-disposition") || "";
  const m = cd.match(/filename="?([^"]+)"?/);
  const filename = m ? m[1] : defaultFilename;
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
}

/**
 * Descarga el Excel LIMPIO listo para cargar al portal del SRI Ecuador.
 * NO contiene VERIFICACIÓN A1, AUDITORÍA DE ANEXOS ni TRAZABILIDAD
 * (regla CLAUDE.md "Separación SRI vs Papel de trabajo").
 */
export async function downloadExcel(sessionId) {
  return _downloadBlob(
    `${BASE}/api/v1/client/ict/sessions/${sessionId}/download`,
    `ICT_${sessionId}_SRI.xlsx`,
  );
}

/**
 * Descarga el Excel PAPEL DE TRABAJO del auditor: incluye VERIFICACIÓN A1,
 * AUDITORÍA DE ANEXOS, TRAZABILIDAD e interpretación generada por IA.
 * Este archivo NO debe cargarse al SRI.
 */
export async function downloadPapelTrabajo(sessionId) {
  return _downloadBlob(
    `${BASE}/api/v1/client/ict/sessions/${sessionId}/papel-trabajo`,
    `ICT_${sessionId}_PAPEL_TRABAJO.xlsx`,
  );
}
