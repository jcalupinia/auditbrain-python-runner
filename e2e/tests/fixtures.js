import { test as base, expect } from "@playwright/test";

/**
 * Extends the base test so every spec that imports `test` from here
 * automatically captures browser-side problems:
 *   - console.error messages
 *   - uncaught page errors (pageerror)
 *   - CORS / blocked-request failures
 *
 * Capture is non-fatal by design (it must not flake CI on benign logs):
 * findings are attached to the HTML report — which CI uploads as an
 * artifact — and printed to the run log. Use `expectNoBrowserErrors`
 * explicitly in a spec when you want a hard assertion.
 */
const CORS_RE =
  /CORS|Cross-Origin|Access-Control-Allow-Origin|blocked by CORS|has been blocked by/i;

export const test = base.extend({
  browserErrors: [
    async ({ page }, use, testInfo) => {
      const consoleErrors = [];
      const pageErrors = [];
      const corsErrors = [];

      page.on("console", (msg) => {
        if (msg.type() !== "error") return;
        const text = msg.text();
        consoleErrors.push(text);
        if (CORS_RE.test(text)) corsErrors.push(text);
      });
      page.on("pageerror", (err) => {
        pageErrors.push(err && err.stack ? err.stack : String(err));
      });
      page.on("requestfailed", (req) => {
        const failure = req.failure();
        const reason = failure ? failure.errorText : "";
        if (/cors|access control|blocked/i.test(reason)) {
          corsErrors.push(`${req.method()} ${req.url()} :: ${reason}`);
        }
      });

      const collected = { consoleErrors, pageErrors, corsErrors };
      await use(collected);

      const total =
        consoleErrors.length + pageErrors.length + corsErrors.length;
      if (total > 0) {
        await testInfo.attach("browser-errors.json", {
          body: JSON.stringify(collected, null, 2),
          contentType: "application/json",
        });
        // eslint-disable-next-line no-console
        console.log(
          `[browser-errors] ${testInfo.title}: ` +
            `${consoleErrors.length} console, ${pageErrors.length} pageerror, ` +
            `${corsErrors.length} CORS`
        );
      }
    },
    { auto: true },
  ],
});

/**
 * Opt-in hard assertion: fail the test if any console error, page error
 * or CORS failure was observed.
 */
export function expectNoBrowserErrors(browserErrors) {
  expect(
    browserErrors.consoleErrors,
    `console errors: ${JSON.stringify(browserErrors.consoleErrors)}`
  ).toEqual([]);
  expect(
    browserErrors.pageErrors,
    `page errors: ${JSON.stringify(browserErrors.pageErrors)}`
  ).toEqual([]);
  expect(
    browserErrors.corsErrors,
    `CORS errors: ${JSON.stringify(browserErrors.corsErrors)}`
  ).toEqual([]);
}

export { expect };
