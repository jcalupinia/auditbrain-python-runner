import test from "node:test";
import assert from "node:assert/strict";
import { buildHandoffContext, resolveExecutionModes, serializeHandoff } from "../handoff.mjs";

test("ChatGPT remains default when optional modes are unavailable", () => {
  const modes = resolveExecutionModes({ chatgpt: true, work: false, codex: false, astra: false });
  assert.deepEqual(modes.map(m => [m.id,m.available]), [["chatgpt",true],["work",false],["codex",false],["astra",false]]);
  assert.equal(modes[0].recommended, true);
});

test("unknown framework and repository remain pending instead of invented", () => {
  const ctx = buildHandoffContext({ tool: { id: "INV-VNR", name: "VNR" }, repository: { verified: false } });
  assert.equal(ctx.framework.type, "PENDIENTE");
  assert.equal(ctx.repository.verified, false);
  assert.equal(ctx.repository.fullName, "PENDIENTE");
});

test("handoff does not embed client evidence payload", () => {
  const ctx = buildHandoffContext({ sourceRefs: [{ name: "Inventario", ref: "file-1", status: "validado", content: "SECRET" }] });
  assert.equal(ctx.privacy.embedsClientEvidence, false);
  assert.equal(JSON.stringify(ctx).includes("SECRET"), false);
});

test("serialized context carries methodology and operational rule", () => {
  const ctx = buildHandoffContext({ methodologyVersion: "1.2.0", requestedChange: "Actualizar VNR" });
  const md = serializeHandoff(ctx);
  assert.match(md, /Memoria metodológica: v1\.2\.0/);
  assert.match(md, /AUDITBRAIN ORQUESTA · IA ASISTE · PYTHON CALCULA · AUDITOR APRUEBA/);
});
