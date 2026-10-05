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
    const esObj = detail && typeof detail === "object";
    const err = new Error(esObj ? (detail.message || JSON.stringify(detail)) : detail);
    // Conservar el detalle estructurado y el status para que el caller pueda reaccionar
    // (p. ej. 409 PRUEBA_ABIERTA_EXISTE → ofrecer «Modificar» la prueba existente).
    err.detail = detail;
    err.status = res.status;
    throw err;
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

// Análisis de estados financieros (NIA 315/520): horizontal, vertical, ratios,
// expectativa vs. real sobre los estados homologados.
export async function motorBalancesAnalisis(esf, eri, umbralPct = 0.1) {
  return parse(await apiFetch(`${API_BASE}/api/v1/aud/motor-balances/analisis`, {
    method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ esf, eri, umbral_pct: umbralPct }),
  }));
}

export async function motorBalancesAnalisisPapel(esf, eri, umbralPct = 0.1, formato = "xlsx") {
  const res = await apiFetch(`${API_BASE}/api/v1/aud/motor-balances/analisis/papel?formato=${formato}`, {
    method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ esf, eri, umbral_pct: umbralPct }),
  });
  return res.blob();
}

// Motor de Auditoría Analítica: Render solo firma el permiso; los datos van
// del navegador al motor (formulario AUT-2026-001, decisión X.2).
export async function motorAnaliticoPermiso(encargo, accion) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/aud/motor-analitico/permiso`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ encargo, accion }),
    })
  );
}
// ---- Descarga SRI (robot headless en el motor; el navegador llama al motor
// DIRECTO con el token firmado; la clave del cliente no pasa por Render). ----
// Normaliza para tolerar que MOTOR_ANALITICO_URL venga con o sin sufijo /motor.
function _motorBase(url) {
  return String(url || "").replace(/\/$/, "").replace(/\/motor$/, "");
}
function _motorHeaders(token, extra = {}) {
  return { Authorization: `Bearer ${token}`, ...extra };
}
// Vista en vivo del robot (MJPEG): un <img> no puede mandar cabecera
// Authorization, así que el permiso firmado va en el query string. Como se
// sirve por el mismo motor (Funnel), NO exige estar en la red Tailscale.
export function sriVivoUrl(url, token) {
  return `${_motorBase(url)}/motor/sri/vivo?permiso=${encodeURIComponent(token || "")}`;
}
export async function sriDescargar(url, token, params) {
  return parse(
    await apiFetch(`${_motorBase(url)}/motor/sri/descargar`, {
      method: "POST",
      headers: _motorHeaders(token, { "Content-Type": "application/json" }),
      body: JSON.stringify(params),
    })
  );
}
export async function sriEstado(url, token, id) {
  return parse(
    await apiFetch(`${_motorBase(url)}/motor/sri/trabajos/${id}`, {
      headers: _motorHeaders(token),
    })
  );
}
export async function sriEnviarCaptcha(url, token, id, codigo) {
  return parse(
    await apiFetch(`${_motorBase(url)}/motor/sri/trabajos/${id}/captcha`, {
      method: "POST",
      headers: _motorHeaders(token, { "Content-Type": "application/json" }),
      body: JSON.stringify({ codigo }),
    })
  );
}
export async function sriConsolidar(url, token, params) {
  return parse(
    await apiFetch(`${_motorBase(url)}/motor/sri/consolidar`, {
      method: "POST",
      headers: _motorHeaders(token, { "Content-Type": "application/json" }),
      body: JSON.stringify(params),
    })
  );
}
export async function sriHistorial(url, token) {
  return parse(
    await apiFetch(`${_motorBase(url)}/motor/sri/historial`, {
      headers: _motorHeaders(token),
    })
  );
}
// Descarga el ZIP de resultados: pide con el token, lo baja como blob.
export async function sriDescargarZip(url, token, id) {
  const res = await apiFetch(`${_motorBase(url)}/motor/sri/trabajos/${id}/zip`, {
    headers: _motorHeaders(token),
  });
  if (!res.ok) throw new Error("No hay archivos para descargar todavía.");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `sri_${id}.zip`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}
// Reconstrucción PDF→XML de Emitidos (offline, agrupa por mes).
export async function sriReconstruir(url, token, params) {
  return parse(
    await apiFetch(`${_motorBase(url)}/motor/sri/reconstruir-xml`, {
      method: "POST",
      headers: _motorHeaders(token, { "Content-Type": "application/json" }),
      body: JSON.stringify(params),
    })
  );
}
// Cruce retención ↔ factura (offline). direccion: "retenciones" | "facturas".
export async function sriCruceRetenciones(url, token, params) {
  return parse(
    await apiFetch(`${_motorBase(url)}/motor/sri/cruce-retenciones`, {
      method: "POST",
      headers: _motorHeaders(token, { "Content-Type": "application/json" }),
      body: JSON.stringify(params),
    })
  );
}
// Valor neto: factura − notas de crédito (offline).
export async function sriValorNeto(url, token, params) {
  return parse(
    await apiFetch(`${_motorBase(url)}/motor/sri/valor-neto`, {
      method: "POST",
      headers: _motorHeaders(token, { "Content-Type": "application/json" }),
      body: JSON.stringify(params),
    })
  );
}
// Descarga de una declaración presentada (login + captcha → trabajo async).
export async function sriDeclaracionesDescargar(url, token, params) {
  return parse(
    await apiFetch(`${_motorBase(url)}/motor/sri/declaraciones/descargar`, {
      method: "POST",
      headers: _motorHeaders(token, { "Content-Type": "application/json" }),
      body: JSON.stringify(params),
    })
  );
}
// Baja un archivo producido en el servidor (Excel/ZIP) por su ruta.
export async function sriDescargarArchivo(url, token, ruta, nombre) {
  const res = await apiFetch(
    `${_motorBase(url)}/motor/sri/archivo?ruta=${encodeURIComponent(ruta)}`,
    { headers: _motorHeaders(token) }
  );
  if (!res.ok) throw new Error("No se pudo descargar el archivo.");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nombre || String(ruta).split(/[/\\]/).pop() || "reporte.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}
// Un permiso "ejecutar" sirve para todos los endpoints SRI (leer y ejecutar).
export async function sriPermiso(encargo) {
  return motorAnaliticoPermiso(encargo, "ejecutar");
}


// ---- Fichas de diseño de herramientas NIIF (AUD) ----
// Viven en el backend, no en el navegador: el circuito exige que quien marca
// una ficha como «probada» pueda ser alguien distinto de quien la diseñó.

const NIIF_BASE = `${API_BASE}/api/v1/aud/niif/fichas`;

export async function niifListarFichas() {
  return parse(await apiFetch(NIIF_BASE, { headers: authHeaders() }));
}

export async function niifCrearFicha(ficha) {
  return parse(
    await apiFetch(NIIF_BASE, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(ficha),
    })
  );
}

export async function niifActualizarFicha(id, ficha) {
  return parse(
    await apiFetch(`${NIIF_BASE}/${id}`, {
      method: "PATCH",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(ficha),
    })
  );
}

export async function niifCambiarEstado(id, estado) {
  return parse(
    await apiFetch(`${NIIF_BASE}/${id}/estado`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ estado }),
    })
  );
}

export async function niifBorrarFicha(id, confirmarNombre) {
  return parse(
    await apiFetch(
      `${NIIF_BASE}/${id}?confirmar_nombre=${encodeURIComponent(confirmarNombre)}`,
      { method: "DELETE", headers: authHeaders() }
    )
  );
}

// Estudio de la prueba: cobertura del requerimiento de una ficha y corrida
// del motor de cálculo (el mismo archivo del sitio, vendorizado en backend).
export async function niifCobertura(id, documentos) {
  return parse(
    await apiFetch(`${NIIF_BASE}/${id}/cobertura`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ documentos }),
    })
  );
}

export async function niifEjecutarMotor({ definicion, filas, parametros, flujos }) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/aud/niif/motor/ejecutar`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ definicion, filas, parametros: parametros || {}, flujos: flujos || [] }),
    })
  );
}

