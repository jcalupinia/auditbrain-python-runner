import { describe, expect, it } from "vitest";
import { CATEGORIES } from "./catalog.js";
import { carteraMedida } from "./pceCxc.js";

describe("catálogo AUD", () => {
  it("la tarjeta de Cuentas por cobrar ya no está vacía", () => {
    const cxc = CATEGORIES.find((c) => c.id === "CXC");
    expect(cxc.tools).toBeDefined();
    expect(cxc.tools[0].id).toBe("AUD.CXC.PCE");
  });

  it("conserva su identificador, etiqueta y tipo", () => {
    const cxc = CATEGORIES.find((c) => c.id === "CXC");
    expect(cxc.label).toBe("Cuentas por cobrar");
    expect(cxc.type).toBe("ciclo");
  });
});

describe("carteraMedida", () => {
  it("con exposición sin medir y sin estratificar en cero, retorna el total", () => {
    const total = 1000000;
    const resultado = carteraMedida(total, 0, 0);
    expect(resultado).toBe(total);
  });

  it("con exposición sin medir, la resta del total", () => {
    const total = 1000000;
    const sinMedir = 100000;
    const resultado = carteraMedida(total, sinMedir, 0);
    expect(resultado).toBe(total - sinMedir);
  });

  it("con exposición sin estratificar, también la resta del total", () => {
    const total = 1000000;
    const sinEstratificar = 50000;
    const resultado = carteraMedida(total, 0, sinEstratificar);
    expect(resultado).toBe(total - sinEstratificar);
  });

  it("con ambas exposiciones, resta las dos del total", () => {
    const total = 1000000;
    const sinMedir = 100000;
    const sinEstratificar = 50000;
    const resultado = carteraMedida(total, sinMedir, sinEstratificar);
    expect(resultado).toBe(total - sinMedir - sinEstratificar);
  });

  it("retorna null si total es null", () => {
    const resultado = carteraMedida(null, 100000, 50000);
    expect(resultado).toBeNull();
  });
});
