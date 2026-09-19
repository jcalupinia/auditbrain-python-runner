import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
const root = new URL("../", import.meta.url);
test("site patch exposes ChatGPT default and truthful fallback", async () => {
  const html = await readFile(new URL("index.html", root), "utf8");
  assert.match(html, /Trabajar en ChatGPT/);
  assert.match(html, /Work, Codex y Astra son opcionales/);
  assert.match(html, /Descargar contexto/);
  assert.doesNotMatch(html.toLowerCase(), /uso ilimitado|sin límites|sin limites|sincronizado automáticamente|sincronizado automaticamente/);
});

test("manifest keeps optional modes from blocking AuditBrain", async () => {
  const manifest = JSON.parse(await readFile(new URL("site-change-manifest.json", root), "utf8"));
  assert.equal(manifest.project_id, "appgprj_6aac4365f6288191a6d65fea99a71373");
  assert.equal(manifest.default_mode, "chatgpt");
  assert.deepEqual(manifest.optional_modes, ["work","codex","astra"]);
  assert.equal(manifest.direct_chat_handoff_verified, false);
  assert.equal(manifest.invariant, "optional_mode_unavailable_does_not_block_auditbrain");
});
