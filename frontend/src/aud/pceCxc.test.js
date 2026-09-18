import { describe, expect, it } from "vitest";
import { CATEGORIES } from "./catalog.js";

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
