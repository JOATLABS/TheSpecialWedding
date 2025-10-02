# ESLint violation audit

## Overview
- **Command executed:** `npx next lint --format json --output-file lint-report.json`
- **Scan date:** 2025-09-30
- **Files with findings:** 41
- **Total violations:** 79 (36 errors, 43 warnings)

All blocking failures come from four React/Next.js rules that surface correctness risks (hooks) and accessibility/performance concerns (escaped entities and `next/image`).

## Violations by rule
| Rule | Count | Severity mix | Notes |
| --- | --- | --- | --- |
| `react-hooks/exhaustive-deps` | 35 | warnings | Missing dependencies inside `useEffect` calls risk stale closures or skipped network fetches. Review each effect and either add the referenced functions/values, memoise them with `useCallback`/`useMemo`, or restructure the logic to avoid unnecessary effects. |
| `react/no-unescaped-entities` | 34 | errors | Apostrophes and quotes in JSX text need HTML entities (e.g. `&apos;`, `&quot;`) or rewording. Leaving them raw breaks HTML validation and Next.js' default escaping guarantees. |
| `@next/next/no-img-element` | 8 | warnings | Replace `<img>` tags in the app directory with Next.js `<Image />` (or explicitly disable optimisation when it is intentional) to restore built-in responsive image optimisation. |
| `react-hooks/rules-of-hooks` | 2 | errors | `useEffect` is invoked conditionally in the guest verification modals. Hooks must be top-level; refactor to early-return JSX instead of branching around hook calls. |

## Most affected modules
| File | Errors | Warnings | Primary issues |
| --- | --- | --- | --- |
| `app/admin/reminders/page.tsx` | 7 | 2 | Unescaped apostrophes/quotes plus missing `useEffect` dependencies. |
| `app/components/landing-page/OurStorySection.tsx` | 2 | 3 | Mixed unescaped entities and `<img>` usage. |
| `app/components/GuestVerificationModal.tsx` | 2 | 2 | Conditional hooks, missing dependencies, and unescaped apostrophes. |
| `app/[slug]/invite/[token]/page.tsx` | 3 | 0 | Unescaped apostrophes in invite copy. |
| `app/admin/budget/quotes/page.tsx` | 2 | 1 | Unescaped apostrophes and missing effect dependencies. |
| `app/admin/guests/page.tsx` | 2 | 1 | Same as above. |
| `app/admin/planner/page.tsx` | 2 | 1 | Same as above. |
| `app/admin/profile/page.tsx` | 2 | 1 | Same as above. |
| `app/admin/weddings/[id]/page.tsx` | 2 | 1 | Same as above. |
| `app/components/GuestVerificationModalOld.tsx` | 1 | 2 | Conditional hooks and missing dependencies. |

(Generate the full list by rerunning `npx next lint --format json --output-file lint-report.json` and grouping by file.)

## Recommended remediation sequence
1. **Stabilise hook ordering.** Refactor the conditional `useEffect` calls in the guest verification modals so hooks execute unconditionally, returning early from the component instead. This removes the highest-severity runtime risk.
2. **Fix stale effect dependencies.** Walk each `useEffect` flagged by `react-hooks/exhaustive-deps` and either:
   - add the referenced functions/values to the dependency array and memoise callbacks with `useCallback`/`useMemo`, or
   - move the logic into event handlers/data loaders where dependencies are explicit.
   Aligning with React's hook rules prevents subtle data desynchronisation bugs.
3. **Escape or rephrase copy.** For each `react/no-unescaped-entities` error, swap the character for an HTML entity (`&apos;`, `&quot;`) or adjust the surrounding copy so the apostrophe/quote is inside curly braces (`{"'"}`) or replaced with synonyms. This keeps server-rendered markup valid.
4. **Adopt `<Image />` wrappers.** Replace the eight `<img>` instances with `next/image` while supplying descriptive `alt` text and layout props. When dynamic sources preclude optimisation, document why the rule is disabled on a per-line basis.
5. **Automate regression checks.** Add the JSON lint report (`npx next lint --format json --output-file lint-report.json`) as part of CI artefacts or integrate with tooling like ESLint's `--max-warnings=0` so future merges surface new violations immediately.

## Next steps
- Pair this audit with targeted PRs that clear the four rule families one by one (starting with hook correctness) and back each change with focused unit/component tests where logic shifts.
- Once the lint baseline is clean, enforce `npm run lint` inside pre-commit or CI pipelines to prevent regressions.
