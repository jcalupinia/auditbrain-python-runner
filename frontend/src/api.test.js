// Tests del cliente de la API de dos fases de AUD.IMPUESTOS.OBLIGACIONES_FISCALES.
// Entorno "node" (vitest.config.js): sin localStorage/DOM reales, así que se
// stubea localStorage mínimamente antes de importar api.js (usa getToken()
// vía localStorage.getItem en cada request autenticado).

import { beforeEach, describe, expect, it, vi } from "vitest";

globalThis.localStorage = {
  store: {},
  getItem(k) {
    return Object.prototype.hasOwnProperty.call(this.store, k) ? this.store[k] : null;
  },
  setItem(k, v) {
    this.store[k] = String(v);
  },
  removeItem(k) {
    delete this.store[k];
  },
};

const api = await import("./api.js");

function jsonResponse(body, { status = 200, url = "" } = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("API de Obligaciones Fiscales (ciclo de dos fases)", () => {
  beforeEach(() => {
    globalThis.localStorage.store = {};
    globalThis.localStorage.setItem("ab_token", "token-de-prueba");
    vi.restoreAllMocks();
  });

  it("crearJobOF hace POST a /jobs con FormData y sin campos vacíos", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: 7, status: "borrador" }));

    const job = await api.crearJobOF({
      project_id: 1,
      cliente_name: "ACME S.A.",
      period_label: "Ejercicio 2025",
      period_end: "",
      prepared_by_name: null,
    });

    expect(job).toEqual({ id: 7, status: "borrador" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/aud\/obligaciones-fiscales\/jobs$/);
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeInstanceOf(FormData);
    expect(opts.body.get("cliente_name")).toBe("ACME S.A.");
    expect(opts.body.has("period_end")).toBe(false);
    expect(opts.body.has("prepared_by_name")).toBe(false);
    expect(opts.headers.Authorization).toBe("Bearer token-de-prueba");
  });

  it("subirSlotOF arma FormData con 'archivos' y agrega 'categoria' solo si viene", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ mayor_especifico: { n_archivos: 1, nombres: ["x.xlsx"] } }));

    const archivo = new File(["contenido"], "x.xlsx");
    await api.subirSlotOF(7, "mayor_especifico", [archivo], "activos_fijos");

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/jobs\/7\/slots\/mayor_especifico$/);
    expect(opts.method).toBe("PUT");
    expect(opts.body.getAll("archivos")).toHaveLength(1);
    expect(opts.body.get("categoria")).toBe("activos_fijos");
  });

  it("subirSlotOF no agrega 'categoria' cuando no viene", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ f104: { n_archivos: 2, nombres: ["a.pdf", "b.pdf"] } }));

    await api.subirSlotOF(7, "f104", [new File(["a"], "a.pdf"), new File(["b"], "b.pdf")]);

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.body.getAll("archivos")).toHaveLength(2);
    expect(opts.body.has("categoria")).toBe(false);
  });

  it("quitarSlotOF hace DELETE al slot correcto", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({}));
    await api.quitarSlotOF(7, "f101");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/jobs\/7\/slots\/f101$/);
    expect(opts.method).toBe("DELETE");
  });

  it("estadoSlotsOF hace GET a /jobs/{id}/slots", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ f104: { n_archivos: 0, nombres: [] } }));
    await api.estadoSlotsOF(7);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/jobs\/7\/slots$/);
    expect(opts.method ?? "GET").toBe("GET");
  });

  it("procesarOF hace POST a /jobs/{id}/procesar", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ id: 7, status: "revision" }));
    const job = await api.procesarOF(7);
    expect(job.status).toBe("revision");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/jobs\/7\/procesar$/);
    expect(opts.method).toBe("POST");
  });

  it("getClasificacionOF hace GET a /jobs/{id}/clasificacion", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ job_id: 7, status: "revision", cuentas: [], categorias: [] }));
    await api.getClasificacionOF(7);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/jobs\/7\/clasificacion$/);
  });

  it("guardarCorreccionesOF hace PUT con JSON {correcciones}", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ job_id: 7, status: "revision", cuentas: [], categorias: [] }));
    await api.guardarCorreccionesOF(7, [{ codigo_cuenta: "1.1.01", categoria: "caja_bancos" }]);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/jobs\/7\/clasificacion$/);
    expect(opts.method).toBe("PUT");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(opts.body)).toEqual({
      correcciones: [{ codigo_cuenta: "1.1.01", categoria: "caja_bancos" }],
    });
  });

  it("guardarCorreccionesOF envía lista vacía cuando no hay correcciones", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ job_id: 7, status: "revision", cuentas: [], categorias: [] }));
    await api.guardarCorreccionesOF(7, []);
    const [, opts] = fetchMock.mock.calls[0];
    expect(JSON.parse(opts.body)).toEqual({ correcciones: [] });
  });

  it("actualizarJobOF hace PATCH con JSON a /jobs/{id} (edita metadatos sin tocar archivos)", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: 7, status: "borrador", cliente_name: "Nuevo" }));
    const job = await api.actualizarJobOF(7, { cliente_name: "Nuevo", prepared_by_name: null });
    expect(job.cliente_name).toBe("Nuevo");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/jobs\/7$/);
    expect(opts.method).toBe("PATCH");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(opts.body)).toEqual({ cliente_name: "Nuevo", prepared_by_name: null });
  });

  it("aprobarOF hace POST a /jobs/{id}/aprobar", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ id: 7, status: "done" }));
    const job = await api.aprobarOF(7);
    expect(job.status).toBe("done");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/jobs\/7\/aprobar$/);
    expect(opts.method).toBe("POST");
  });

  it("listarCategoriasOF hace GET a /categorias (fuera de /jobs)", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([{ codigo: "caja_bancos", nombre: "Caja y bancos" }]));
    const categorias = await api.listarCategoriasOF();
    expect(categorias).toEqual([{ codigo: "caja_bancos", nombre: "Caja y bancos" }]);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/aud\/obligaciones-fiscales\/categorias$/);
    expect(url).not.toMatch(/\/jobs\//);
  });

  it("propaga el mensaje de error del backend cuando la respuesta no es ok (ej. 400 sin categoria)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(
        { detail: "El mayor específico exige declarar la categoria a la que pertenece." },
        { status: 400 }
      )
    );
    await expect(api.subirSlotOF(7, "mayor_especifico", [new File(["a"], "a.xlsx")])).rejects.toThrow(
      /categoria a la que pertenece/
    );
  });
});