// ---- Ciclo real de una prueba (E6: ficha del encargo y programa) ----
const CICLO = `${API_BASE}/api/v1/aud/ciclo`;
const jsonPost = (method, body) => ({
  method,
  headers: authHeaders({ "Content-Type": "application/json" }),
  body: JSON.stringify(body),
});

// Encargos NIIF: se eligen y crean dentro de la herramienta, sin depender del Workspace.
export async function cicloEncargos() {
  return parse(await apiFetch(`${CICLO}/encargos`, { headers: authHeaders() }));
}
export async function cicloCrearEncargo(datos) {
  return parse(await apiFetch(`${CICLO}/encargos`, jsonPost("POST", datos)));
}
export async function cicloLeerFicha(projectId) {
  return parse(await apiFetch(`${CICLO}/proyectos/${projectId}/ficha`, { headers: authHeaders() }));
}
export async function cicloGuardarFicha(projectId, ficha) {
  return parse(await apiFetch(`${CICLO}/proyectos/${projectId}/ficha`, jsonPost("PUT", ficha)));
}
export async function cicloHerramientas() {
  return parse(await apiFetch(`${CICLO}/herramientas`, { headers: authHeaders() }));
}
export async function cicloListarPruebas(projectId) {
  return parse(await apiFetch(`${CICLO}/proyectos/${projectId}/pruebas`, { headers: authHeaders() }));
}
export async function cicloCrearPrueba(projectId, origen, tributario) {
  return parse(await apiFetch(`${CICLO}/proyectos/${projectId}/pruebas`, jsonPost("POST", { origen, tributario })));
}
export async function cicloLeerPrueba(id) {
  return parse(await apiFetch(`${CICLO}/pruebas/${id}`, { headers: authHeaders() }));
}
export async function cicloAccion(id, accion, revision, datos = {}) {
  // Acciones que invocan al LLM: la extracción por IA de un documento y el
  // Procesar (map_validate), que auto-extrae los PDF/Word pendientes. El servidor
  // de IA local tarda por documento, y uno pesado (el informe/las notas = 5
  // llamadas) se alarga; con el default de 60s el cliente abortaba («No se pudo
  // conectar con el servidor»). Se les da una ventana amplia (600s) y SIN
  // reintentos (no re-POSTear un trabajo largo del modelo). El backend hace
  // failover a la nube si el local va lento; y si la nube está sin saldo, termina
  // en el local (más lento). Esta ventana cubre ese peor caso (sondeo + local).
  const invocaLLM = accion === "extraer_ia" || accion === "map_validate";
  const opts = invocaLLM ? { timeoutMs: 600000, retries: 0 } : {};
  return parse(await apiFetch(`${CICLO}/pruebas/${id}/acciones`, jsonPost("POST", { accion, revision, datos }), opts));
}
// E7: evidencia. El archivo va por formulario multiparte; el servidor lo guarda
// en su disco y devuelve su huella.
export async function cicloSubirArchivo(pruebaId, revision, requerimiento, componente, archivo) {
  const fd = new FormData();
  fd.append("revision", String(revision));
  fd.append("requerimiento", requerimiento);
  fd.append("componente", componente || "");
  fd.append("archivo", archivo);
  return parse(await apiFetch(`${CICLO}/pruebas/${pruebaId}/archivos`, { method: "POST", headers: authHeaders(), body: fd }));
}

