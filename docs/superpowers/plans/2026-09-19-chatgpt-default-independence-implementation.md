# ChatGPT Default Independence v1.2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ordinary ChatGPT the default AuditBrain collaboration path, keep Work/Codex/Astra optional, version the methodology to v1.2.0, and provide a tested Site handoff module that never treats optional quota exhaustion as AuditBrain failure.

**Architecture:** AuditBrain Builder owns workflow context; Sites is the interface; GitHub is canonical for implementation artifacts; AUDIT-IA executes released deterministic tools. The Site prepares a portable handoff package for ChatGPT. Optional execution modes are capability flags, never hard dependencies.

**Tech Stack:** Markdown documentation, vanilla ES modules for the Site patch, Node built-in test runner for portable tests; existing React/Vite/Vitest integration can consume the same pure handoff functions.

**Spec:** `docs/superpowers/specs/2026-09-19-chatgpt-default-independence-design.md`

## Global Constraints

- Ordinary ChatGPT is the default conversational path.
- Work, Codex and Astra are optional accelerators and may be unavailable without blocking AuditBrain.
- Do not claim unlimited ChatGPT use or bypass any OpenAI plan/product limits.
- Do not claim automatic Site→Chat synchronization unless a verified platform action exists.
- GitHub is canonical for code/contracts/tests; no client evidence or secrets are stored there.
- Python remains authoritative for deterministic numerical calculations.
- Existing VNR/accounting methodology is unchanged by this feature.
- Site fallback must export a portable context package when a direct normal-Chat handoff is unavailable.

## Review Focus

- Work quota exhausted: ChatGPT remains selectable and no global error is raised.
- Codex/Astra unavailable simultaneously: exported handoff is unchanged and valid.
- Missing direct ChatGPT deep-link integration: UI truthfully switches to copy/download fallback.
- Sensitive evidence: handoff exports references/metadata, not embedded client evidence by default.
- Missing framework/tool version: context package marks the field pending rather than inventing it.

---

### Task 1: Version methodology documents to v1.2.0

**Files:**
- Create: `docs/auditbrain/Manual_Arquitectura_AuditBrain.md`
- Create: `docs/auditbrain/Memoria_Metodologica_AuditBrain.md`
- Create: `docs/auditbrain/CHANGELOG.md`

**Interfaces:**
- Consumes: approved independence spec.
- Produces: canonical methodology v1.2.0 used by handoff context.

- [ ] **Step 1: Write document consistency test**

Create `site-patches/chatgpt-default/tests/docs-consistency.test.mjs` asserting both docs report v1.2.0, M01 says AuditBrain Builder, M16 exists, and the manual contains “Independencia del modo de IA”.

- [ ] **Step 2: Run test and verify RED**

Run: `node --test site-patches/chatgpt-default/tests/docs-consistency.test.mjs`
Expected: FAIL because v1.2.0 files do not yet exist.

- [ ] **Step 3: Create the v1.2.0 documents and changelog**

Preserve v1.1.0 methodology, replace M01, add M16, add the AI-mode architecture section, explicit fallback behavior, quota acceptance cases, and version history.

- [ ] **Step 4: Run test and verify GREEN**

Run: `node --test site-patches/chatgpt-default/tests/docs-consistency.test.mjs`
Expected: PASS.

### Task 2: Implement portable ChatGPT handoff domain logic

**Files:**
- Create: `site-patches/chatgpt-default/handoff.mjs`
- Create: `site-patches/chatgpt-default/tests/handoff.test.mjs`

**Interfaces:**
- Consumes: `{project, tool, methodologyVersion, framework, state, requestedChange, repository, sourceRefs, constraints, availability}`.
- Produces: `buildHandoffContext()`, `resolveExecutionModes()`, `getModeMessage()`, and `serializeHandoff()`.

- [ ] **Step 1: Write failing behavior tests**

Tests cover ChatGPT default, Work/Codex/Astra unavailable, missing repository, pending framework, and no embedded evidence payload.

- [ ] **Step 2: Run test and verify RED**

