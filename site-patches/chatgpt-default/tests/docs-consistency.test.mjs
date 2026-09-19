import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
const root = new URL("../../../docs/auditbrain/", import.meta.url);
test("manual and memory are v1.2.0 and quota-independent", async () => {
  const manual = await readFile(new URL("Manual_Arquitectura_AuditBrain.md", root), "utf8");
  const memory = await readFile(new URL("Memoria_Metodologica_AuditBrain.md", root), "utf8");
  assert.match(manual, /Versión 1\.2\.0/);
  assert.match(manual, /Independencia del modo de IA/);
  assert.match(memory, /v1\.2\.0/);
  assert.match(memory, /M01 — AuditBrain Builder/);
  assert.match(memory, /M16 — Independencia del modo y cupo de IA/);
});