// Diagnóstico de los proveedores de IA + ping EN VIVO al servidor local.
// Requiere sesión (JWT): por eso abrir la URL a pelo da "Not authenticated";
// desde aquí sí viaja el token. Devuelve {orden, preferido, configurados, local}.
export async function iaEstado() {
  return parse(await apiFetch(`${API_BASE}/api/v1/chat/ia/estado`, { headers: authHeaders() }));
}

// El original, tal cual se subió (para verlo o leer sus hojas en el navegador).
export async function cicloBajarArchivo(pruebaId, archivoId) {
  const res = await apiFetch(`${CICLO}/pruebas/${pruebaId}/archivos/${archivoId}`, { headers: authHeaders() });
  if (!res.ok) await parse(res);
  return new Uint8Array(await res.arrayBuffer());
}

// E9: el papel aprobado lo arma el navegador con el exportador del sitio y el
// servidor lo guarda una sola vez, con su huella.
// En una prueba declarativa van también el Word y el PowerPoint (`extra`).
// Papel de una prueba DECLARATIVA con el diseño de los procesadores: el navegador
// envía las cédulas con fórmulas del sitio (cargaPapel) y el servidor arma el
// Excel, HTML, Word, PowerPoint o PDF. No lee ni guarda nada.
export async function cicloPapelDeclarativo(carga, formato = "xlsx") {
  const res = await apiFetch(`${CICLO}/papel-declarativo?formato=${formato}`, jsonPost("POST", carga), { timeoutMs: 180000 });
  if (!res.ok) await parse(res);
  return new Uint8Array(await res.arrayBuffer());
}
// Papel aprobado de una prueba declarativa: el servidor lo arma y lo guarda con su huella.
export async function cicloGuardarPapelDeclarativo(pruebaId, revision, carga) {
  return parse(await apiFetch(`${CICLO}/pruebas/${pruebaId}/papel-declarativo`, jsonPost("POST", { revision, ...carga }), { timeoutMs: 180000 }));
}
// E10: modelo Excel de un requerimiento de cálculo, para enviarlo al cliente.
export async function cicloBajarModelo(pruebaId, requerimiento) {
  const res = await apiFetch(`${CICLO}/pruebas/${pruebaId}/modelo/${encodeURIComponent(requerimiento)}`, { headers: authHeaders() });
  if (!res.ok) await parse(res);
  return new Uint8Array(await res.arrayBuffer());
}
// Excel del papel en curso de una prueba con procesador: lo arma el servidor.
export async function cicloBajarLibro(pruebaId, formato = "xlsx", seccion = null) {
  // `seccion` (solo HTML de planificación): devuelve un HTML autónomo con SOLO esa
  // sección (Materialidad, Riesgos, …) en vez del papel completo.
  const q = seccion ? `&seccion=${encodeURIComponent(seccion)}` : "";
  const res = await apiFetch(`${CICLO}/pruebas/${pruebaId}/libro?formato=${formato}${q}`, { headers: authHeaders() });
  if (!res.ok) await parse(res);
  return new Uint8Array(await res.arrayBuffer());
}
// Papel de trabajo DA formulado de Efectivo y Equivalentes (fórmulas vivas): lo arma el servidor.
export async function cicloBajarPapelBancos(pruebaId) {
  const res = await apiFetch(`${CICLO}/pruebas/${pruebaId}/papel-bancos`, { headers: authHeaders() });
  if (!res.ok) await parse(res);
  return new Uint8Array(await res.arrayBuffer());
}
// Reproceso de la conciliación bancaria del último mes (Efectivo y Equivalentes): matriz por
// cuenta (banco, saldos, diferencia, estado, coincidencias) o { disponible:false, motivo }.
export async function cicloReproceso(pruebaId) {
  return parse(await apiFetch(`${CICLO}/pruebas/${pruebaId}/reproceso`, { headers: authHeaders() }));
}
// REPROCESO_CONCILIACION.xlsx: la matriz del reproceso por cuenta (cuadre por fórmula).
export async function cicloReprocesoExcel(pruebaId) {
  const res = await apiFetch(`${CICLO}/pruebas/${pruebaId}/reproceso-excel`, { headers: authHeaders() });
  if (!res.ok) await parse(res);
  return new Uint8Array(await res.arrayBuffer());
}
// Ejercicio modelo (solo lectura): el recorrido de 9 pasos con datos de ejemplo.
export async function cicloEjercicioModelo(pruebaId) {
  return parse(await apiFetch(`${CICLO}/pruebas/${pruebaId}/ejercicio-modelo`, { headers: authHeaders() }));
}
// Papel de muestra del ejercicio modelo (Excel/Word/PowerPoint/HTML).
export async function cicloEjercicioModeloLibro(pruebaId, formato = "xlsx") {
  const res = await apiFetch(`${CICLO}/pruebas/${pruebaId}/ejercicio-modelo/libro?formato=${formato}`, { headers: authHeaders() });
  if (!res.ok) await parse(res);
  return new Uint8Array(await res.arrayBuffer());
}
// Consola de revisión del auditor: recálculo independiente y veredicto de una planificación.
export async function cicloConsolaRevision(pruebaId) {
  return parse(await apiFetch(`${CICLO}/pruebas/${pruebaId}/consola-revision`, { headers: authHeaders() }));
}
// Consola-chat del piloto: guion del agente para el preparador o el auditor.
export async function cicloConsolaChat(pruebaId, rol = "preparador") {
  return parse(await apiFetch(`${CICLO}/pruebas/${pruebaId}/consola-chat?rol=${rol}`, { headers: authHeaders() }));
}
export async function cicloBandejas() {
  return parse(await apiFetch(`${CICLO}/bandejas`, { headers: authHeaders() }));
}

