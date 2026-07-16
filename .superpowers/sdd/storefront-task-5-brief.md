# Task 5 — Reproducible Playwright storefront testbed and visible acceptance

## Context

Replace the self-attested storefront verifier with real browser automation while
retaining Python only for isolated seeding, post-run database assertions, and
cleanup. Prior browser evidence is invalid and must not be reused.

## Required behavior

1. Generate a unique run ID and embed it in planner, settings, package, review,
   inquiry, and cleanup state. Require it through authenticated backend reads and
   rendered DOM so browser/backend/Mongo identity is proven.
2. Add same-owner negative fixtures: inactive package, template package,
   excluded service, and unpublished review.
3. Add a dedicated storefront Playwright config/spec and `npm run
   test:e2e:storefront`. Consume already-attested loopback production services;
   do not auto-start unrelated global servers.
4. Browser code performs every interaction. Remove user-authored pass booleans
   and handwritten DOM/console evidence from the acceptance path.
5. Retain Playwright JSON/JUnit, trace, screenshots, failure video, DOM/ARIA
   snapshots, console/page errors, failed requests, and response statuses in a
   unique ignored run directory. Manifest binds run ID, git/diff fingerprint,
   frontend build ID, backend revision, ports, provider mode, test results, and
   cleanup result.
6. Run Chromium desktop and 390x844 mobile, light/dark, keyboard, overflow,
   contrast/accessibility checks. Add `@axe-core/playwright` with npm and lockfile
   update if required.
7. Cover the accepted storefront scenario list: gating, modal IA, slug preview,
   draft/publication, package/review positives and negatives, media lifecycle,
   inquiry truth, friendly config error, automatic/manual domain flows,
   cancel/resume, independent checks, active HTTPS, disconnect/retry/cleanup.
8. Provide deterministic loopback fake-provider fixtures for state-machine UI;
   never label them external proof.
9. Real provider mode requires exact account, zone, CNAME target, staging/public
   bucket, hostname, provider ID allowlists; cleanup in `finally`, and survivors
   fail the run.
10. Keep in-app Chrome playback as the final visible UX layer after Playwright.
    Automated and visible evidence remain separate acceptance rows.

## TDD and verification contract

- Write failing contract/browser tests first and record RED.
- Use Node 22 and `.venv.nosync/bin/python`.
- Run deterministic provider-disabled E2E end to end. Run live provider mode only
  when exact prerequisites and permissions pass the doctor; otherwise mark it
  BLOCKED, never PASSED.
- Do not commit. Shared dirty checkout.

## Report

Write `.superpowers/sdd/storefront-task-5-report.md`; return status, artifacts,
commands/counts, and blocked external rows.
