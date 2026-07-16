# Task 2 — Storefront modal and production domain customer journey

## Context

Implement the accepted storefront information architecture and customer-facing
domain workflow after Task 1's typed backend contracts exist. Preserve the
existing portal, focus trap, preview-save reconciliation, media lifecycle, and
all dirty user work. Reuse the existing brand/design-system tokens and UI
components. Do not add a route or redesign unrelated admin surfaces.

## Required behavior

1. Refactor the storefront dialog into semantic `Design`, `Content & publish`,
   and `Domain` tabs plus the existing live-preview experience. Tabs need
   stable IDs, `aria-controls`, tabpanels, roving tab index, Home/End and arrow
   keys. Domain operations must not share or be disabled by design-save state.
2. Repair the shell:
   - existing `max-w-5xl` product pattern;
   - one bounded scroll region and sticky header;
   - full-screen mobile treatment;
   - explicit light/dark foreground, placeholder, border, error, and status
     colors everywhere;
   - ordinary instructional text at least 14 px and form values at least 16 px
     in the repo's 14 px root context;
   - practical 44 px targets;
   - dialog description, focus/Escape/restoration, no horizontal overflow.
3. Preserve the internal slug as the permanent preview/fallback URL. Preview and
   Save for preview never depend on custom-domain state.
4. Replace the textbox-plus-Connect UI with a transport-injected, testable
   domain panel that renders backend truth only:
   - domain and `new`/`migration` intent;
   - preflight before claim;
   - provider identity distinct from registrar/platform provider;
   - automatic setup only when `domain_connect_supported` is true;
   - manual setup always available;
   - expected records with purpose/type/relative host/FQDN/value/TTL/proxy,
     copy buttons, Copy all, provider link, expected/observed and last check;
   - ownership, routing, provider-hostname, SSL, and HTTPS progress;
   - Check again distinct from Retry verification;
   - active state, unpublished warning, platform URL, and exact cleanup records;
   - assisted migration, conflict, operator review, config unavailable,
     authorization cancelled, pending/failure/retry, and resume states.
5. Replace native `window.confirm` with an accessible disconnect confirmation.
   State explicitly that the slug and publication remain unchanged.
6. Normalize typed and legacy FastAPI/AdminContext failures into friendly
   storefront errors. Never display raw JSON. Include exact customer action and
   support ID when supplied.
7. Copy actions announce completion through a polite live region.
8. Add resumability through `/admin/packages?storefront=domain&attempt=<id>`:
   the packages page opens the modal/domain tab on a valid query and preserves
   unrelated query parameters. Provider callback redirects to that state.
9. Add frontend service functions/types for Task 1 plus later Domain Connect,
   retry, and instruction endpoints. Do not invent provider results client-side.
10. Access behavior:
    - storefront disabled: existing UpgradeModal and no settings request;
    - storefront enabled/domain disabled: design/preview works and Domain shows
      a domain-specific upgrade state;
    - existing-domain manage capability may render status/disconnect even when
      new activation is unavailable.

## TDD and verification contract

- Write rendered/behavioral tests first, run and record expected RED, then
  implement and run GREEN.
- Add focused `storefrontDomainJourney.test.tsx` tests instead of relying only
  on source regexes. Extend `storefrontApi.test.ts` and the existing admin
  contract tests.
- Cover tabs/keyboard/ARIA, explicit colors, responsive classes, provider/manual
  branches, raw-error normalization, each independent check, copy announcement,
  disconnect, resume query, and publication independence.
- Use Node 22. The full repository command is
  `PATH=/opt/homebrew/opt/node@22/bin:/opt/homebrew/bin:/usr/bin:/bin npm test`.
- Run `npm run type-check` for changed TypeScript after focused tests.
- Do not commit. Shared dirty checkout.
- Hostile-review visible copy, layout, error states, access boundaries, and any
  deviation from the accepted plan.

## Report

Write the full report to
`.superpowers/sdd/storefront-task-2-report.md` and return only status, changed
files, red/green commands/counts, and concerns.
