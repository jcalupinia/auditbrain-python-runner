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

// Espera cooperativa entre reintentos.
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Backoff creciente: 2s, 4s, 8s, 12s (tope). Suma ~26s, suficiente para cubrir
// el "arranque en frío" típico de Render (~50s con el timeout por intento).
function _backoffMs(attempt) {
  return Math.min(2000 * 2 ** attempt, 12000);
}

// Wrapper resiliente sobre fetch. En Render (plan gratuito / Sandbox Tier 0) el
// backend se DUERME tras ~15 min de inactividad; el primer request durante el
// arranque falla con error de red o con un 502/503/504 del proxy ANTES de
// llegar a la app, y el navegador lo reporta como el críptico "Failed to fetch".
//
// Estrategia: timeout por intento (AbortController) + reintentos con backoff,
// SOLO para fallos transitorios de infraestructura:
//   - error de red / abort por timeout  → el request no llegó a la app: seguro reintentar.
//   - 502 / 503 / 504 (gateway)          → backend arrancando o reciclando: reintentar.
// NUNCA reintenta respuestas 4xx/5xx propias de la app (son respuestas válidas:
// 401 sesión, 413 tamaño, 415 tipo, 500 lógica). Esas van directo a parse().
async function apiFetch(url, opts = {}, { timeoutMs = 60000, retries = 4 } = {}) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...opts, signal: ctrl.signal });
      clearTimeout(timer);
      const gateway = res.status === 502 || res.status === 503 || res.status === 504;
      if (gateway && attempt < retries) {
        await sleep(_backoffMs(attempt));
        continue;
      }
      return res;
    } catch {
      clearTimeout(timer);
      // Error de red o abort por timeout: reintentar hasta agotar los intentos.
      if (attempt < retries) {
        await sleep(_backoffMs(attempt));
        continue;
      }
    }
  }
  // Reintentos agotados: mensaje claro en español en vez de "Failed to fetch".
  throw new Error(
    "No se pudo conectar con el servidor. Es posible que se esté iniciando " +
      "(arranque en frío). Espera unos segundos y vuelve a intentar."
  );
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
  const res = await apiFetch(`${API_BASE}/api/v1/auth/login`, {
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
    await apiFetch(`${API_BASE}/api/v1/auth/me`, { headers: authHeaders() })
  );
}

// Clave que bloquea la estructura del Excel SRI del ICT. Solo admin (el
// backend valida el rol; si no es admin devuelve 403).
export async function getSriProtectionKey() {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/auth/sri-protection-key`, {
      headers: authHeaders(),
    })
  );
}

export async function runPython(script, inputs) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/python/run`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ script, inputs: inputs || {} }),
    })
  );
}

// ---- Motor de balances (homologación N-períodos, AUD staff) ----
export async function motorBalancesHomologar(files) {
  const fd = new FormData();
  (files || []).forEach((f) => fd.append("archivos", f));
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/aud/motor-balances/homologar`,
      { method: "POST", body: fd, headers: authHeaders() }, // el browser fija el boundary
      { timeoutMs: 120000 }
    )
  );
}

export async function motorBalancesRecalcular(esf, eri) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/aud/motor-balances/recalcular`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ esf, eri }),
    })
  );
}

export async function motorBalancesPlan() {
  return parse(await apiFetch(`${API_BASE}/api/v1/aud/motor-balances/plan`, { headers: authHeaders() }));
}

export async function motorBalancesEstados(esf, eri) {
  return parse(await apiFetch(`${API_BASE}/api/v1/aud/motor-balances/estados`, {
    method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ esf, eri }),
  }));
}

export async function createUser(email, password, role) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/auth/users`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ email, password, role }),
    })
  );
}

// --- Gestión de operadores (admin) ---
export async function listOperators() {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/auth/users`, { headers: authHeaders() })
  );
}

export async function resetOperatorPassword(userId, newPassword) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/auth/users/${userId}/reset-password`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ new_password: newPassword ?? null }),
    })
  );
}

// --- Gestión de usuarios de portal cliente (admin · staff portal) ---
export async function listPortalUsers(clientId) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/staff/clients/${clientId}/portal-users`, {
      headers: authHeaders(),
    })
  );
}