export async function cicloProcesadores() {
  return parse(await apiFetch(`${CICLO}/procesadores`, { headers: authHeaders() }));
}
export async function niifGuardarDefinicion(fichaId, definicion, filas, parametros) {
  return parse(await apiFetch(`${CICLO}/fichas/${fichaId}/definicion`, jsonPost("PUT", { definicion, filas, parametros: parametros || {} })));
}

// ---- Agente guía «NIIF Piloto» (un solo motor para todas las pruebas) ----
const PILOTO = `${API_BASE}/api/v1/aud/niif/piloto`;

export async function pilotoPruebas() {
  return parse(await apiFetch(`${PILOTO}/pruebas`, { headers: authHeaders() }));
}
export async function pilotoRequisitos(id) {
  return parse(await apiFetch(`${PILOTO}/pruebas/${encodeURIComponent(id)}/requisitos`, { headers: authHeaders() }));
}
export async function pilotoPlantilla(id) {
  return parse(await apiFetch(`${PILOTO}/pruebas/${encodeURIComponent(id)}/plantilla`, { headers: authHeaders() }));
}
// Ejecuta la prueba y devuelve el resultado + la verificación del Excel (formato=json).
export async function pilotoEjecutar(id, body) {
  return parse(
    await apiFetch(
      `${PILOTO}/pruebas/${encodeURIComponent(id)}/ejecutar?formato=json`,
      jsonPost("POST", body),
      { timeoutMs: 180000 }
    )
  );
}
// Descarga un formato del papel (xlsx/html/docx/pptx/pdf/zip). Dispara el guardado.
export async function pilotoDescargarPapel(id, body, formato, nombre) {
  const res = await apiFetch(
    `${PILOTO}/pruebas/${encodeURIComponent(id)}/ejecutar?formato=${encodeURIComponent(formato)}`,
    jsonPost("POST", body),
    { timeoutMs: 180000 }
  );
  if (!res.ok) await parse(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre || `${id}.${formato}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

// Consola de comunicación por prueba (chat auditable) sobre el ciclo.
export async function cicloComentarios(pruebaId) {
  return parse(await apiFetch(`${CICLO}/pruebas/${pruebaId}/comentarios`, { headers: authHeaders() }));
}
export async function cicloComentar(pruebaId, texto, asistente = false) {
  return parse(await apiFetch(`${CICLO}/pruebas/${pruebaId}/comentarios`, jsonPost("POST", { texto, asistente }), { timeoutMs: 120000 }));
}
// Puente planificación → pruebas del piloto (de una prueba de planificación).
export async function cicloPruebasSugeridas(pruebaId) {
  return parse(await apiFetch(`${CICLO}/pruebas/${pruebaId}/pruebas-sugeridas`, { headers: authHeaders() }, { timeoutMs: 180000 }));
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

// ---------- Cuentas de recursos gratuitos (staff lee; admin modifica) ----------

export async function listRecursoCuentas() {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/recursos/cuentas`, { headers: authHeaders() })
  );
}

