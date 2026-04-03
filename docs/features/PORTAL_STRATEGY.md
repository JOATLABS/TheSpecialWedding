# Vendor and Couple Portal Strategy

## Objective
Define how the wedding planning platform should support planners, couples, and vendors with portals that balance collaboration, transparency, and implementation effort.

## Research highlights
- Dedicated vendor portals provide a shared workspace for onboarding, managing purchase orders, product details, bidding, invoicing, and payment processing, which strengthens operational visibility for both the business and its suppliers.【21e590†L3-L18】
- Supplier enablement experts report that many organizations still rely on email or ERP stopgaps and that portals fail when data and workflows are not standardized, underscoring the need for intuitive self-service and strong data governance.【29426d†L7-L18】
- Wedding planning coaches emphasize that a client dashboard should centralize budgets, guest lists, vendor contracts, timelines, and communication to replace scattered tools and improve the client experience.【a1ca90†L6-L29】
- Event planning client portal platforms highlight features like invoices, payment reminders, e-signatures, shared files, tasks, questionnaires, and vision boards so planners and clients can collaborate asynchronously.【e39ebf†L1-L15】
- Modern client portal products for wedding and event planners automate collecting files, forms, approvals, and document signatures while giving customers visibility into project status, tasks, and resources in one hub.【70cb30†L1-L12】

## Portal vision
Design a multi-portal experience with a planner control center, a vendor workspace, and a couple dashboard that all connect to the same project data layer.

### Planner command center
- Maintain the source of truth for project timelines, budgets, vendor contracts, tasks, and documents.
- Configure which data is exposed to couples and vendors, including granular permissions for read-only vs. editable fields.
- Monitor engagement analytics (task completion, overdue approvals, unread updates) to intervene early.
- Launch templated workflows (e.g., vendor onboarding packet, couple design review) that auto-assign tasks and request files.
- **Current delivery**: The `/admin/planner` dashboard is already live with assigned wedding lists, RSVP rollups, and recent activity, backed by the `/admin/planner/metrics` endpoint. Iterations should focus on deeper analytics and automation rather than rebuilding the core workspace.【F:app/admin/planner/page.tsx†L1-L167】【F:app/api/planner_metrics.py†L1-L120】

### Vendor workspace (portal or light dashboard)
- **Use cases**: onboarding, compliance (W-9/insurance uploads), deliverable tracking, quote/bid submissions, invoice uploads, payment status review, and secure messaging.
- **Access model**: authenticated portal with optional passwordless links for low-friction participation; allow single-event or reusable vendor profiles.
- **Key capabilities**:
  - Guided onboarding forms aligned to standardized data models so vendor records map cleanly into the planner’s system (addresses HICX findings).
  - Task list with due dates, comment threads, and file exchanges for deliverables (e.g., menu selections, floor plan sign-off).
  - Self-service views of purchase orders, approved budgets, and payment milestones to reduce back-and-forth emails.
  - Notifications triggered when the planner updates requirements or when vendor submissions require review.
- **Phased delivery**:
  1. Start with secure web forms tied to vendor records (MVP for collecting data and documents).
  2. Layer in login-based dashboards with status widgets and messaging once data governance is stable.
  3. Add advanced modules (bidding, inventory, payments) aligned with roadmap priorities.

### Couple dashboard
- **Use cases**: view curated reports, budgets, RSVPs, seating charts, vendor statuses, design boards, and shared documents.
- **Key capabilities**:
  - Read/write access to selected planner forms (RSVP updates, questionnaire responses) with audit trail.
  - Task checklists and timeline milestones the couple can update, with planner notifications on changes.
  - Visual boards (mood boards, inspiration galleries) and document sharing to capture feedback asynchronously.
  - Integrated payment summary (invoices, upcoming installments) and signature workflows for proposals/contracts.
  - Mobile-friendly, login-optional access for quick approvals while preserving security.
- **Feedback loops**: embed quick reactions or comment threads alongside reports so couples can approve or request changes without leaving the portal.

## Implementation roadmap
1. **Foundations** (Sprint 1-2)
   - Audit existing forms and data schemas; define unified vendor and couple data models.
   - Extend authentication/authorization to support role-based access for vendors and couples.
   - Build portal theming and navigation shell that can host role-specific modules.
2. **Couple dashboard MVP** (Sprint 3-5)
   - Ship read-only widgets for budget, timeline, and document library, plus RSVP form editing.
   - Integrate task checklist assignments and approval comments.
   - Enable planner-controlled sharing presets per section.
3. **Vendor workspace MVP** (Sprint 3-6 in parallel)
   - Deliver secure onboarding packet (forms + file uploads) with status tracking.
   - Expose purchase order summary and payment milestone statuses.
   - Add messaging/comments for deliverables to reduce email reliance.
4. **Feedback and automation enhancements** (Sprint 6-8)
   - Introduce automated reminders and digest emails for overdue tasks.
   - Provide analytics dashboard for planner to see portal engagement.
   - Support template-driven workflows (e.g., florals, catering) to auto-assign vendor and couple tasks.
5. **Advanced collaboration** (Sprint 9+)
   - Add e-signatures, proposal approvals, and integrated payments.
   - Explore real-time co-editing (floor plans, seating) and API integrations with specialized vendor tools.
   - Offer optional lightweight mobile app or push notifications if demand warrants.

## Success measures
- Vendor onboarding cycle time and task completion rates improve vs. email-based process.
- Couples access the dashboard weekly (or as defined) with reduced ad-hoc status requests.
- Planner support load (status emails, manual reminders) decreases measurably.
- Portal satisfaction surveys show high ease-of-use scores across roles, validating continued investment.
