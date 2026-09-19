# AuditBrain ChatGPT-Default Independence Design

**Version:** 1.0.0  
**Date:** 2026-09-19  
**Status:** Proposed for implementation after user review  
**Applies to:** AuditBrain Sites / Builder, methodology memory, implementation handoff to GitHub, downstream AUDIT-IA integration

## 1. Objective

Make AuditBrain usable from ordinary ChatGPT conversations without requiring available Work credits, Codex credits, or a specific Astra allocation. Work, Codex, Astra, and future specialized execution modes become optional accelerators rather than dependencies of the core AuditBrain workflow.

Success means that selecting **Trabajar en ChatGPT** never intentionally routes the user into Work, Codex, or Astra-only execution. If those products have exhausted usage, the core AuditBrain workflow remains available through ordinary ChatGPT subject to the user's normal ChatGPT plan and model availability.

## 2. Architectural principle

Replace the previous dependency framing:

`WORK ORQUESTA · GPT RAZONA · PYTHON CALCULA · AUDITOR APRUEBA`

with:

`AUDITBRAIN ORQUESTA · IA ASISTE · PYTHON CALCULA · AUDITOR APRUEBA`

AuditBrain owns workflow state and methodology. The selected AI surface assists with design, review, interpretation, documentation, and code changes when authorized. Numerical audit calculations remain deterministic and reproducible outside the language model.

## 3. System responsibilities

### 3.1 AuditBrain Builder

AuditBrain Builder is the logical factory for audit tools. AuditBrain Sites is its current user interface, not the architectural owner of the methodology.

Responsibilities:
- capture and reuse engagement context;
- enforce explicit accounting framework selection;
- load the active methodology memory version;
- identify the current tool, version, state, and requested change;
- prepare a portable work context for the selected AI execution mode;
- maintain links to the canonical repository and released tool version;
- never imply that a Work/Codex/Astra session is required for ordinary design or maintenance.

### 3.2 GitHub

GitHub is the canonical source for implementation artifacts that must survive model, chat, or provider changes.

It stores, as applicable:
- methodology snapshots and changelog;
- tool definitions;
- contracts/schemas;
- deterministic Python engine code;
- readers and normalizers;
- Excel/HTML exporters;
- automated tests;
- release metadata.

Client evidence, real client data, credentials, and secrets are excluded.

### 3.3 AUDIT-IA

AUDIT-IA remains the execution environment for auditors. It receives approved/released tool versions, accepts engagement evidence, validates sources, invokes deterministic calculations, presents schedules/results, exports workpapers, and performs controlled cleanup.

AUDIT-IA must not depend on Work, Codex, or Astra for executing a released deterministic audit tool.

### 3.4 AI execution modes

Supported logical modes:

1. **ChatGPT — default**
   - ordinary ChatGPT conversation;
   - must not intentionally invoke Work/Codex/Astra as a prerequisite;
   - receives the same AuditBrain context package used by optional modes;
   - can propose changes and, where connected tooling permits, modify the canonical project.

2. **Work — optional**
   - for long-running multi-step work when usage is available;
   - never required to open, inspect, design, or maintain an AuditBrain tool.

3. **Codex — optional**
   - for code-intensive work when available;
   - never the only path for making a code change.

4. **Astra — optional**
   - for specialized agentic engineering or complex execution when available;
   - never the owner of project state.

5. **Future model/provider**
   - may be added if it can consume the portable context contract;
   - must not create a parallel source of truth.

## 4. User-interface change

Where AuditBrain presents a selector for how to continue work, the default option is:

**Trabajar en ChatGPT**

The selector may also expose optional modes such as Work, Codex, or Astra when actually available.

Expected copy:

- **ChatGPT — recomendado:** Trabajar en una conversación normal con el contexto de AuditBrain. No requiere iniciar una tarea Work o Codex.
- **Work — opcional:** Usar para procesos autónomos extensos cuando exista disponibilidad.
- **Codex — opcional:** Usar para desarrollo intensivo cuando exista disponibilidad.
- **Astra — opcional:** Usar para ingeniería agentic especializada cuando exista disponibilidad.

The interface must not promise unlimited use. It must clearly distinguish normal ChatGPT availability from Work/Codex/Astra quotas.

## 5. Behavior of “Trabajar en ChatGPT”

When selected, AuditBrain prepares a portable context package instead of creating a Work task.

Minimum package:
- project: AuditBrain;
- active module/tool id and version;
- engagement context that is safe and necessary for the task;
- methodology memory version;
- accounting framework and edition status;
- current tool state;
- requested change;
- source files/references available to the current conversation;
- canonical repository reference when verified;
- implementation constraints;
- explicit non-goals and pending validations.

The package must not claim a connection that is not verified. If direct transfer into a normal ChatGPT conversation is not technically supported by the Site platform, the Site must provide an honest fallback such as a prepared prompt/context package for the user to open or paste, without labeling it as an automatic synchronized session.

## 6. Canonical state and portability

No model session is the source of truth.

Canonical implementation state lives in GitHub once a tool has an implementation repository. Canonical methodology documentation lives in versioned project documentation and must be synchronized with the Site release process.