export async function setRecursoAcceso(id, slug, on) {
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/recursos/cuentas/${id}/accesos/${encodeURIComponent(slug)}`,
      { method: on ? "PUT" : "DELETE", headers: authHeaders() }
    )
  );
}

export async function resetRecursoClave(id, newPassword, enviarCorreo) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/recursos/cuentas/${id}/reset-clave`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ new_password: newPassword || null, enviar_correo: !!enviarCorreo }),
    })
  );
}

export async function setRecursoActivo(id, activo) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/recursos/cuentas/${id}/activo`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ activo }),
    })
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

// --- Generación de imágenes/video ------------------------------------------
// El backend hace de proxy al puente ComfyUI del servidor local (time-sharing
// de la GPU). El frontend solo habla con el backend usando su sesión JWT — NO
// necesita Tailscale ni conoce la clave del puente.
export async function mediaStatus() {
  try {
    const d = await parse(
      await apiFetch(`${API_BASE}/api/v1/chat/media/status`, { headers: authHeaders() })
    );
    return Boolean(d && d.enabled);
  } catch {
    return false;
  }
}

export async function generateImage({ prompt, model = "flux", width = 1024, height = 1024 }) {
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/chat/media/image`,
      {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ prompt, model, width, height }),
      },
      { timeoutMs: 240000, retries: 0 } // la generación + swap tarda; no reintentar
    )
  );
}

