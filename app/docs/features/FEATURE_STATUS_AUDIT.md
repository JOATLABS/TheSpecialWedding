# Feature Status Audit (January 2025 Update)

This audit validates the feature documentation in `app/docs/features/` against the code that currently ships on the `work` branch. Items are grouped by their real delivery status so product planning can align the roadmap and documentation.

## Legend
- ✅ — Feature behaves as described in the docs.
- 🟡 — Partially implemented; additional work is needed to meet the documented behaviour.
- ❌ — Documentation claims the feature is complete, but the implementation is missing.

## ✅ Implemented as Documented
- **Budget category management** (`BUDGET_MODULE.md`) – The documented workflow (wedding selector, live budget summary, category CRUD) exists end-to-end in the admin dashboard and associated API client.【F:app/docs/features/BUDGET_MODULE.md†L56-L118】【F:app/admin/budget/page.tsx†L61-L166】【F:app/services/budgetApi.ts†L23-L69】
- **Vendor quote workflow** (`BUDGET_MODULE.md`) – Creating, filtering, updating, and rating vendor quotes is implemented in both the UI and API layer, matching the guide’s description.【F:app/docs/features/BUDGET_MODULE.md†L82-L91】【F:app/admin/budget/quotes/page.tsx†L91-L168】【F:app/components/budget/VendorQuoteCard.tsx†L17-L200】【F:app/services/budgetApi.ts†L81-L129】

## 🟡 Implemented Partially / Still In Progress
- **Budget template customisation** (`BUDGET_MODULE.md`) – Planners can list and apply templates, but the documented “Create Custom Template” and editable category lists are not wired up (the button has no handler and there is no template creation API), so template authoring remains outstanding.【F:app/docs/features/BUDGET_MODULE.md†L93-L118】【F:app/admin/budget/templates/page.tsx†L134-L160】【F:app/services/budgetApi.ts†L131-L152】
- **Secure CSV export end-to-end** (`CSV_EXPORT_IMPLEMENTATION.md`) – The FastAPI endpoint and service implement the hardened export pipeline, yet the admin responses page still generates CSVs client-side and never calls the new endpoint, leaving the feature half-integrated.【F:app/docs/features/CSV_EXPORT_IMPLEMENTATION.md†L9-L120】【F:app/api/forms.py†L411-L518】【F:app/services/form_service.py†L666-L720】【F:app/admin/forms/[id]/responses/page.tsx†L88-L131】
- **Form builder creation options** (`FORM_BUILDER_GUIDE.md`) – Documentation promises blank-form and duplicate creation paths; the current admin screen only creates forms from templates, with no duplicate or blank-flow UI present.【F:app/docs/features/FORM_BUILDER_GUIDE.md†L11-L69】【F:app/admin/forms/page.tsx†L24-L119】【c45a7c†L1-L1】
- **Platform analytics dashboard** (`PLATFORM_METRICS_GUIDE.md`) – The guide references dedicated analytics services and endpoints, but the metrics page synthesises estimates from generic user data and the documented backend modules do not exist yet.【F:app/docs/features/PLATFORM_METRICS_GUIDE.md†L1-L36】【F:app/admin/metrics/page.tsx†L54-L118】【cc35a1†L1-L1】
- **Vendor dashboard parity** (`MULTI_TENANT_ROADMAP.md`) – The roadmap labels the vendor dashboard “production ready”, yet the page still renders hard-coded placeholder tasks and TODO comments instead of real tenant data.【F:app/docs/features/MULTI_TENANT_ROADMAP.md†L44-L123】【F:app/admin/vendor/page.tsx†L24-L100】

## ❌ Documented as Complete but Missing
- **Payment tracking UI** (`PAYMENT_TRACKING.md`, `BUDGET_MODULE.md`) – Both docs state that payment recording modals and history tabs are live, but the budget page still shows a “coming soon” toast and the PaymentModal/PaymentHistory components are absent from the codebase.【F:app/docs/features/PAYMENT_TRACKING.md†L3-L129】【F:app/docs/features/BUDGET_MODULE.md†L63-L132】【F:app/admin/budget/page.tsx†L194-L197】【8e8ca7†L1-L1】
- **Email notification system** (`EMAIL_NOTIFICATION_SYSTEM.md`) – The write-up references Celery workers, Redis task queues, and supporting modules that are not present (no Celery files or dependencies), and the existing notification service still contains placeholder sending logic.【F:app/docs/features/EMAIL_NOTIFICATION_SYSTEM.md†L1-L44】【b35e7a†L1-L1】【984397†L1-L1】【F:requirements.txt†L1-L22】【F:app/services/notification_service.py†L187-L199】
- **Form response notification enhancements** (`form-notifications-implementation.md`) – Despite the document marking the work “COMPLETED”, the notification service lacks response-specific APIs, the form model has no reviewed/unreviewed fields, the responses UI has no review toggles or badges, the profile screen exposes no notification preferences, and there is no NotificationBadge component in the UI library.【F:app/docs/features/form-notifications-implementation.md†L15-L158】【F:app/services/notification_service.py†L15-L188】【F:app/models/form.py†L1-L200】【F:app/admin/forms/[id]/responses/page.tsx†L33-L193】【F:app/admin/profile/page.tsx†L1-L190】【68f3a4†L1-L3】

## Recommended Next Steps
1. Update the feature guides above to reflect the real implementation status so planners and engineers share a single source of truth.
2. Prioritise the incomplete items (budget payments UI, CSV export wiring, notification system, vendor tooling, analytics backend) with accompanying backend and frontend work.
3. Backfill automated tests (API and Playwright) once each feature is delivered to prevent documentation drift during future releases.