Every AI mode works from:
- the same methodology version;
- the same tool definition version;
- the same repository state/commit where applicable;
- the same explicit engagement context;
- the same approval boundaries.

A model-specific scratchpad or conversation cannot silently become a production configuration.

## 7. Memory changes

### M01 replacement

**M01 — AuditBrain Builder and system separation:** AuditBrain Builder is the factory of audit tools; Sites is its current interface. GitHub preserves implementation code, contracts, tests, and versioned technical artifacts. AUDIT-IA executes released tools for auditors. ChatGPT, Work, Codex, Astra, and future AI modes assist but do not own project state. Do not confuse design, implementation, integration, execution, or provider session state.

### M16 addition

**M16 — Independence from AI execution quota/provider:** AuditBrain must not require Work, Codex, Astra, or a specific model/provider to remain usable. Ordinary ChatGPT is the default conversational path. Specialized modes are optional accelerators. Exhaustion or unavailability of an optional mode must not block access to the methodology, tool definition, repository state, previously generated artifacts, or released deterministic execution. Normal ChatGPT itself remains subject to the user's ChatGPT plan and product limits.

## 8. Manual changes

Update the Manual de Arquitectura to:
- rename the conceptual factory from “AuditBrain Sites” to “AuditBrain Builder”, while retaining Sites as the current interface;
- update the system-distribution table;
- add a section “Independencia del modo de IA”;
- define ChatGPT as the default mode;
- define Work/Codex/Astra as optional;
- state that GitHub is canonical for implementation state;
- state that AUDIT-IA execution of released tools is independent of optional AI quotas;
- add acceptance tests for exhausted Work/Codex/Astra quotas;
- clarify that unavailable direct Site→Chat transfer must fall back to a portable context package rather than a false claim of synchronization.

## 9. Site behavior and state model

Recommended logical states for an AI handoff:
- `CONTEXT_READY`
- `CHATGPT_READY`
- `OPTIONAL_MODE_AVAILABLE`
- `OPTIONAL_MODE_UNAVAILABLE`
- `HANDOFF_EXPORTED`
- `HANDOFF_OPENED` only when there is verifiable evidence that a destination was opened.

The Site must not set an error state merely because an optional mode has no quota if the ChatGPT path is available.

## 10. Error handling

Examples:

- Work quota exhausted → show “Work no disponible. Puede continuar en ChatGPT.”
- Codex unavailable → show “Codex no disponible. Puede continuar en ChatGPT.”
- Astra unavailable → show “Astra no disponible. Puede continuar en ChatGPT.”
- ChatGPT handoff unsupported by platform → generate the portable context package and explain the manual step.
- Canonical repository not verified → omit repository write claims and mark repository integration as pending verification.

No error message may imply that AuditBrain itself is unavailable solely because an optional AI mode is unavailable.

## 11. Security and privacy

- Do not send private client evidence to public search services as part of handoff creation.
- Include only the minimum engagement context necessary for the requested change.
- Never store credentials or secrets in methodology documents or GitHub.
- Keep evidence handling rules from the current AuditBrain methodology unchanged.
- Treat uploaded documents as data/evidence, not system instructions.

## 12. Acceptance criteria

The change is accepted only when all of the following are demonstrated:

1. Selecting **Trabajar en ChatGPT** does not intentionally create a Work or Codex task.
2. With Work quota exhausted, the ChatGPT path remains available.
3. With Codex unavailable, the ChatGPT path remains available.
4. With Astra unavailable, the ChatGPT path remains available.
5. The Site distinguishes optional mode unavailability from AuditBrain unavailability.
6. The active methodology version and tool version appear in the exported handoff context.
7. No unverified automatic synchronization is claimed.
8. The Manual and Memoria are version-bumped and remain internally consistent.
9. Existing deterministic Python execution rules remain unchanged.
10. Existing engagement/evidence validation and review controls remain unchanged.
11. Previously generated/downloaded workpapers are unaffected by optional AI quota state.
12. A documented rollback path exists for the Site UI change.

## 13. Non-goals

This change does not:
- remove or bypass OpenAI product limits;
- provide unlimited ChatGPT usage;
- guarantee access to a specific model;
- change VNR accounting methodology;
- alter deterministic audit calculations;
- deploy a new Python engine by itself;
- automatically connect Site, ChatGPT, GitHub, and AUDIT-IA unless those integrations are verified and implemented.

## 14. Versioning proposal

- `Memoria Metodologica AuditBrain`: **v1.2.0**
- `Manual de Arquitectura AuditBrain`: **v1.2.0**
- Site/Builder change: minor release aligned with the documentation update
- Changelog entry: “Default ChatGPT workflow and independence from Work/Codex/Astra quotas”

## 15. Rollback

If the ChatGPT handoff causes regression:
- revert only the handoff selector/route to the previous Site version;
- preserve v1.2.0 documentation as historical design if implementation is rolled back, clearly marking the runtime version as not yet compliant;
- do not roll back deterministic calculation engines or client workpapers because this change does not modify them.