describe("API de cuentas de recursos (consola REC)", () => {
  beforeEach(() => {
    globalThis.localStorage.store = {};
    globalThis.localStorage.setItem("ab_token", "token-de-prueba");
    vi.restoreAllMocks();
  });

  it("setRecursoAcceso(on=true) hace PUT al acceso del recurso", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ ok: true, accesos: ["anticipo-ir-2026"] }));
    const res = await api.setRecursoAcceso(5, "anticipo-ir-2026", true);
    expect(res.accesos).toEqual(["anticipo-ir-2026"]);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/recursos\/cuentas\/5\/accesos\/anticipo-ir-2026$/);
    expect(opts.method).toBe("PUT");
    expect(opts.headers.Authorization).toBe("Bearer token-de-prueba");
  });

  it("setRecursoAcceso(on=false) hace DELETE al acceso del recurso", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ ok: true, accesos: [] }));
    await api.setRecursoAcceso(5, "anticipo-ir-2026", false);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/recursos\/cuentas\/5\/accesos\/anticipo-ir-2026$/);
    expect(opts.method).toBe("DELETE");
  });

  it("resetRecursoClave con clave vacía envía new_password null y enviar_correo", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ email: "a@b.ec", temp_password: "X", note: "n" }));
    await api.resetRecursoClave(5, "", true);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/recursos\/cuentas\/5\/reset-clave$/);
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ new_password: null, enviar_correo: true });
  });

  it("resetRecursoClave envía la clave escrita por el admin", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ email: "a@b.ec", temp_password: "Abcdefgh1", note: "n" }));
    await api.resetRecursoClave(5, "Abcdefgh1", false);
    const [, opts] = fetchMock.mock.calls[0];
    expect(JSON.parse(opts.body)).toEqual({ new_password: "Abcdefgh1", enviar_correo: false });
  });
});

describe("API de cuentas de Automatizaciones (consola AUT)", () => {
  beforeEach(() => {
    globalThis.localStorage.store = {};
    globalThis.localStorage.setItem("ab_token", "token-de-prueba");
    vi.restoreAllMocks();
  });

  it("listAutCuentas sin client_id hace GET sin query", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([]));
    await api.listAutCuentas();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/staff\/automatizaciones\/cuentas$/);
    expect(opts.headers.Authorization).toBe("Bearer token-de-prueba");
  });

  it("listAutCuentas con client_id agrega el query param", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([]));
    await api.listAutCuentas(9);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/staff\/automatizaciones\/cuentas\?client_id=9$/);
  });

  it("createAutCuenta hace POST con el payload en JSON", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: 1, estado: "activa" }));
    const payload = {
      client_id: 9,
      herramienta: "PRESUPUESTOS_IA",
      empresa_nombre: "ACME S.A.",
      admin_nombre: "Ana",
      admin_email: "ana@acme.ec",
      vigencia_hasta: null,
    };
    await api.createAutCuenta(payload);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/staff\/automatizaciones\/cuentas$/);
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(opts.body)).toEqual(payload);
  });

  it("reenviarAccesoAut, suspenderAut y reactivarAut hacen POST a su acción", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => Promise.resolve(jsonResponse({ id: 3 })));
    await api.reenviarAccesoAut(3);
    await api.suspenderAut(3);
    await api.reactivarAut(3);
    const urls = fetchMock.mock.calls.map((c) => c[0]);
    expect(urls[0]).toMatch(/\/cuentas\/3\/reenviar-acceso$/);
    expect(urls[1]).toMatch(/\/cuentas\/3\/suspender$/);
    expect(urls[2]).toMatch(/\/cuentas\/3\/reactivar$/);
    fetchMock.mock.calls.forEach((c) => expect(c[1].method).toBe("POST"));
  });

  it("refrescarEmpresaAut hace POST a refrescar-empresa", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ id: 3 }));
    await api.refrescarEmpresaAut(3);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/cuentas\/3\/refrescar-empresa$/);
    expect(opts.method).toBe("POST");
  });

  it("borrarAutCuenta hace DELETE con confirmado=true", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ ok: true }));
    await api.borrarAutCuenta(3);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/cuentas\/3\?confirmado=true$/);
    expect(opts.method).toBe("DELETE");
  });
});
