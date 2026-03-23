# TypeScript Test Typing Strategy

This document describes the phased approach to reintroduce TypeScript typing for Playwright / test code after temporarily excluding large spec files to stabilize application types.

## Goals

- Keep `app/` application build strictly typed without being polluted by broad implicit globals from test frameworks.
- Provide rich type safety in `tests/` (Playwright, utilities, factories) with minimal config duplication.
- Avoid reintroducing `any` creep when specs are added back.

## Current State

- `tsconfig.json` excludes: `tests/frontend/**`, selected large specs, and `tests/e2e/**` to keep `npx tsc --noEmit` clean.
- Playwright already provides its own type declarations via `@playwright/test` when imported, but spec files were causing errors due to mixed patterns and implicit anys.

## Proposed Phases

### Phase 1: Separate Test TSConfig

Create `tsconfig.tests.json` extending root config but narrowing `include` to test files and layering in test-specific libs.

Example (to add):

```jsonc
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "noEmit": true,
    "types": ["node", "@playwright/test"],
    "isolatedModules": false
  },
  "include": [
    "tests/**/*.ts",
    "tests/**/*.tsx"
  ]
}
```

Rationale:

- Keeps application strict settings.
- Adds explicit `@playwright/test` types only for test graph.
- Disables `isolatedModules` if needed for older CommonJS-style helper modules.

### Phase 2: Incremental Unexclude

1. Remove one previously excluded spec (e.g., `tests/quick-login-test.spec.ts`).
2. Run `npx tsc -p tsconfig.tests.json --noEmit`.
3. Fix surfaced `any` / implicit errors locally (add lightweight `types/test-utils.d.ts` if needed for custom globals).
4. Repeat for next spec groups (`tests/e2e/**`, large composite spec) until coverage restored.

### Phase 3: Shared Test Types Module

Add `tests/types/index.d.ts` for shared domain test helpers:

```ts
// tests/types/index.d.ts
import type { Page } from '@playwright/test';

declare global {
  interface TestUserCredentials {
    email: string;
    password: string;
    role?: string;
  }
  interface LoginHelpers {
    loginAs(page: Page, creds: TestUserCredentials): Promise<void>;
  }
}
export {};
```

Include it automatically via `types` or direct path in `tsconfig.tests.json`.

### Phase 4: CI Integration

Add a CI step:

```bash
npx tsc -p tsconfig.tests.json --noEmit
```

Fail build only if app tsconfig fails; test typing can be a separate (non-blocking initially) job until stabilized.

## Edge Cases & Patterns to Normalize

- Replace `page.waitForTimeout` usages with awaited selectors/assertions for more stable typing & reliability.
- Normalize error handling: `catch (err) { const message = err instanceof Error ? err.message : String(err); }`.
- Explicitly type factory return values in `tests/factories.py`-mirrored TS utilities if created.

## Migration Checklist

- [ ] Add `tsconfig.tests.json`.
- [ ] Add `tests/types/index.d.ts` (initially empty scaffold).
- [ ] Unexclude first small spec, compile with test config.
- [ ] Fix implicit anys.
- [ ] Iterate across remaining specs.
- [ ] Add CI command.

## Optional Enhancements

- Introduce path alias `@tests/*` via `baseUrl` and `paths` in test tsconfig only.
- Add ESLint override for `tests/**` to allow dev-time relaxed rules (but keep no implicit any).

## Decision Log

- Kept a separate config instead of monolithic union to avoid dragging Playwright globals into app runtime types.
- Chose additive phased reintroduction to reduce noise and keep PRs reviewable.

---

Maintainer Note: Keep this doc updated as phases complete; remove from backlog once CI step is green across all specs.
