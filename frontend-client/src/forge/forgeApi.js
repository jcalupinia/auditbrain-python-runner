// Cliente API del módulo Forge (portal de clientes). Reusa el token de api.js
// y apunta a /client/forge/* (auth rol client + device).
import * as api from "../api.js";

const BASE =
  import.meta.env.VITE_API_BASE || "https://auditbrain-python-runner.onrender.com";

async function _request(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  const token = api.getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(`${BASE}/api/v1${path}`, {
    ...opts,
    headers,
    credentials: "include",
  });
  let body = null;
  try {
    body = await resp.json();
  } catch {
    body = null;
  }
  if (!resp.ok) {
    const detail = body && body.detail;
    const msg =
      (detail && detail.message) || detail || `HTTP ${resp.status}`;
    const err = new Error(msg);
    err.status = resp.status;
    throw err;
  }
  return body;
}

export const listTargets = () => _request("/client/forge/targets");
export const getSubscription = () => _request("/client/forge/subscription");
export const listBrains = () => _request("/client/forge/brains");
export const createBrain = (data) =>
  _request("/client/forge/brains", { method: "POST", body: JSON.stringify(data) });
export const compileBrain = (id, target) =>
  _request(`/client/forge/brains/${id}/compile`, {
    method: "POST",
    body: JSON.stringify({ target }),
  });
