// Resolución del backend de preview por hostname (frontend/src/previewResolver.js).
import { describe, expect, it } from "vitest";

import { normalizeHost, resolvePreviewBackend } from "./previewResolver.js";

describe("normalizeHost", () => {
  it("canoniza mayúsculas, espacios, punto final, puerto, esquema y ruta", () => {
    expect(normalizeHost("  123.CONSOLA.Preview.Audit-IA.ec. ")).toBe("123.consola.preview.audit-ia.ec");
    expect(normalizeHost("123.consola.preview.audit-ia.ec:8443")).toBe("123.consola.preview.audit-ia.ec");
    expect(normalizeHost("https://123.consola.preview.audit-ia.ec/ruta?x=1")).toBe("123.consola.preview.audit-ia.ec");
  });
  it("rechaza IPs literales, guiones bajos y vacíos", () => {
    expect(normalizeHost("127.0.0.1")).toBe("");
    expect(normalizeHost("algo_raro.example.com")).toBe("");
    expect(normalizeHost("")).toBe("");
    expect(normalizeHost(undefined)).toBe("");
  });
});

describe("resolvePreviewBackend", () => {
  it("Coolify: consola y portal del PR n apuntan al backend del MISMO PR", () => {
    expect(resolvePreviewBackend("123.consola.preview.audit-ia.ec")).toEqual({
      provider: "coolify", pr: "123", apiBase: "https://123.api.preview.audit-ia.ec",
    });
    expect(resolvePreviewBackend("123.CLIENTES.preview.audit-ia.ec.")).toEqual({
      provider: "coolify", pr: "123", apiBase: "https://123.api.preview.audit-ia.ec",
    });
  });
  it("Render (compatibilidad temporal)", () => {
    expect(resolvePreviewBackend("auditbrain-frontend-pr-55.onrender.com").apiBase)
      .toBe("https://auditbrain-python-runner-pr-55.onrender.com");
    expect(resolvePreviewBackend("auditbrain-clientes-pr-55.onrender.com").pr).toBe("55");
  });
  it("cualquier otro host devuelve null (nunca producción)", () => {
    for (const h of [
      "consola.audit-ia.ec", "clientes.audit-ia.ec", "api.audit-ia.ec", "localhost",
      "consola.preview.audit-ia.ec", "123.api.preview.audit-ia.ec", "x123.consola.preview.audit-ia.ec",
      "123.consola.preview.audit-ia.ec.evil.tld", "evil.123.consola.preview.audit-ia.ec",
      "auditbrain-frontend.onrender.com", "auditbrain-frontend-pr-x.onrender.com", "",
    ]) {
      expect(resolvePreviewBackend(h), h).toBeNull();
    }
  });
});
