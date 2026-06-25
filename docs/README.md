# The Special Wedding — Documentation

Production documentation for **The Special Wedding**, a multi-tenant SaaS platform
for professional wedding planners. Every document below describes a single feature:
what it is, the features it works with, and the step-by-step actions a user takes to
use it — illustrated with screenshots from the live application.

> **Live:** [thespecialwedding.io](https://thespecialwedding.io)

## How this documentation is organized

- **[Feature documentation](#feature-documentation)** — one document per feature.
- **[Architecture](ARCHITECTURE.md)** — how the platform is built and how the pieces fit together.
- **[Platform roadmap](ROADMAP.md)** — where the product and platform are heading.
- **[Brand](brand/)** — logos, brand guidelines, and the official branding brief.

## Roles at a glance

| Role | What they do |
|------|--------------|
| **Root Admin** | Operates the platform: monitoring, accounts, subscription plans, vendor advertising. |
| **Planner** | Runs weddings end-to-end: guests, RSVP, reminders, seating, vendors, budget, calendar, gallery. |
| **Team Member** | A planner's staff, with role-scoped permissions on the planner's weddings. |
| **Couple** | The clients, working in their own portal: guest tracking, registry, FAQ, memories. |
| **Guest** | Visits the wedding landing page, RSVPs, views the gallery, uploads memories. |
| **Vendor** | Reviews and signs contracts and receives payments via token-based access. |

## Feature documentation

### Planning workspace (Planner)
1. [Planner Dashboard](features/planner-dashboard.md)
2. [Weddings](features/weddings.md)
3. [Wedding Landing Pages](features/wedding-landing-pages.md)
4. [Guest Management](features/guest-management.md)
5. [RSVP System](features/rsvp-system.md)
6. [Communications & Reminders](features/communications-and-reminders.md)
7. [Seating Charts](features/seating-charts.md)
8. [Vendors & Contracts](features/vendors-and-contracts.md)
9. [Budget Tracking](features/budget-tracking.md)
10. [Payments & Finance Autopilot](features/payments-and-finance-autopilot.md)
11. [Service Packages](features/service-packages.md)
12. [Form Builder](features/forms-builder.md)
13. [Calendar](features/calendar.md)
14. [Gallery](features/gallery.md)
15. [Guest Memories](features/guest-memories.md)
16. [Team Management](features/team-management.md)
17. [AI Insights](features/ai-insights.md)
18. [Notifications](features/notifications.md)

### Client experience (Couple & Guests)
19. [Couple Portal](features/couple-portal.md)

### Account & platform
20. [Billing & Subscriptions](features/billing-and-subscriptions.md)
21. [Platform Administration](features/platform-administration.md)

---

_Screenshots in this documentation were captured from the running application. Some
panels (for example AI insights and external messaging) depend on third-party API keys
and appear in a configuration-pending state in non-production environments._