export async function generateVideo({ prompt, width = 704, height = 480, length = 65 }) {
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/chat/media/video`,
      {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ prompt, width, height, length }),
      },
      { timeoutMs: 300000, retries: 0 }
    )
  );
}

// ---- Marketing-Tools (Creative Studio) ----
export async function removeBg(image_base64) {
  return parse(await apiFetch(`${API_BASE}/api/v1/chat/media/removebg`,
    { method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ image_base64 }) }, { timeoutMs: 120000, retries: 0 }));
}
export async function ttsGenerate(text) {
  return parse(await apiFetch(`${API_BASE}/api/v1/chat/media/tts`,
    { method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ text }) }, { timeoutMs: 120000, retries: 0 }));
}
export async function subtitleGenerate(audio_base64) {
  return parse(await apiFetch(`${API_BASE}/api/v1/chat/media/subtitle`,
    { method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ audio_base64 }) }, { timeoutMs: 180000, retries: 0 }));
}
export async function reelStart(file) {
  const fd = new FormData();
  fd.append("audio", file);
  return parse(await apiFetch(`${API_BASE}/api/v1/chat/media/reel`,
    { method: "POST", headers: authHeaders(), body: fd }, { timeoutMs: 120000, retries: 0 }));
}
export async function reelStatus(jid) {
  return parse(await apiFetch(`${API_BASE}/api/v1/chat/media/reel/${jid}`,
    { headers: authHeaders() }, { timeoutMs: 30000, retries: 1 }));
}
export async function reelOutput(jid, fmt) {
  const res = await apiFetch(`${API_BASE}/api/v1/chat/media/reel/${jid}/output?fmt=${fmt}`,
    { headers: authHeaders() }, { timeoutMs: 180000, retries: 0 });
  if (!res.ok) throw new Error("No se pudo descargar el reel.");
  return URL.createObjectURL(await res.blob());
}

// Sube un archivo y devuelve su texto extraído (no lo persiste en el servidor).
// { name, kind, chars, truncated, text }. Lanza si el archivo no se puede leer.
export async function extractAttachment(file) {
  const fd = new FormData();
  fd.append("file", file);
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/chat/attachments/extract`,
      { method: "POST", body: fd, headers: authHeaders() }, // el browser fija el boundary
      { timeoutMs: 120000 }
    )
  );
}

