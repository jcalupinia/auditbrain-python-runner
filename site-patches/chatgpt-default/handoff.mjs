const PENDING = "PENDIENTE";

export function resolveExecutionModes(availability = {}) {
  const normalChat = availability.chatgpt !== false;
  return [
    { id: "chatgpt", label: "ChatGPT", recommended: true, available: normalChat, optional: false },
    { id: "work", label: "Work", recommended: false, available: availability.work === true, optional: true },
    { id: "codex", label: "Codex", recommended: false, available: availability.codex === true, optional: true },
    { id: "astra", label: "Astra", recommended: false, available: availability.astra === true, optional: true },
  ];
}

export function getModeMessage(mode) {
  if (mode.id === "chatgpt") {
    return mode.available
      ? "Trabajar en una conversación normal con el contexto de AuditBrain. No requiere iniciar una tarea Work o Codex."
      : "ChatGPT normal no está disponible en este momento según el estado informado por la plataforma.";
  }
  return mode.available
    ? `${mode.label} disponible como modo opcional.`
    : `${mode.label} no disponible. Puede continuar en ChatGPT.`;
}

export function buildHandoffContext(input = {}) {
  const safeRefs = Array.isArray(input.sourceRefs)
    ? input.sourceRefs.map((x) => ({ name: x?.name || PENDING, ref: x?.ref || PENDING, status: x?.status || PENDING }))
    : [];
  return {
    schema: "auditbrain-handoff/1.0",
    project: input.project || "AuditBrain",
    tool: {
      id: input.tool?.id || PENDING,
      name: input.tool?.name || PENDING,
      version: input.tool?.version || PENDING,
    },
    methodologyVersion: input.methodologyVersion || "1.2.0",
    framework: {
      type: input.framework?.type || PENDING,
      edition: input.framework?.edition || PENDING,
      status: input.framework?.status || PENDING,
    },
    state: input.state || "CONTEXT_READY",
    requestedChange: input.requestedChange || PENDING,
    repository: input.repository?.verified === true
      ? { verified: true, fullName: input.repository.fullName || PENDING, ref: input.repository.ref || PENDING }
      : { verified: false, fullName: PENDING, ref: PENDING },
    sourceRefs: safeRefs,
    constraints: Array.isArray(input.constraints) ? [...input.constraints] : [],
    privacy: {
      embedsClientEvidence: false,
      note: "El paquete contiene contexto y referencias mínimas; la evidencia del cliente no se incrusta por defecto.",
    },
  };
}

export function serializeHandoff(ctx) {
  const lines = [
    "# AuditBrain · contexto portable para ChatGPT",
    "",
    `- Proyecto: ${ctx.project}`,
    `- Herramienta: ${ctx.tool.name} (${ctx.tool.id})`,
    `- Versión de herramienta: ${ctx.tool.version}`,
    `- Memoria metodológica: v${ctx.methodologyVersion}`,
    `- Marco: ${ctx.framework.type}`,
    `- Edición: ${ctx.framework.edition}`,
    `- Estado: ${ctx.state}`,
    `- Cambio solicitado: ${ctx.requestedChange}`,
    `- Repositorio verificado: ${ctx.repository.verified ? "Sí" : "No"}`,
  ];
  if (ctx.repository.verified) lines.push(`- Repositorio: ${ctx.repository.fullName}@${ctx.repository.ref}`);
  if (ctx.sourceRefs.length) {
    lines.push("", "## Fuentes/referencias disponibles");
    for (const s of ctx.sourceRefs) lines.push(`- ${s.name} · ${s.status} · ${s.ref}`);
  }
  if (ctx.constraints.length) {
    lines.push("", "## Restricciones");
    for (const c of ctx.constraints) lines.push(`- ${c}`);
  }
  lines.push("", "## Regla operativa", "AUDITBRAIN ORQUESTA · IA ASISTE · PYTHON CALCULA · AUDITOR APRUEBA");
  return lines.join("\n");
}
