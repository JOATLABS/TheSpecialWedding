# Feature Implementation Audit (February 2025)

This audit cross-references every feature document under `app/docs/features/` with the live code on the `work` branch. Items are grouped by their true delivery state so the roadmap and documentation can stay aligned.

## ✅ Fully Delivered

- **Budget category & summary management** (`BUDGET_MODULE.md`) – The admin budget dashboard exposes wedding selection, real-time summary cards, and full CRUD for categories exactly as described in the guide.【F:app/docs/features/BUDGET_MODULE.md†L9-L62】【F:app/admin/budget/page.tsx†L26-L205】【F:app/services/budgetApi.ts†L23-L79】
- **Vendor quote workflow** (`BUDGET_MODULE.md`) – Planners can list, create, accept/reject, and rate vendor quotes via the dedicated UI and service layer, matching the documented status tracking behaviour.【F:app/docs/features/BUDGET_MODULE.md†L20-L24】【F:app/admin/budget/quotes/page.tsx†L31-L164】【F:app/services/budgetApi.ts†L81-L120】
- **Guest CSV import pipeline** (`CSV_IMPORT_GUIDE.md`) – The importer enforces the documented column rules, defaults, and plus-one logic before inserting guests, and the admin endpoint is locked behind planner access as specified.【F:app/docs/features/CSV_IMPORT_GUIDE.md†L5-L89】【F:app/services/import_service.py†L13-L67】【F:app/api/admin_import.py†L9-L19】
- **Secure form response CSV export** (`CSV_EXPORT_IMPLEMENTATION.md`) – The responses page calls the hardened export endpoint with date/metadata filters, the helper normalises filenames, and backend sanitisation plus unit tests cover the flow end to end.【F:app/docs/features/CSV_EXPORT_IMPLEMENTATION.md†L5-L75】【F:app/admin/forms/[id]/responses/page.tsx†L52-L268】【F:app/services/formExport.ts†L23-L83】【F:app/api/forms.py†L411-L449】【F:app/services/form_service.py†L666-L801】【F:tests/unit/formExport.test.ts†L1-L96】
- **Planner metrics dashboard** (`PORTAL_STRATEGY.md`) – `/admin/planner` already consumes the `/admin/planner/metrics` API to render assigned weddings, RSVP rollups, and recent activity as the strategy document notes.【F:app/docs/features/PORTAL_STRATEGY.md†L16-L21】【F:app/admin/planner/page.tsx†L1-L118】【F:app/api/planner_metrics.py†L11-L164】

## 🟡 Started but Not Finished

- **Payment tracking experience** (`BUDGET_MODULE.md`) – Backend endpoints and models exist, but the planner UI still shows a “coming soon” toast and the modal/history components are absent, leaving the feature unfinished for users.【F:app/docs/features/BUDGET_MODULE.md†L15-L29】【F:app/admin/budget/page.tsx†L194-L205】【8aa0c7†L1-L2】【1d5241†L1-L2】
- **Custom budget template authoring** (`BUDGET_MODULE.md`) – Templates can be applied, yet the “Create Custom Template” button has no handler and there is no authoring workflow, so documentation correctly flags the gap.【F:app/docs/features/BUDGET_MODULE.md†L26-L29】【F:app/admin/budget/templates/page.tsx†L134-L138】
- **Form builder creation variants & analytics** (`FORM_BUILDER_GUIDE.md`) – Admins can only spin up forms from templates; blank creation, duplication, unread badges, and analytics remain future work despite being listed as roadmap items.【F:app/docs/features/FORM_BUILDER_GUIDE.md†L11-L87】【F:app/admin/forms/page.tsx†L29-L190】
- **Platform metrics analytics** (`PLATFORM_METRICS_GUIDE.md`) – The dashboard exists, but key metrics fall back to zeroes or constants and the referenced analytics service is still missing, leaving this feature in a partial state.【F:app/docs/features/PLATFORM_METRICS_GUIDE.md†L1-L54】【F:app/admin/metrics/page.tsx†L59-L115】
- **Form response notification system** (`form-notifications-implementation.md`) – Documentation outlines the plan, yet no response-specific methods, review fields, badges, or profile preferences have been built, so the initiative has not progressed past planning.【F:app/docs/features/form-notifications-implementation.md†L1-L38】【F:app/services/notification_service.py†L187-L215】【F:app/models/form.py†L234-L244】【F:app/admin/forms/[id]/responses/page.tsx†L238-L360】【F:app/admin/profile/page.tsx†L32-L190】

## ❌ Documented as Complete but Missing in Code

- **Vendor dashboard production readiness** (`MULTI_TENANT_ROADMAP.md`) – The roadmap marks the vendor dashboard as completed, yet the live page still seeds hard-coded placeholder tasks instead of real tenant data, so the documentation overstates delivery.【F:app/docs/features/MULTI_TENANT_ROADMAP.md†L44-L50】【F:app/admin/vendor/page.tsx†L51-L142】
- **Trial expiration security test coverage** (`TRIAL_EXPIRATION_SECURITY_AUDIT_REPORT.md`) – The audit cites dedicated security test suites that do not exist in the repository, meaning the claimed automated validation has not been implemented.【F:app/docs/features/TRIAL_EXPIRATION_SECURITY_AUDIT_REPORT.md†L188-L200】【d8f2aa†L1-L5】

## Recommended Next Steps

1. Update the highlighted documents so completion badges match the current code reality.
2. Prioritise finishing the partially delivered items (payments UI, form builder enhancements, analytics, and notifications) with integration tests to prevent regressions.
3. Backfill the missing vendor workspace and trial security tests before advertising those capabilities as production ready.
