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
docs/                  # Architecture docs, migration guides, QA reports
```

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.11+
- MongoDB 5.0+
- Redis 7+

### Local Development

```bash
# 1. Install frontend dependencies
npm install --legacy-peer-deps

# 2. Install backend dependencies
pip install -r requirements.txt

# 3. Start infrastructure
docker compose up -d mongo redis

# 4. Seed subscription plans
python scripts/seed_subscription_plans.py

# 5. Create root admin user
python scripts/setup_admin_user.py

# 6. Start the backend
uvicorn app.main:app --reload --port 8000

# 7. Start the frontend (separate terminal)
npm run dev
```

### Environment Variables

The platform requires these environment variables (set via `.env` or Coolify dashboard):

| Variable | Purpose |
|----------|---------|
| `MONGODB_URL` | MongoDB connection string |
| `SECRET_KEY` | JWT signing key (32+ chars, not a default) |
| `CORS_ORIGINS` | Allowed origins (comma-separated) |
| `NEXT_PUBLIC_API_BASE_URL` | Backend API URL for frontend |
| `FRONTEND_URL` | Frontend URL for generated links |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_MESSAGING_SERVICE_SID` | Twilio messaging service |
| `TWILIO_STATUS_CALLBACK_URL` | Webhook URL for delivery tracking |
| `RESEND_API_KEY` | Resend email API key |
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

The platform deploys as a single Docker container via `Dockerfile.coolify`:

```bash
# Dockerfile Location in Coolify: Dockerfile.coolify
# Builds Next.js frontend + FastAPI backend in one container
# Supervisor manages both processes
```

Set all environment variables in the Coolify dashboard. The container exposes port 3000 (Next.js) and 8000 (FastAPI) internally, with Supervisor orchestrating both.

## Roles

| Role | Access |
|------|--------|
| **Root Admin** | Platform management, planner invitations, subscription management, monitoring, error tracking |
| **Planner** | Wedding CRUD, guest management, RSVP, reminders, seating, vendors, budget, calendar, gallery |
| **Guest** | Wedding landing page, RSVP submission, gallery viewing (with OTP verification for private weddings) |
| **Vendor** | Contract viewing and signing via token-based access |

## License

Proprietary - All rights reserved. See [LICENSE](LICENSE) for details.
