// Prueba del resolver del portal sin dependencias: `node --test frontend-client/src/previewResolver.test.mjs`
import assert from "node:assert/strict";
import { test } from "node:test";

import { normalizeHost, resolvePreviewBackend } from "./previewResolver.js";

test("normalizeHost canoniza y rechaza valores inválidos", () => {
  assert.equal(normalizeHost("  123.CLIENTES.Preview.Audit-IA.ec. "), "123.clientes.preview.audit-ia.ec");
  assert.equal(normalizeHost("https://123.clientes.preview.audit-ia.ec:443/x"), "123.clientes.preview.audit-ia.ec");
  assert.equal(normalizeHost("127.0.0.1"), "");
  assert.equal(normalizeHost("algo_raro.ec"), "");
});

test("Coolify: el portal del PR n usa el backend del MISMO PR", () => {
  assert.deepEqual(resolvePreviewBackend("123.clientes.preview.audit-ia.ec"), {
    provider: "coolify", pr: "123", apiBase: "https://123.api.preview.audit-ia.ec",
  });
});

test("Render (compatibilidad temporal)", () => {
  assert.equal(resolvePreviewBackend("auditbrain-clientes-pr-55.onrender.com").apiBase,
    "https://auditbrain-python-runner-pr-55.onrender.com");
});

test("cualquier otro host devuelve null (nunca producción)", () => {
  for (const h of [
    "clientes.audit-ia.ec", "api.audit-ia.ec", "clientes.preview.audit-ia.ec", "123.api.preview.audit-ia.ec",
    "123.clientes.preview.audit-ia.ec.evil.tld", "auditbrain-clientes.onrender.com", "", "localhost",
  ]) {
    assert.equal(resolvePreviewBackend(h), null, h);
  }
});
