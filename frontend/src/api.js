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
