# Architectural & Platform Roadmap

Where **The Special Wedding** is today, and where the product and platform are heading.
This complements the [Architecture](ARCHITECTURE.md) reference and the
[feature documentation](README.md#feature-documentation).

> Roadmap items describe direction and priority, not commitments or dates. Sequencing
> may change with customer feedback.

## Where we are (shipped & in production)

The platform serves professional wedding planners end-to-end:

- **Planning workspace** — weddings, guests, RSVP (OTP-verified), communications &
  reminders (SMS/email), seating charts, vendors & contracts, budgets, service packages,
  forms, calendar with Google sync, gallery, and guest memories.
- **Client experience** — guest-facing landing pages and a dedicated couple portal
  (guest tracking, registry, FAQ, memories review).
- **Monetization** — Stripe subscriptions across Solo / Boutique / Signature / Enterprise
  tiers, Stripe Connect payouts, and a finance-autopilot view of money in and out.
- **AI** — Gemini-powered budget, dashboard, seating, cash-flow, and vendor insights,
  metered by plan credits.
- **Operations** — multi-tenant isolation, role- and plan-based access, team seats,
  Web Push/in-app/email notifications, audit logging, health monitoring, and a Root
  Admin control plane.

## Near-term (next)

### Platform & architecture
- **Split-service deployment** — promote frontend and backend to separate Coolify
  services (from today's single combined container) for independent scaling and faster
  deploys. GitHub secret-sync tooling for this path already exists in `scripts/deploy/`.
- **Observability** — expand structured metrics, error budgets, and alerting on top of
  the existing health checks and audit log.
- **Performance** — continue query/index tuning and load-test-driven optimization of the
  highest-traffic paths (guest lists, landing pages, memories uploads).

### Product
- **QR check-in** — day-of guest check-in via QR codes (currently a reserved,
  not-yet-enabled plan capability).
- **Advanced & vendor analytics** — deeper reporting for Signature/Enterprise tiers.
- **Vendor collaboration** — richer two-way vendor workflows beyond token contract
  signing.

## Mid-term

- **Custom domains** — let planners serve wedding sites on their own domains.
- **White-label** — planner-branded couple/guest experiences for higher tiers.
- **Vendor advertising platform** — monetized vendor directory/ads surfaced to planners
  and couples (foundations exist in the admin Ad Platform and vendor data).
- **Deeper calendar policy layer** — connection policies and finer availability/visibility
  controls for teams.

## Longer-term / exploratory

- **Public API & integrations** — a documented API (reserved as a plan capability) and
  webhooks for third-party tools.
- **Modular service extraction** — peel high-load modules (e.g. media, messaging) out of
  the monolith into dedicated services where scale justifies it.
- **Internationalization** — multi-currency and multi-language guest experiences.
- **Expanded AI** — proactive planning assistants and automated, AI-drafted client
  communications.

## Guiding principles

1. **Tenant isolation first** — every change preserves strict separation between planners'
   data.
2. **Operational simplicity** — prefer the simplest deployment that meets the need; split
   only where scale demands it.
3. **Plan-gated value** — new capabilities slot cleanly into the subscription tiers and
   credit model.
4. **Client trust** — couples and guests stay in control of their data, reviews, and
   privacy.
