# Storefront Task 2 Report — Production Customer Domain Frontend

## Status

`DONE_WITH_CONCERNS`

The frontend implementation and its automated verification are complete within Task 2's assigned scope. Production integration is not yet signed off because the backend lifecycle contracts are being landed by sibling tasks and visible browser E2E evidence belongs to Task 5.

## Anti-drift check

The implementation stayed on the requested production storefront/custom-domain customer journey. It did not change Python, environment configuration, deployment configuration, dependency manifests, documentation guides, testbed lifecycle files, or commits. It preserved the existing storefront design/media save work while replacing the oversimplified domain textbox with a provider-aware, resumable setup flow.

## Acceptance matrix

| Requirement | Frontend evidence | Result |
| --- | --- | --- |
| Storefront IA is readable and bounded | Exactly three ARIA tabs: `Design`, `Content & publish`, and `Domain`; Live preview is a persistent header action; mobile full-screen shell; desktop `max-w-5xl`; Domain content is a single `max-w-[760px]` column | PASS |
| Platform preview is independent of custom-domain state | Header Live preview and saved-preview controls use the internal platform slug URL | PASS |
| Customer declares intent before mutation | Domain plus `new`, `existing`, or `migration` intent is preflighted before claim | PASS |
| Provider/registrar/network roles are clear | Separate provider detection, registrar guidance, storefront-network target, provider link, and customer-safe errors | PASS |
| Automatic setup is truthful | `Connect automatically with {provider}` appears only when the backend returns exact Domain Connect support; frontend calls `/domain-connect/authorize` | PASS |
| Manual setup is always available | Exact record cards show purpose, type, relative host, FQDN, value, TTL, proxy instruction, observed value, Copy, Copy all, and provider link | PASS |
| Verification is not a false positive | Ownership, DNS routing, provider hostname, SSL certificate, and secure storefront are independent checks; Check again is read-only while Retry is a separate mutation | PASS |
| Redirect flow is resumable | Safe attempt IDs are restored from query state; completion POSTs once to `/domain-connect/complete`, then refreshes canonical status; unrelated query parameters are preserved | PASS |
| DNS work can be delegated | Validated email and optional note call the DNS-instructions endpoint and announce success through a polite live region | PASS |
| Existing domains remain manageable | `can_manage_existing_domain` is independent of new-domain activation; existing status/disconnect remain available when new activation is unavailable | PASS |
| Disconnect is safe and accessible | No native confirm; nested modal traps focus, supports Escape and restoration, states that platform URL/publication remain unchanged, and shows cleanup records | PASS |
| Readability/accessibility | Explicit light/dark foregrounds, 16 px inputs, no 10–13 px copy in touched storefront components, minimum 44 px controls, semantic tab relationships, arrow/Home/End tab navigation, modal focus traps | PASS (automated contract; visible browser proof still required) |

## Files changed by Task 2

- `app/admin/components/storefront/CustomDomainManager.tsx`
- `app/admin/packages/StorefrontSettingsModal.tsx`
- `app/admin/packages/page.tsx`
- `app/admin/packages/storefrontRouteState.ts`
- `app/components/storefront/StorefrontImagePicker.tsx`
- `app/services/storefrontApi.ts`
- `tests/unit/storefrontAdminContract.test.ts`
- `tests/unit/storefrontApi.test.ts`
- `tests/unit/storefrontConsumerCompatibility.test.ts`
- `tests/unit/storefrontDomainJourney.test.tsx`
- `.superpowers/sdd/storefront-task-2-report.md`

The worktree contains concurrent changes from other tasks. Task 2 did not author or alter the testbed lifecycle specification.

## TDD evidence

### RED

Initial corrected focused run before the UI implementation:

```text
43 tests; 27 passed; 16 failed
```

Late contract correction for the production Domain Connect route was also driven red first:

```text
PATH=/opt/homebrew/opt/node@22/bin:/opt/homebrew/bin:/usr/bin:/bin \
  ./node_modules/.bin/tsx --test tests/unit/storefrontApi.test.ts

14 tests; 13 passed; 1 failed
Expected: /admin/storefront/custom-domain/domain-connect/authorize
Actual:   /admin/storefront/custom-domain/domain-connect/start
```

The implementation was then changed to the canonical `/authorize` route. `/start` is not used by this frontend.

### GREEN — focused storefront contracts

```text
PATH=/opt/homebrew/opt/node@22/bin:/opt/homebrew/bin:/usr/bin:/bin \
  ./node_modules/.bin/tsx --test \
  tests/unit/storefrontConsumerCompatibility.test.ts \
  tests/unit/storefrontDomainJourney.test.tsx \
  tests/unit/storefrontApi.test.ts \
  tests/unit/storefrontAdminContract.test.ts

47 tests; 47 passed; 0 failed; 5 suites
```

### GREEN — type check

```text
PATH=/opt/homebrew/opt/node@22/bin:/opt/homebrew/bin:/usr/bin:/bin npm run type-check

Exit 0; dependency preflight passed; TypeScript emitted no errors
```

The repository warns that Node 22 satisfies `package.json` engines but is formally validated only on Node 20 and 24. Node 22 was used because it was the requested verification runtime.

### GREEN — full frontend regression suite

```text
PATH=/opt/homebrew/opt/node@22/bin:/opt/homebrew/bin:/usr/bin:/bin npm test

499 tests; 499 passed; 0 failed; 91 suites
```

An earlier full run exposed one stale source-contract expectation (`498/499`). That compatibility assertion was updated to require the new preflight/claim lifecycle, then the complete suite passed.

### Diff hygiene

```text
git diff --check -- <Task 2 files>

Exit 0
```

## Hostile review outcomes

- Rejected a four-tab layout: Live preview is now an action/region, leaving exactly three configuration tabs.
- Removed the single textbox/Connect fiction and modeled preflight, claim, auto/manual configuration, verification, SSL, active, failure, and disconnect states.
- Corrected automatic authorization from the legacy `/start` route to the production `/authorize` contract.
- Kept manual setup available even when automatic provider setup is supported.
- Added exact DNS record evidence and separate verification checks so `active` cannot be implied by only one DNS observation.
- Added resumable callback completion and guarded attempt parsing instead of assuming a redirect always returns to an intact modal.
- Added DNS-instruction delegation for customers who do not control their DNS account.
- Split permission to activate a new domain from permission to manage an already connected domain.
- Replaced native confirmation with a keyboard-accessible disconnect dialog and truthful preservation/cleanup copy.
- Reordered focusable controls so the main modal focus loop has a deterministic first element; this also eliminated an assertion/OOM failure caused by comparing different portal nodes.

## Remaining concerns / required downstream proof

1. Do not call the production feature complete until sibling backend routes return the exact mapped lifecycle payloads and the frontend-to-backend integration passes.
2. Task 5 must execute the real frontend browser flow and retain screenshots/evidence for desktop and mobile states. Unit, type, and full scripted tests do not replace visible browser validation.
3. Automatic setup must remain hidden unless the backend has positive provider-specific Domain Connect evidence. Unknown providers must continue through manual setup.
4. Provider authorization, DNS propagation, SSL issuance, migration conflict, retry, and disconnect cleanup need live lifecycle proof against the configured production-like infrastructure.
5. No commit was created by Task 2.