export async function sendChatMessage(conversationId, content, attachments = []) {
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/chat/conversations/${conversationId}/messages`,
      {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ content, attachments }),
      }
    )
  );
}

/**
 * Envía un mensaje y consume la respuesta en STREAMING (SSE), token por token.
 * No usa apiFetch: su AbortController (60s) y reintentos romperían/duplicarían
 * el stream. El JWT va en header (Authorization), por eso fetch+ReadableStream
 * en vez de EventSource nativo (que no admite headers).
 *
 * Callbacks: onUser(msg), onToken(text), onAssistant(msg), onError(detail).
 * Devuelve true si el stream se procesó; lanza si la conexión falla al abrir.
 */
export async function streamChatMessage(
  conversationId,
  content,
  { onUser, onToken, onAssistant, onError, onReasoning, attachments = [] } = {}
) {
  const res = await fetch(
    `${API_BASE}/api/v1/chat/conversations/${conversationId}/messages/stream`,
    {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ content, attachments }),
    }
  );
  if (res.status === 401) {
    clearSession();
    if (typeof window !== "undefined") window.location.reload();
    return false;
  }
  if (!res.ok || !res.body) {
    throw new Error(`HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const frames = buf.split("\n\n");
    buf = frames.pop(); // el último puede estar incompleto
    for (const frame of frames) {
      const lines = frame.split("\n");
      const evLine = lines.find((l) => l.startsWith("event:"));
      const dataLine = lines.find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      const ev = evLine ? evLine.slice(6).trim() : "message";
      let data;
      try {
        data = JSON.parse(dataLine.slice(5).trim());
      } catch {
        continue;
      }
      if (ev === "user_message") onUser?.(data);
      else if (ev === "reasoning") onReasoning?.();
      else if (ev === "token") onToken?.(data.text);
      else if (ev === "assistant_message") onAssistant?.(data);
      else if (ev === "error") onError?.(data.detail);
    }
  }
  return true;
}

// ---------- AUD.IMPUESTOS.OBLIGACIONES_FISCALES (ciclo de dos fases) ----------

const OF_BASE = `${API_BASE}/api/v1/aud/obligaciones-fiscales`;

// Crea el job en estado 'borrador'. Ya NO recibe archivos: esos se suben
// después, slot por slot, con subirSlotOF.
export async function crearJobOF(form) {
  const fd = new FormData();
  Object.entries(form).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") fd.append(k, v);
  });
  return parse(
    await apiFetch(`${OF_BASE}/jobs`, {
      method: "POST",
      headers: authHeaders(), // No Content-Type: el browser pone el boundary multipart
      body: fd,
    })
  );
}

// Sube (o reemplaza) los archivos de un slot. `archivos` es un array de
// File; todos viajan bajo el campo 'archivos'. `categoria` solo se agrega
// si viene (obligatoria para el slot mayor_especifico; el backend responde
// 400 si falta). Devuelve el estado de slots actualizado.
export async function subirSlotOF(jobId, slot, archivos, categoria) {
  const fd = new FormData();
  (archivos || []).forEach((f) => fd.append("archivos", f));
  if (categoria !== null && categoria !== undefined && categoria !== "") {
    fd.append("categoria", categoria);
  }
  return parse(
    await apiFetch(`${OF_BASE}/jobs/${jobId}/slots/${slot}`, {
      method: "PUT",
      headers: authHeaders(),
      body: fd,
    })
  );
}

// Borra los archivos de un slot. Devuelve el estado de slots actualizado.
export async function quitarSlotOF(jobId, slot) {
  return parse(
    await apiFetch(`${OF_BASE}/jobs/${jobId}/slots/${slot}`, {
      method: "DELETE",
      headers: authHeaders(),
    })
  );
}

// Estado de todos los slots: { slot: { n_archivos, nombres } }.
export async function estadoSlotsOF(jobId) {
  return parse(
    await apiFetch(`${OF_BASE}/jobs/${jobId}/slots`, {
      headers: authHeaders(),
    })
  );
}

// Fase 1: clasifica el Mayor General y deja el job en 'revision'.
export async function procesarOF(jobId) {
  return parse(
    await apiFetch(`${OF_BASE}/jobs/${jobId}/procesar`, {
      method: "POST",
      headers: authHeaders(),
    })
  );
}

// Cuentas propuestas por el motor + catálogo de categorías, para la
// pantalla de revisión de la clasificación.
export async function getClasificacionOF(jobId) {
  return parse(
    await apiFetch(`${OF_BASE}/jobs/${jobId}/clasificacion`, {
      headers: authHeaders(),
    })
  );
}

