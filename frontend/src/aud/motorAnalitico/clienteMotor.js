import { motorAnaliticoPermiso } from "../../api.js";

/* Cliente del Motor de Auditoría Analítica (SP2).
   Render firma un permiso de 5 min; el navegador llama directo al motor.
   Si el auditor está en Tailscale, Chrome retiene la petición hasta que
   autoriza el «acceso a la red local»: eso se ve como una espera sin
   respuesta y se informa como `red_local`. */

export const ESPERA_MS = 8000;        // solo lecturas: /estado, /trabajos/{id}, /excepciones
export const SONDEO_MS = 5000;        // el motor admite 30 peticiones/min por usuario
export const LIMITE_ARCHIVO_BYTES = 50 * 1024 * 1024; // mismo límite que servicio/app.py::MAX_BYTES
const MARGEN_MS = 30000;

// Un archivo de más de 50 MB se rechaza en el navegador antes de subir: si
// la subida tarda más que cualquier reloj, el navegador la corta pero el
// motor ya creó el trabajo (id perdido, cupo de 3 trabajos gastado en vano).
export function archivoDemasiadoGrande(archivo, limite = LIMITE_ARCHIVO_BYTES) {
  return archivo.size > limite;
}

export class ErrorMotor extends Error {
  constructor(estado, mensaje) {
    super(mensaje);
    this.estado = estado;
  }
}

export function filtrosAQuery(filtros = {}) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(filtros)) {
    const texto = v === undefined || v === null ? "" : String(v).trim();
    if (texto) q.set(k, texto);
  }
  return q.toString();
}

async function conEspera(fetchImpl, url, opts, ms) {
  const ctrl = new AbortController();
  const reloj = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetchImpl(url, { ...opts, signal: ctrl.signal });
  } finally {
    clearTimeout(reloj);
  }
}

async function detalle(res) {
  try {
    const d = await res.json();
    return typeof d?.detail === "string" ? d.detail : `HTTP ${res.status}`;
  } catch {
    return `HTTP ${res.status}`;
  }
}

export function crearCliente({
  encargo,
  pedirPermiso = motorAnaliticoPermiso,
  fetchImpl = (...a) => fetch(...a),
  ahora = () => Date.now(),
  esperaMs = ESPERA_MS,
}) {
  const cache = {};

  async function permiso(accion) {
    const c = cache[accion];
    if (c && c.vence - ahora() > MARGEN_MS) return c;
    const p = await pedirPermiso(encargo, accion);
    cache[accion] = { token: p.token, url: p.url, vence: ahora() + p.expira_en * 1000 };
    return cache[accion];
  }

  // `sinLimite`: la creación de un trabajo (subida de archivo) se manda sin
  // AbortController — una subida de 50 MB puede tardar más que cualquier
  // reloj razonable y el motor ya creó el trabajo cuando el navegador corta
  // por timeout; mejor dejar que la red maneje la caída. `ms`/ESPERA_MS
  // queda solo para las lecturas (trabajo, excepciones, estado).
  async function llamar(accion, ruta, opts = {}, { blob = false, ms = esperaMs, sinLimite = false } = {}) {
    const { token, url } = await permiso(accion);
    const conAuth = { ...opts, headers: { ...(opts.headers || {}), Authorization: `Bearer ${token}` } };
    const res = sinLimite
      ? await fetchImpl(`${url}${ruta}`, conAuth)
      : await conEspera(fetchImpl, `${url}${ruta}`, conAuth, ms);
    if (!res.ok) throw new ErrorMotor(res.status, await detalle(res));
    return blob ? res.blob() : res.json();
  }

  return {
    permiso,
    async estado() {
      const { url } = await permiso("leer");
      const res = await conEspera(fetchImpl, `${url}/estado`, {}, esperaMs);
      if (!res.ok) throw new ErrorMotor(res.status, await detalle(res));
      return res.json();
    },
    crearDemo() {
      const fd = new FormData();
      fd.append("demo", "1");
      return llamar("ejecutar", "/trabajos", { method: "POST", body: fd }, { sinLimite: true });
    },
    crearConArchivo(archivo) {
      const fd = new FormData();
      fd.append("archivo", archivo);
      return llamar("ejecutar", "/trabajos", { method: "POST", body: fd }, { sinLimite: true });
    },
    crearConMayor(archivo, parametros, balance) {
      const fd = new FormData();
      fd.append("origen", "mayor");
      fd.append("archivo", archivo);
      fd.append("parametros", JSON.stringify(parametros));
      if (balance) fd.append("balance", balance);
      return llamar("ejecutar", "/trabajos", { method: "POST", body: fd }, { sinLimite: true });
    },
    trabajo: (id) => llamar("leer", `/trabajos/${encodeURIComponent(id)}`),
    excepciones: (id, filtros) =>
      llamar("leer", `/trabajos/${encodeURIComponent(id)}/excepciones?${filtrosAQuery(filtros)}`),
    plantilla: () => llamar("leer", "/plantilla", {}, { blob: true }),
  };
}

export async function disponibilidad(cliente) {
  try {
    await cliente.permiso("leer");
  } catch (e) {
    return { estado: "sin_permiso", detalle: e.message };
  }
  try {
    await cliente.estado();
    return { estado: "disponible" };
  } catch (e) {
    if (e?.name === "AbortError") return { estado: "red_local" };
    return { estado: "caido" };
  }
}
