# AuditBrain e2e / visual QA

Playwright harness for the React/Vite frontend. The backend is stubbed
via `page.route` (see `tests/helpers.js`), so the suite is deterministic
and runs offline. Browser-side problems (console errors, `pageerror`,
CORS/blocked requests) are captured automatically by `tests/fixtures.js`
and attached to the HTML report.

## Run locally

```bash
cd e2e
npm install
npx playwright install chromium      # needs network to cdn.playwright.dev
npx playwright test                  # functional + visual, all viewports
```

Artifacts: `playwright-report/`, `test-results/` (videos, traces),
`screenshots/actual/`. Visual baselines live in
`screenshots/baseline/<project>/` and are committed.

## CI

`.github/workflows/e2e-playwright.yml` runs on `pull_request` and
`workflow_dispatch`. Functional tests are blocking; on the first run it
seeds visual baselines (non-blocking) and uploads them as the
`playwright-visual-baseline` artifact — download and commit
`screenshots/baseline/` to enable strict visual-regression diffing.

## Optional: smoke against the live Render deployment

This is **outside the main CI gate** — it is never run on `pull_request`
and must be triggered manually, since it depends on the real deployed
site and a network policy that allows `*.onrender.com`.

The default specs assume the mocked backend, so the Render smoke is a
**read-only, unauthenticated** check: load the deployed frontend, assert
the login screen renders, and surface any console/`pageerror`/CORS
issues. Run it manually with an inline spec, without modifying the CI
config:

```bash
cd e2e
# Requires: Chromium installed + network allowlist for *.onrender.com
BASE="https://auditbrain-frontend.onrender.com"
npx playwright test --config=- <<'EOF'
import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: ".",
  use: { baseURL: process.env.SMOKE_URL, screenshot: "on", trace: "on" },
});
EOF
```

…pointing at a one-off spec that loads `/` and checks
`form.login-card` is visible. Keep it **manual / `workflow_dispatch`
only** so it can never gate a PR or reach production. Do **not** point
authenticated flows at production with real credentials.

## Constraints

This directory is fully isolated: it does not touch the backend,
endpoints, functional frontend code, or `render.yaml`.
