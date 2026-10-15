// Resolución del backend de un Preview Environment a partir del hostname del navegador.
// Módulo PURO (sin import.meta ni window) para poder probarlo con vitest y con node:test.
//
// Reglas:
//  1) Coolify (mismo servidor): <n>.consola|clientes.preview.audit-ia.ec -> https://<n>.api.preview.audit-ia.ec
//  2) Render (compatibilidad temporal): auditbrain-frontend|clientes-pr-<n>.onrender.com
//     -> https://auditbrain-python-runner-pr-<n>.onrender.com
//  3) Cualquier otro host -> null (no es un preview; el llamador decide si es producción/dev conocido
//     o si debe fallar cerrado). NUNCA se cae a producción desde aquí.
export const COOLIFY_PREVIEW_DOMAIN = "preview.audit-ia.ec";

const DOM = COOLIFY_PREVIEW_DOMAIN.replace(/\./g, "\\.");
const COOLIFY_RE = new RegExp("^(\\d{1,7})\\.(?:consola|clientes)\\." + DOM + "$");
const RENDER_RE = /^auditbrain-(?:frontend|clientes)-pr-(\d{1,7})\.onrender\.com$/;

// Hostname canónico: minúsculas, sin espacios, sin punto final, sin puerto, sin esquema ni ruta.
export function normalizeHost(value) {
  let h = String(value ?? "").trim().toLowerCase();
  if (h.includes("://")) h = h.split("://")[1] || "";
  h = h.split("/")[0].split("@").pop() || "";
  if ((h.match(/:/g) || []).length === 1) h = h.split(":")[0];
  h = h.replace(/\.$/, "");
  if (!h || h.length > 253 || !/^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$/.test(h)) return "";
  if (/^[\d.]+$/.test(h)) return "";
  return h;
}

// Devuelve { provider, pr, apiBase } si el host es un preview reconocido; si no, null.
export function resolvePreviewBackend(hostname) {
  const host = normalizeHost(hostname);
  if (!host) return null;
  let m = COOLIFY_RE.exec(host);
  if (m) return { provider: "coolify", pr: m[1], apiBase: `https://${m[1]}.api.${COOLIFY_PREVIEW_DOMAIN}` };
  m = RENDER_RE.exec(host);
  if (m) return { provider: "render", pr: m[1], apiBase: `https://auditbrain-python-runner-pr-${m[1]}.onrender.com` };
  return null;
}
