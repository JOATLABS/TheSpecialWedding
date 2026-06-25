# The Special Wedding

A multi-tenant SaaS platform for professional wedding planners. Manage guest lists, send RSVP invitations via SMS/email, track seating arrangements, handle vendor contracts, process payments, and deliver beautiful wedding landing pages to guests.

**Live:** [thespecialwedding.io](https://thespecialwedding.io)

## What It Does

| Feature | Description |
|---------|-------------|
| **Wedding Landing Pages** | Themed, mobile-friendly guest-facing pages with RSVP, gallery, event details, and dark mode support |
| **Guest Management** | Import/export guests, QR codes, CSV export, phone/email tracking, plus-one management |
| **RSVP System** | OTP-verified RSVP flow via Twilio SMS or email, already-RSVPed detection, Request RSVP Link for lost invitations |
| **SMS & Email Reminders** | Bulk and individual sends via Twilio and Resend, delivery tracking, health monitoring, opt-out handling |
| **Seating Charts** | Drag-and-drop canvas, capacity validation, PDF/banner export for venue display |
| **Vendor & Contracts** | Vendor management, contract creation with token-based access, milestone payments, PDF generation |
| **Budget Tracking** | Category-based budgets, vendor quotes comparison, payment tracking, budget alerts |
| **AI Insights** | Google Gemini-powered budget insights, dashboard insights, seating optimization, contract drafting |
| **Calendar** | Planner task management with Google Calendar two-way sync, ICS downloads with timezone support |
| **Gallery** | Cloudflare R2 media storage, privacy-aware access, presigned uploads |
| **Billing** | Stripe subscriptions, checkout sessions, webhook processing, custom trial durations |
| **Notifications** | Web Push (VAPID), in-app notifications, email alerts for planners and admins |
| **Platform Monitoring** | Health checks for all external services, error tracking, audit logging with TTL auto-cleanup |

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS |
| **Backend** | FastAPI (Python 3.11), Motor (async MongoDB driver) |
| **Database** | MongoDB 5.0 |
| **Cache** | Redis 7 |
| **SMS/OTP** | Twilio (Messaging Service + Status Callbacks) |
| **Email** | Resend API |
| **Payments** | Stripe (Subscriptions, Checkout, Webhooks) |
| **AI** | Google Gemini API |
| **Storage** | Cloudflare R2 (S3-compatible) |
| **PDF** | WeasyPrint (seating charts, contracts), python-pptx |
| **Push** | Web Push API with VAPID |
| **Cron** | Cloudflare Workers (trial expiry, metrics snapshots, backups, uptime) |
| **Deployment** | Coolify (Docker, single server) |

## Project Structure

```
app/
  [slug]/              # Guest-facing wedding pages (/{slug}, /{slug}/gallery, etc.)
  admin/               # Planner & root admin dashboard pages
    billing/           # Stripe billing UI
    budget/            # Budget management
    forms/             # Custom form builder
    gallery/           # Gallery upload management
    guests/            # Guest list management
    planner/           # Planner dashboard, calendar, activity log
    platform/          # Root admin: metrics, errors, health
    reminders/         # SMS/email reminder management
    saas/              # SaaS admin: plans, users, content, theme
    seating/           # Seating chart canvas
    vendors/           # Vendor & contract management
    weddings/          # Wedding CRUD
  api/                 # FastAPI route handlers
  components/          # Shared React components
  contexts/            # React contexts (Auth, Theme, Wedding)
  core/                # Settings, database, indexes
  models/              # Pydantic models / MongoDB schemas
  services/            # Business logic layer
  utils/               # Shared utilities

cloudflare-workers/    # Cron workers (trial, metrics, backup, uptime)
scripts/               # Seed scripts, setup, changelog tools
docs/                  # Production docs: per-feature guides, architecture, roadmap
```

## Getting Started

### Prerequisites

- Node.js 20.x or 24.x
- npm 10+
- Python 3.11+
- MongoDB 5.0+
- Redis 7+

### Local Development

```bash
# 1. Install frontend dependencies
npm ci

# Validate the local dependency tree before starting the frontend
npm run deps:doctor

# 2. Install backend dependencies
pip install -r requirements.txt

# 3. Start infrastructure
docker compose up -d mongo redis

# 4. Seed subscription plans
python scripts/seed_subscription_plans.py

# 5. Create root admin user
python scripts/setup_admin_user.py

# 6. Create planner/vendor/couple/team-member test accounts manually
#    through the frontend flows when needed. The TEST_* values in .env
#    are fixture credentials for manual QA, not auto-seeded users.

# 7. Start the backend
uvicorn app.main:app --reload --port 8000

# 8. Start the frontend (separate terminal)
npm run dev
```

This repository is `npm`-only. Use `package-lock.json` as the canonical lockfile.
If your install becomes stale or partially missing, recover with:

```bash
rm -rf node_modules
npm ci
npm run deps:doctor
```

If you intentionally change frontend dependencies, use `npm install` and commit the updated `package-lock.json`.

### Environment Variables

The platform requires these environment variables (set via `.env` or Coolify dashboard):

| Variable | Purpose |
|----------|---------|
| `MONGODB_URL` | MongoDB connection string |
| `SECRET_KEY` | JWT signing key (32+ chars, not a default) |
| `CORS_ORIGINS` | Allowed origins (comma-separated) |
| `NEXT_PUBLIC_API_BASE_URL` | Public backend API fallback for server-side frontend calls and deploy tooling |
| `FRONTEND_URL` | Frontend URL for generated links |
| `INTERNAL_API_BASE_URL` | Runtime backend URL used by the frontend container for SSR/data fetches and `/api/proxy` |
| `BACKEND_SERVICE_URL` | Optional explicit runtime target for `/api/proxy` in split-service deployments |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_MESSAGING_SERVICE_SID` | Twilio messaging service |
| `TWILIO_STATUS_CALLBACK_URL` | Webhook URL for delivery tracking |
| `RESEND_API_KEY` | Resend email API key |
| `RESEND_BILLING_EMAIL` | Dedicated sender address for Stripe billing/invoice emails |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `GOOGLE_GEMINI_API_KEY` | Google Gemini API key |
| `MEDIA_DOMAIN` | Cloudflare R2 public domain |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | R2 credentials |
| `S3_BUCKET_NAME` / `S3_ENDPOINT_URL` | R2 bucket config |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Web Push VAPID keys |
| `VAPID_EMAIL` | VAPID contact email |
| `REDIS_URL` | Redis connection string |

### Production Deployment (Coolify)

The current production path deploys as a single Docker container via `Dockerfile.coolify`:

```bash
# Dockerfile Location in Coolify: Dockerfile.coolify
# Builds Next.js frontend + FastAPI backend in one container
# Supervisor manages both processes
```

Runtime details:

- frontend process: `npm start` on port `3000`
- backend process: `/usr/local/bin/start-backend.sh` on port `8000`
- backend worker count comes from `WEB_CONCURRENCY` and defaults to `2`
- if `REDIS_ENABLED` is not truthy, the backend forces `WEB_CONCURRENCY=1` so SSE remains correct across workers

Set all environment variables in the Coolify dashboard. The container exposes port `3000` (Next.js) and `8000` (FastAPI) internally, with Supervisor orchestrating both.

Recommended next deployment path:

- A split-service Coolify rollout (frontend and backend as separate services) — see the [platform roadmap](docs/ROADMAP.md).
- [GitHub secret sync script](scripts/deploy/sync_github_secrets.sh)

Repo rollout status:

- staging auto-deploy after CI: [`.github/workflows/deploy-coolify.yml`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/.github/workflows/deploy-coolify.yml)
- manual production promotion by immutable SHA: [`.github/workflows/promote-coolify-production.yml`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/.github/workflows/promote-coolify-production.yml)
- shared deploy verification and rollback logic: [`.github/workflows/coolify-deploy-shared.yml`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/.github/workflows/coolify-deploy-shared.yml)

For the production architecture and platform direction, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Roles

| Role | Access |
|------|--------|
| **Root Admin** | Platform management, planner invitations, subscription management, monitoring, error tracking |
| **Planner** | Wedding CRUD, guest management, RSVP, reminders, seating, vendors, budget, calendar, gallery |
| **Guest** | Wedding landing page, RSVP submission, gallery viewing (with OTP verification for private weddings) |
| **Vendor** | Contract viewing and signing via token-based access |

## License

Proprietary - All rights reserved. See [LICENSE](LICENSE) for details.