export async function createPortalUser(clientId, email) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/staff/clients/${clientId}/portal-users`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ email }),
    })
  );
}

export async function resetPortalUserPassword(clientId, userId, newPassword) {
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/staff/clients/${clientId}/portal-users/${userId}/reset-password`,
      {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ new_password: newPassword ?? null }),
      }
    )
  );
}

export async function deleteOperator(userId) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/auth/users/${userId}`, {
      method: "DELETE",
      headers: authHeaders(),
    })
  );
}

export async function deletePortalUser(clientId, userId) {
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/staff/clients/${clientId}/portal-users/${userId}`,
      { method: "DELETE", headers: authHeaders() }
    )
  );
}

export async function setOperatorActive(userId, active) {
  const op = active ? "enable" : "disable";
  return parse(
    await apiFetch(`${API_BASE}/api/v1/auth/users/${userId}/${op}`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
    })
  );
}

export async function setPortalUserActive(clientId, userId, active) {
  const op = active ? "enable" : "disable";
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/staff/clients/${clientId}/portal-users/${userId}/${op}`,
      { method: "POST", headers: authHeaders({ "Content-Type": "application/json" }) }
    )
  );
}

// --- Carga masiva de clientes (licencias) + gestión global de portal ---
export async function bulkUploadPortalUsers(file) {
  const fd = new FormData();
  fd.append("file", file);
  return parse(
    await apiFetch(`${API_BASE}/api/v1/staff/portal-users/bulk`, {
      method: "POST",
      headers: authHeaders(), // el browser fija el boundary multipart
      body: fd,
    })
  );
}

export async function listAllPortalUsers() {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/staff/portal-users`, { headers: authHeaders() })
  );
}

export async function createSinglePortalClient({ cliente, ruc, email, new_password }) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/staff/portal-users`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ cliente, ruc, email, new_password: new_password ?? null }),
    })
  );
}

export async function resetPortalUserById(userId, newPassword) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/staff/portal-users/${userId}/reset-password`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ new_password: newPassword ?? null }),
    })
  );
}

export async function setPortalUserActiveById(userId, active) {
  const op = active ? "enable" : "disable";
  return parse(
    await apiFetch(`${API_BASE}/api/v1/staff/portal-users/${userId}/${op}`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
    })
  );
}

export async function deletePortalUserById(userId) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/staff/portal-users/${userId}`, {
      method: "DELETE",
      headers: authHeaders(),
    })
  );
}

// Genera un documento vía el endpoint existente /api/v1/documents/generate.
// Solo JWT (Bearer); la API Key nunca se envía desde el navegador.
export async function generateDocument({ format, title, content }) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/documents/generate`, {
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
  return parse(await apiFetch(`${API_BASE}/api/v1/health`));
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
    await apiFetch(`${TAX_PU_BASE}/extract`, {
      method: "POST",
      headers: authHeaders(), // browser fija el boundary multipart
      body: fd,
    })
  );
}

// Descarga autenticada de un .xlsx (export o plantilla). Dispara el guardado.
async function downloadXlsx(url, fetchOpts, filename) {
  const res = await apiFetch(url, { ...fetchOpts, headers: authHeaders(fetchOpts.headers) });
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

// Exporta el Dashboard a un .xlsx EJECUTIVO PREMIUM con gráficos NATIVOS de Excel
// (ligados a las celdas → se actualizan al editar), tablas estructuradas y hoja
// "Datos_PowerBI" en formato largo (lista para importar a Power BI). El backend
// (openpyxl) lo genera; el estilo de gráfico sale del selector del dashboard.
export async function exportDashboardXlsx({ data, labels, meses, empresa, chartStyle }) {
  const safe = String(empresa || "cliente").replace(/[\s/\\]+/g, "_") || "cliente";
  await downloadXlsx(
    `${TAX_PU_BASE}/dashboard-xlsx`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        data,
        labels: labels || [],
        meses: meses || [],
        empresa: empresa || "Empresa",
        chart_style: chartStyle || "combo",
      }),
    },
    `Dashboard_Ejecutivo_${safe}.xlsx`
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
    await apiFetch(`${TAX_PU_BASE}/sri/${encodeURIComponent(ruc)}`, {
      headers: authHeaders(),
    })
  );
}

