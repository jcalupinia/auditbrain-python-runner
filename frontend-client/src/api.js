const BASE = import.meta.env.VITE_API_BASE || "https://auditbrain-api.onrender.com";

let _token = localStorage.getItem("ab_client_token") || null;

export function setToken(t) {
  _token = t;
  if (t) localStorage.setItem("ab_client_token", t);
  else localStorage.removeItem("ab_client_token");
}

export function getToken() {
  return _token;
}

async function request(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (_token) headers["Authorization"] = `Bearer ${_token}`;
  const resp = await fetch(`${BASE}/api/v1${path}`, {
    ...opts,
    headers,
    credentials: "include", // crítico para cookie device_id
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

export async function login(email, password) {
  // ATENCIÓN: usamos URLSearchParams (NO FormData) para que los caracteres
  // especiales del email (en particular ``+`` en aliases tipo
  // ``jcalupinia+cliente@dominio.ec``) se codifiquen como ``%2B`` y no
  // como espacio. OAuth2PasswordRequestForm de FastAPI espera
  // ``application/x-www-form-urlencoded`` y aplica decodificación URL
  // estricta: el ``+`` literal se decodifica como espacio, lo que rompe
  // el login para emails con alias y devuelve 401 "Credenciales incorrectas".
  const body = new URLSearchParams();
  body.append("username", email);
  body.append("password", password);
  const r = await fetch(`${BASE}/api/v1/client/auth/login`, {
    method: "POST",
    body,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    credentials: "include",
  });
  const respBody = await r.json();
  if (!r.ok) {
    const err = new Error(respBody?.detail?.message || respBody?.detail || `HTTP ${r.status}`);
    err.status = r.status; err.code = respBody?.detail?.code; throw err;
  }
  setToken(respBody.access_token);
  return respBody;
}

export async function logout() {
  try { await request("/client/auth/logout", { method: "POST" }); }
  finally { setToken(null); }
}

export const me = () => request("/client/auth/me");
export const changePassword = (old_password, new_password) =>
  request("/client/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ old_password, new_password }),
  });
export const getCatalog = () => request("/client/catalog");
export const listJobs = (status = null, limit = 20) => {
  const qs = new URLSearchParams();
  if (status) qs.set("status", status);
  qs.set("limit", limit);
  return request(`/client/tools/jobs?${qs}`);
};
export const getJob = (jobId) => request(`/client/tools/jobs/${jobId}`);
export const createJob = async (toolCode, fileMap) => {
  // fileMap: { slotName: File or [File, ...] }
  const fd = new FormData();
  for (const [slot, val] of Object.entries(fileMap)) {
    const arr = Array.isArray(val) ? val : [val];
    for (const f of arr) fd.append(slot, f);
  }
  return request(`/client/tools/${toolCode}/jobs`, { method: "POST", body: fd });
};
export async function downloadJob(jobId, filename = null) {
  const resp = await fetch(`${BASE}/api/v1/client/tools/jobs/${jobId}/download`, {
    headers: _token ? { Authorization: `Bearer ${_token}` } : {},
    credentials: "include",
  });
  if (!resp.ok) {
    let detail = null;
    try { detail = (await resp.json())?.detail; } catch {}
    const msg = typeof detail === "string" ? detail
              : detail?.message || `HTTP ${resp.status}`;
    const err = new Error(msg);
    err.status = resp.status;
    err.code = detail?.code;
    throw err;
  }
  const blob = await resp.blob();
  // Try to read filename from Content-Disposition
  const cd = resp.headers.get("content-disposition") || "";
  const m = cd.match(/filename="?([^"]+)"?/);
  const finalName = filename || (m ? m[1] : `job-${jobId}.bin`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = finalName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
