// Cliente de la API AuditBrain. Solo JWT: la API Key NUNCA vive aquí.

const API_BASE = (
  import.meta.env.VITE_API_BASE ?? "https://auditbrain-python-runner.onrender.com"
).replace(/\/$/, "");

const TOKEN_KEY = "ab_token";
const ROLE_KEY = "ab_role";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function getRole() {
  return localStorage.getItem(ROLE_KEY);
}
export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
}

async function parse(res) {
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    // Token JWT expirado/inválido a mitad de sesión: limpiar y volver al
    // login automáticamente. Excepción: el propio endpoint de login también
    // devuelve 401 con credenciales malas; ahí queremos que el formulario
    // muestre el error sin recargar.
    const reqUrl = res.url || "";
    if (
      res.status === 401 &&
      getToken() &&
      !reqUrl.endsWith("/api/v1/auth/login")
    ) {
      clearSession();
      if (typeof window !== "undefined") window.location.reload();
    }
    const detail =
      (data && data.detail) || res.statusText || `HTTP ${res.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

export async function login(email, password) {
  // OAuth2 password flow: form-urlencoded, username = email.
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const data = await parse(res);
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(ROLE_KEY, data.role);
  return data;
}

function authHeaders(extra = {}) {
  const t = getToken();
  return t ? { ...extra, Authorization: `Bearer ${t}` } : extra;
}

export async function me() {
  return parse(
    await fetch(`${API_BASE}/api/v1/auth/me`, { headers: authHeaders() })
  );
}

export async function runPython(script, inputs) {
  return parse(
    await fetch(`${API_BASE}/api/v1/python/run`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ script, inputs: inputs || {} }),
    })
  );
}

export async function createUser(email, password, role) {
  return parse(
    await fetch(`${API_BASE}/api/v1/auth/users`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ email, password, role }),
    })
  );
}

// Genera un documento vía el endpoint existente /api/v1/documents/generate.
// Solo JWT (Bearer); la API Key nunca se envía desde el navegador.
export async function generateDocument({ format, title, content }) {
  return parse(
    await fetch(`${API_BASE}/api/v1/documents/generate`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        result: { Titulo: title, Contenido: content },
        output_expectations: { format },
        execution_context: { task_name: title, module_area: "Documentos" },
        document_service: {},
      }),
    })
  );
}

// Busca una URL de descarga en la respuesta del servicio documental,
// sin asumir una forma fija (puede variar según formato).
export function findDownloadUrl(resp) {
  const r = resp && resp.response;
  if (!r || typeof r !== "object") return null;
  for (const k of ["url", "download_url", "file_url", "link", "file", "path"]) {
    if (typeof r[k] === "string" && /^https?:\/\//.test(r[k])) return r[k];
  }
  return null;
}

// Endpoint público existente (sin auth). Solo lectura para el dashboard.
export async function health() {
  return parse(await fetch(`${API_BASE}/api/v1/health`));
}

export function getApiBase() {
  return API_BASE;
}

// ---------- TAX.PLANIFICACION_UTILIDADES (ingesta + export Excel) ----------

const TAX_PU_BASE = `${API_BASE}/api/v1/tax/planificacion-utilidades`;

// Ingesta: sube F-101 (PDF) o balance resumido (.xlsx) y devuelve los datos
// mapeados a los esquemas ESF/ER, params detectados y warnings.
export async function extractTaxPlan(kind, file) {
  const fd = new FormData();
  fd.append("kind", kind);
  fd.append("file", file);
  return parse(
    await fetch(`${TAX_PU_BASE}/extract`, {
      method: "POST",
      headers: authHeaders(), // browser fija el boundary multipart
      body: fd,
    })
  );
}

// Descarga autenticada de un .xlsx (export o plantilla). Dispara el guardado.
async function downloadXlsx(url, fetchOpts, filename) {
  const res = await fetch(url, { ...fetchOpts, headers: authHeaders(fetchOpts.headers) });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* sin body */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const blob = await res.blob();
  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(objUrl), 30000);
}

// Exporta el modelo actual a Excel con fórmulas nativas interactivas.
export async function exportTaxPlan({ data, ctrl, params }) {
  const empresa = (params && params.empresa) || "cliente";
  const safe = String(empresa).replace(/[\s/]+/g, "_");
  await downloadXlsx(
    `${TAX_PU_BASE}/export`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data, ctrl, params }),
    },
    `Planificacion_Utilidades_${safe}.xlsx`
  );
}

// Descarga la plantilla en blanco del balance resumido.
export async function downloadTaxPlantilla() {
  await downloadXlsx(
    `${TAX_PU_BASE}/plantilla`,
    { method: "GET" },
    "Balance_resumido_plantilla.xlsx"
  );
}

// Consulta el SRI por RUC (oficial): razón social + actividad económica.
export async function consultarSriRuc(ruc) {
  return parse(
    await fetch(`${TAX_PU_BASE}/sri/${encodeURIComponent(ruc)}`, {
      headers: authHeaders(),
    })
  );
}

// Genera y descarga la presentación ejecutiva (.pptx) premium para
// gerencia/accionistas. Se arma en el servidor con python-pptx.
export async function generarPresentacionTax({ content }) {
  const empresa = (content && content.empresa) || "cliente";
  const safe = String(empresa).replace(/[\s/]+/g, "_");
  await downloadXlsx(
    `${TAX_PU_BASE}/presentacion`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    },
    `Presentacion_Utilidades_${safe}.pptx`
  );
}

// ---------- Fase 2 · M1: contexto operativo ----------

export async function getMyContext() {
  return parse(
    await fetch(`${API_BASE}/api/v1/me/context`, { headers: authHeaders() })
  );
}

export async function setActiveProject(projectId) {
  return parse(
    await fetch(`${API_BASE}/api/v1/me/context`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ project_id: projectId }),
    })
  );
}

export async function listClients() {
  return parse(
    await fetch(`${API_BASE}/api/v1/context/clients`, { headers: authHeaders() })
  );
}

export async function createClient(payload) {
  return parse(
    await fetch(`${API_BASE}/api/v1/context/clients`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    })
  );
}

export async function listProjects() {
  return parse(
    await fetch(`${API_BASE}/api/v1/context/projects`, { headers: authHeaders() })
  );
}

export async function createProject(payload) {
  return parse(
    await fetch(`${API_BASE}/api/v1/context/projects`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    })
  );
}

export async function addProjectMember(projectId, payload) {
  return parse(
    await fetch(`${API_BASE}/api/v1/context/projects/${projectId}/members`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    })
  );
}

// ---------- Fase 2 · M2: chat cognitivo ----------

export async function listConversations() {
  return parse(
    await fetch(`${API_BASE}/api/v1/chat/conversations`, { headers: authHeaders() })
  );
}

export async function createConversation(payload = {}) {
  return parse(
    await fetch(`${API_BASE}/api/v1/chat/conversations`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    })
  );
}

export async function getConversation(conversationId) {
  return parse(
    await fetch(`${API_BASE}/api/v1/chat/conversations/${conversationId}`, {
      headers: authHeaders(),
    })
  );
}

export async function sendChatMessage(conversationId, content) {
  return parse(
    await fetch(
      `${API_BASE}/api/v1/chat/conversations/${conversationId}/messages`,
      {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ content }),
      }
    )
  );
}

// ---------- AUD.IMPUESTOS.OBLIGACIONES_FISCALES (M1) ----------

export async function createObligacionesFiscalesJob(form, files) {
  const fd = new FormData();
  Object.entries(form).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") fd.append(k, v);
  });
  (files.f103 || []).forEach((f) => fd.append("files_f103", f));
  (files.f104 || []).forEach((f) => fd.append("files_f104", f));
  (files.ats || []).forEach((f) => fd.append("files_ats", f));
  if (files.mayor_compras) fd.append("mayor_compras", files.mayor_compras);
  if (files.mayor_ventas) fd.append("mayor_ventas", files.mayor_ventas);
  if (files.f101) fd.append("file_f101", files.f101);

  const res = await fetch(
    `${API_BASE}/api/v1/aud/obligaciones-fiscales/jobs`,
    {
      method: "POST",
      headers: authHeaders(), // No Content-Type: el browser pone el boundary multipart
      body: fd,
    }
  );
  return parse(res);
}

export async function getObligacionesFiscalesJob(jobId) {
  return parse(
    await fetch(
      `${API_BASE}/api/v1/aud/obligaciones-fiscales/jobs/${jobId}`,
      { headers: authHeaders() }
    )
  );
}

export async function listObligacionesFiscalesJobs(projectId) {
  return parse(
    await fetch(
      `${API_BASE}/api/v1/aud/obligaciones-fiscales/jobs?project_id=${projectId}`,
      { headers: authHeaders() }
    )
  );
}

export async function downloadObligacionesFiscalesJob(jobId, suggestedFilename) {
  // Descarga autenticada (JWT). Crea un blob URL temporal y dispara click.
  const res = await fetch(
    `${API_BASE}/api/v1/aud/obligaciones-fiscales/jobs/${jobId}/download`,
    { headers: authHeaders() }
  );
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* sin body */
    }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedFilename || `DM_Obligaciones_Fiscales_${jobId}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
