import { describe, expect, it, vi } from "vitest";
import { ErrorMotor, crearCliente, disponibilidad, filtrosAQuery } from "./clienteMotor.js";

const URL_MOTOR = "https://motor.test/motor";

function permisos() {
  const pedidos = [];
  const pedir = vi.fn(async (encargo, accion) => {
    pedidos.push([encargo, accion]);
    return { token: `tok-${accion}-${pedidos.length}`, url: URL_MOTOR, expira_en: 300 };
  });
  return { pedir, pedidos };
}

const ok = (cuerpo) => ({ ok: true, status: 200, json: async () => cuerpo, blob: async () => new Blob(["x"]) });

describe("clienteMotor", () => {
  it("reutiliza el permiso hasta 30 s antes de vencer", async () => {
    const { pedir, pedidos } = permisos();
    let t = 0;
    const fetchImpl = vi.fn(async () => ok({ id: "t1" }));
    const c = crearCliente({ encargo: "proyecto-7", pedirPermiso: pedir, fetchImpl, ahora: () => t });
    await c.trabajo("t1");
    t = 269_000;
    await c.trabajo("t1");
    expect(pedidos).toEqual([["proyecto-7", "leer"]]);
    t = 271_000;
    await c.trabajo("t1");
    expect(pedidos.length).toBe(2);
    expect(fetchImpl.mock.calls[2][1].headers.Authorization).toBe("Bearer tok-leer-2");
  });

  it("usa permisos distintos para leer y ejecutar", async () => {
    const { pedir, pedidos } = permisos();
    const fetchImpl = vi.fn(async () => ok({ id: "t1", estado: "en_cola" }));
    const c = crearCliente({ encargo: "p", pedirPermiso: pedir, fetchImpl });
    await c.crearDemo();
    expect(pedidos).toEqual([["p", "ejecutar"]]);
    const [url, opts] = fetchImpl.mock.calls[0];
    expect(url).toBe(`${URL_MOTOR}/trabajos`);
    expect(opts.method).toBe("POST");
    expect(opts.body.get("demo")).toBe("1");
  });

  it("arma la consulta de excepciones sin filtros vacíos", () => {
    expect(filtrosAQuery({ pagina: 2, tam: 50, severidad: "", regla: "GAS-006", texto: " andes " }))
      .toBe("pagina=2&tam=50&regla=GAS-006&texto=andes");
  });

  it("convierte respuestas de error en ErrorMotor con estado", async () => {
    const { pedir } = permisos();
    const fetchImpl = vi.fn(async () => ({ ok: false, status: 409, json: async () => ({ detail: "el trabajo no ha terminado" }) }));
    const c = crearCliente({ encargo: "p", pedirPermiso: pedir, fetchImpl });
    const error = await c.excepciones("t1", {}).catch((e) => e);
    expect(error).toBeInstanceOf(ErrorMotor);
    expect(error.estado).toBe(409);
    expect(error.message).toBe("el trabajo no ha terminado");
  });
});

describe("disponibilidad", () => {
  const cliente = (fetchImpl, pedir = permisos().pedir) =>
    crearCliente({ encargo: "p", pedirPermiso: pedir, fetchImpl, esperaMs: 20 });

  it("disponible cuando /estado responde", async () => {
    expect(await disponibilidad(cliente(async () => ok({ ok: true })))).toEqual({ estado: "disponible" });
  });

  it("red_local cuando la petición queda retenida", async () => {
    const colgado = (url, { signal }) => new Promise((_, rechazar) =>
      signal.addEventListener("abort", () => rechazar(new DOMException("abortado", "AbortError"))));
    expect((await disponibilidad(cliente(colgado))).estado).toBe("red_local");
  });

  it("caido ante error de red o 5xx", async () => {
    expect((await disponibilidad(cliente(async () => { throw new TypeError("Failed to fetch"); }))).estado).toBe("caido");
    expect((await disponibilidad(cliente(async () => ({ ok: false, status: 502, json: async () => ({}) })))).estado).toBe("caido");
  });

  it("sin_permiso cuando Render no emite el permiso", async () => {
    const pedir = async () => { throw new Error("El Motor de Auditoría Analítica no está configurado."); };
    const r = await disponibilidad(cliente(async () => ok({}), pedir));
    expect(r).toEqual({ estado: "sin_permiso", detalle: "El Motor de Auditoría Analítica no está configurado." });
  });
});