// Guarda las correcciones del auditor. `correcciones` es un array de
// { codigo_cuenta, categoria } — solo las cuentas que cambiaron.
export async function guardarCorreccionesOF(jobId, correcciones) {
  return parse(
    await apiFetch(`${OF_BASE}/jobs/${jobId}/clasificacion`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ correcciones: correcciones || [] }),
    })
  );
}

// Fase 2: persiste lo aprendido y genera el Excel. Deja el job en 'done'.
export async function aprobarOF(jobId) {
  return parse(
    await apiFetch(`${OF_BASE}/jobs/${jobId}/aprobar`, {
      method: "POST",
      headers: authHeaders(),
    })
  );
}

// `procesar` y `aprobar` disparan el trabajo pesado en segundo plano y
// responden al instante con el job en 'running'. Este helper consulta el
// estado del job hasta que llega a uno de los `estadosFinales` (p.ej.
// 'revision' tras procesar, 'done' tras aprobar) o hasta agotar el tiempo.
// Un Mayor grande puede tardar varios minutos en clasificarse/generarse.
export async function esperarEstadoOF(
  jobId,
  estadosFinales,
  { intervalMs = 2500, timeoutMs = 15 * 60 * 1000 } = {}
) {
  const finales = new Set(estadosFinales);
  const limite = Date.now() + timeoutMs;
  // Espera inicial breve: el background suele estar listo enseguida en
  // encargos chicos.
  for (;;) {
    const job = await getObligacionesFiscalesJob(jobId);
    if (finales.has(job.status) || job.status === "failed") return job;
    if (Date.now() >= limite) return job; // se devuelve el último estado visto
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

// Catálogo de categorías disponibles (para los selects de clasificación).
export async function listarCategoriasOF() {
  return parse(await apiFetch(`${OF_BASE}/categorias`, { headers: authHeaders() }));
}

// Actualiza los metadatos del encargo (cliente, período, corte, preparado/
// revisado por, firma auditora) SIN tocar archivos ni clasificación. Solo
// se envían los campos presentes en `form` (el backend actualiza solo eso).
export async function actualizarJobOF(jobId, form) {
  return parse(
    await apiFetch(`${OF_BASE}/jobs/${jobId}`, {
      method: "PATCH",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(form),
    })
  );
}

// Borra el job (y sus archivos en /tmp). El backend YA expone este endpoint
// (DELETE /jobs/{id}); se agrega el wrapper acá porque el workspace lo
// necesita para "🔄 Encerar" (empezar el encargo desde cero, incluyendo los
// documentos subidos).
export async function eliminarJobOF(jobId) {
  const res = await apiFetch(`${OF_BASE}/jobs/${jobId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok && res.status !== 204) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* sin body */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
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
// Registros del encargo con un clic (independencia, discusión, aceptación, carta, comunicación) y sus documentos.
export async function cicloRegistros(projectId) {
  return parse(await apiFetch(`${CICLO}/proyectos/${projectId}/registros`, { headers: authHeaders() }));
}
export async function cicloRegistrar(projectId, datos) {
  return parse(await apiFetch(`${CICLO}/proyectos/${projectId}/registros`, jsonPost("POST", datos)));
}
export async function cicloAnularRegistro(projectId, registroId) {
  return parse(await apiFetch(`${CICLO}/proyectos/${projectId}/registros/${registroId}`, { method: "DELETE", headers: authHeaders() }));
}
export async function cicloDocumentoEncargo(projectId, tipo) {
  const res = await apiFetch(`${CICLO}/proyectos/${projectId}/documentos/${tipo}`, { headers: authHeaders() });
  if (!res.ok) await parse(res);
  return new Uint8Array(await res.arrayBuffer());
}
export async function cicloResolverConsulta(projectId, registroId, resolucion) {
  return parse(await apiFetch(`${CICLO}/proyectos/${projectId}/registros/${registroId}/resolver`, jsonPost("POST", { resolucion })));
}
