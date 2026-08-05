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
