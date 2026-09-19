# AuditBrain · ChatGPT-default Site patch

Release candidate aligned with **Manual/Memory v1.2.0**.

The patch makes ChatGPT the default collaboration route and models Work, Codex and Astra as optional modes. It exports a portable Markdown handoff when direct Site→Chat transfer is not verified.

## Verify

```bash
node --test tests/*.test.mjs
```

## Important

This folder is a deployable/integrable patch candidate. Its presence in GitHub or a ZIP is not proof that the current ChatGPT Site has been published with the change.
