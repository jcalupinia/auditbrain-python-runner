import { buildHandoffContext, getModeMessage, resolveExecutionModes, serializeHandoff } from "./handoff.mjs";

const availability = window.AUDITBRAIN_AI_AVAILABILITY || { chatgpt: true, work: false, codex: false, astra: false };
const input = window.AUDITBRAIN_HANDOFF_INPUT || {
  project: "AuditBrain",
  tool: { id: "PENDIENTE", name: "Herramienta activa", version: "PENDIENTE" },
  methodologyVersion: "1.2.0",
  framework: { type: "PENDIENTE", edition: "PENDIENTE", status: "PENDIENTE" },
  state: "CONTEXT_READY",
  requestedChange: "Continuar trabajo en ChatGPT",
  repository: { verified: false },
  sourceRefs: [],
  constraints: ["No usar Work, Codex o Astra como requisito del flujo ChatGPT."],
};
const modes = resolveExecutionModes(availability);
const grid = document.querySelector("#mode-grid");
for (const m of modes) {
  const el = document.createElement("article");
  el.className = `mode${m.recommended ? " recommended" : ""}`;
  el.innerHTML = `<div class="status ${m.available ? "" : "off"}">${m.available ? "Disponible" : "Opcional no disponible"}</div><h2>${m.label} ${m.recommended ? '<span class="badge">RECOMENDADO</span>' : ""}</h2><p>${getModeMessage(m)}</p>`;
  grid.appendChild(el);
}
const ctx = buildHandoffContext(input);
const text = serializeHandoff(ctx);
document.querySelector("#context-preview").value = text;

async function copyContext() {
  try {
    await navigator.clipboard.writeText(text);
    document.querySelector("#handoff-status").textContent = "Contexto copiado. Abra ChatGPT normal y péguelo en la conversación.";
  } catch {
    document.querySelector("#context-preview").focus();
    document.querySelector("#context-preview").select();
    document.querySelector("#handoff-status").textContent = "No se pudo copiar automáticamente. El contexto quedó seleccionado para copiar manualmente.";
  }
}
function downloadContext() {
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "auditbrain-chatgpt-context.md"; a.click();
  URL.revokeObjectURL(url);
  document.querySelector("#handoff-status").textContent = "Contexto exportado. AuditBrain permanece disponible aunque un modo opcional no tenga cupo.";
}
document.querySelector("#copy-context").addEventListener("click", copyContext);
document.querySelector("#download-context").addEventListener("click", downloadContext);
