---
name: security-remediation-plan
description: Phased remediation plan for the current WeddingWebApp security review, prioritizing production blockers before follow-up KB consistency and cleanup work.
---

# Security Remediation Plan

Use this skill when working through the findings in `security_best_practices_report.md` for this repository.

## What this skill is for

- Drive remediation in a careful order instead of fixing findings opportunistically.
- Treat the SSE token leak and production docs/OpenAPI exposure as release blockers.
- Keep KB contract, route, performance, and legacy-context cleanup as scheduled follow-up work.

## Workflow

1. Read `phase-plan.md`.
2. Execute one phase at a time.
3. Do not start the next phase until the current phase has explicit validation results.
4. Preserve staging operability while tightening production behavior.

## Current repo-specific priorities

1. Remove JWT-in-query-string usage from the admin SSE stream.
2. Disable or explicitly gate `/docs`, `/redoc`, and `/openapi.json` in production.
3. Align KB status handling across model, API, and editor UX.
4. Fix or remove the unwired KB feedback-summary route.
5. Stop returning KB article bodies in list/search responses when they are not needed.
6. Remove or clearly deprecate the legacy admin auth/API context stack after confirming no consumers remain.

## Sequencing rule

Do not combine the Phase 1 SSE transport change with broader admin auth refactors. The safe move is to migrate the stream off query-string tokens first, validate it in staging, and only then consider wider auth convergence.