// Agente: genera la narrativa de recomendación a partir de las cifras
// deterministas de los escenarios. La IA no calcula números.
export async function generarRecomendacionAgente({ empresa, comparacion, recomendado }) {
  return parse(
    await apiFetch(`${TAX_PU_BASE}/recomendacion`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ empresa, comparacion, recomendado }),
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

// ---------- Eventos / Inscripciones a charlas (admin) ----------

export async function listEventRegistrations(slug, limit = 500) {
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/events/${slug}/registrations?limit=${limit}`,
      { headers: authHeaders() }
    )
  );
}

// ---------- Fase 2 · M1: contexto operativo ----------

export async function getMyContext() {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/me/context`, { headers: authHeaders() })
  );
}

export async function setActiveProject(projectId) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/me/context`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ project_id: projectId }),
    })
  );
}

export async function listClients() {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/context/clients`, { headers: authHeaders() })
  );
}

export async function createClient(payload) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/context/clients`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    })
  );
}

export async function listProjects() {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/context/projects`, { headers: authHeaders() })
  );
}

export async function createProject(payload) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/context/projects`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    })
  );
}

export async function addProjectMember(projectId, payload) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/context/projects/${projectId}/members`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    })
  );
}

// ---------- Fase 2 · M2: chat cognitivo ----------

export async function listConversations() {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/chat/conversations`, { headers: authHeaders() })
  );
}

export async function createConversation(payload = {}) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/chat/conversations`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    })
  );
}

export async function getConversation(conversationId) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/chat/conversations/${conversationId}`, {
      headers: authHeaders(),
    })
  );
}

export async function sendChatMessage(conversationId, content) {
  return parse(
    await apiFetch(
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

  const res = await apiFetch(
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
    await apiFetch(
      `${API_BASE}/api/v1/aud/obligaciones-fiscales/jobs/${jobId}`,
      { headers: authHeaders() }
    )
  );
}

export async function listObligacionesFiscalesJobs(projectId) {
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/aud/obligaciones-fiscales/jobs?project_id=${projectId}`,
      { headers: authHeaders() }
    )
  );
}

export async function downloadObligacionesFiscalesJob(jobId, suggestedFilename) {
  // Descarga autenticada (JWT). Crea un blob URL temporal y dispara click.
  const res = await apiFetch(
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

// ---- Permisos de herramientas por usuario (entitlements) ----
export async function getStaffTools() {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/staff/tools`, { headers: authHeaders() })
  );
}

export async function getUserEntitlements(userId) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/staff/portal-users/${userId}/entitlements`, {
      headers: authHeaders(),
    })
  );
}

export async function setUserEntitlements(userId, toolCodes) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/staff/portal-users/${userId}/entitlements`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ tool_codes: toolCodes }),
    })
  );
}

// ---------- AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO ----------

const ICT_BASE = `${API_BASE}/api/v1/aud/informe-cumplimiento-tributario`;

export async function parseIctPreview(files) {
  const fd = new FormData();
  fd.append("informe_auditoria_externa", files.informe);
  fd.append("declaracion_ir", files.f101);
  return parse(await fetch(`${ICT_BASE}/parse-preview`, {
    method: "POST", headers: authHeaders(), body: fd,
  }));
}

export async function createIctJob(form, files) {
  const fd = new FormData();
  Object.entries(form).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") fd.append(k, v);
  });
  fd.append("informe_auditoria_externa", files.informe);
  fd.append("declaracion_ir", files.f101);
  if (files.diferencias) fd.append("anexo_diferencias_sri", files.diferencias);
  return parse(await fetch(`${ICT_BASE}/jobs`, {
    method: "POST", headers: authHeaders(), body: fd,
  }));
}

export async function getIctJob(jobId) {
  return parse(await fetch(`${ICT_BASE}/jobs/${jobId}`, { headers: authHeaders() }));
}

export async function listIctJobs(projectId) {
  return parse(await fetch(`${ICT_BASE}/jobs?project_id=${projectId}`, { headers: authHeaders() }));
}

export async function downloadIctJob(jobId, suggestedFilename) {
  const res = await fetch(`${ICT_BASE}/jobs/${jobId}/download`, { headers: authHeaders() });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { detail = (await res.json()).detail || detail; } catch { /* */ }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedFilename || `Informe_Cumplimiento_Tributario_${jobId}.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