Run: `node --test site-patches/chatgpt-default/tests/handoff.test.mjs`
Expected: FAIL because `handoff.mjs` does not exist.

- [ ] **Step 3: Implement minimal deterministic handoff functions**

`resolveExecutionModes()` always keeps ChatGPT enabled unless caller explicitly marks normal Chat unavailable; optional modes reflect availability. `buildHandoffContext()` includes safe metadata only and uses `"PENDIENTE"` for unknown required context. `serializeHandoff()` returns readable Markdown for copy/download.

- [ ] **Step 4: Run test and verify GREEN**

Run: `node --test site-patches/chatgpt-default/tests/handoff.test.mjs`
Expected: PASS.

### Task 3: Implement Site selector and fallback UI

**Files:**
- Create: `site-patches/chatgpt-default/index.html`
- Create: `site-patches/chatgpt-default/styles.css`
- Create: `site-patches/chatgpt-default/app.mjs`
- Create: `site-patches/chatgpt-default/tests/ui-contract.test.mjs`

**Interfaces:**
- Consumes: handoff functions from Task 2.
- Produces: a Site-compatible UI patch with `Trabajar en ChatGPT` default and optional Work/Codex/Astra cards.

- [ ] **Step 1: Write failing UI-contract test**

Assert HTML contains the default ChatGPT action, optional-mode labels, copy/download fallback, and no copy that claims unlimited access or automatic synchronization.

- [ ] **Step 2: Run test and verify RED**

Run: `node --test site-patches/chatgpt-default/tests/ui-contract.test.mjs`
Expected: FAIL because UI files do not exist.

- [ ] **Step 3: Implement minimal UI**

Default action generates context and copies/downloads it. Optional unavailable modes display “Puede continuar en ChatGPT.” No optional failure disables the default action.

- [ ] **Step 4: Run test and verify GREEN**

Run: `node --test site-patches/chatgpt-default/tests/ui-contract.test.mjs`
Expected: PASS.

### Task 4: Add integration/rollback instructions for the live AuditBrain Site

**Files:**
- Create: `site-patches/chatgpt-default/INTEGRATION.md`
- Create: `site-patches/chatgpt-default/site-change-manifest.json`

**Interfaces:**
- Consumes: current Site project id `appgprj_6aac4365f6288191a6d65fea99a71373` and live slug `auditbrain-auditoria` when still current.
- Produces: exact merge contract for the current Site and a rollback boundary.

- [ ] **Step 1: Write failing manifest test**

Extend `ui-contract.test.mjs` to assert manifest names the Site project, sets ChatGPT default, lists Work/Codex/Astra optional, and declares `direct_chat_handoff_verified=false` until a platform action is actually verified.

- [ ] **Step 2: Run test and verify RED**

Run: `node --test site-patches/chatgpt-default/tests/ui-contract.test.mjs`
Expected: FAIL because manifest does not exist.

- [ ] **Step 3: Implement integration docs and manifest**

Document insertion point, state mapping, fallback, rollback and non-goals. Never describe the patch bundle itself as already published.

- [ ] **Step 4: Run test and verify GREEN**

Run: `node --test site-patches/chatgpt-default/tests/ui-contract.test.mjs`
Expected: PASS.

### Task 5: Verification and release package

**Files:**
- Create: `site-patches/chatgpt-default/README.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: independently reviewable patch bundle and deployment checklist.

- [ ] **Step 1: Run complete portable test suite**

Run: `node --test site-patches/chatgpt-default/tests/*.test.mjs`
Expected: all tests PASS.

- [ ] **Step 2: Validate forbidden claims**

Run a text scan for `ilimitado`, `sin limites`, `sin límites`, `sincronizado automaticamente`, and `sincronizado automáticamente`; expected: no misleading product claims.

- [ ] **Step 3: Package release candidate**

Create a ZIP containing spec, plan, v1.2.0 docs and Site patch. Record that publishing the existing ChatGPT Site requires a Site-write capability; the package is not itself proof of publication.