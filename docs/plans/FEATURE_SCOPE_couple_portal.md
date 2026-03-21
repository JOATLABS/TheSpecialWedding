# Feature Scope: Couple Portal

## Overview

A read-only portal where **couples** can view key details about their wedding — timeline, guest stats, budget overview, and planner contact info — without needing admin access to the planner's dashboard.

## What Exists Today

| Component | Status |
|-----------|--------|
| Payment portal (`/portal/[token]`) | Built — contract, payments, payment method |
| Wedding slug page (`/[slug]`) | Built — public landing page for guests |
| Wedding data model | Complete — events, budget, guests, registries, FAQs |
| Couple authentication | Token-only (no login system for couples) |

## Proposed Architecture

### Route

```
/couple/[token]          → Couple dashboard (token-based, no login)
```

The planner generates a **couple access token** from the admin panel and shares it (link or QR). The couple bookmarks it.

### Pages / Tabs

1. **Overview** — wedding date countdown, couple names, venue, planner contact
2. **Timeline** — events list with dates, times, locations (read from `wedding.events`)
3. **Guest Stats** — total invited, RSVP'd, pending, declined (aggregated from guests + RSVPs)
4. **Budget Summary** — total budget, spent so far, remaining (read from budget data)
5. **Payment Schedule** — reuse existing portal payment view (`/portal/[token]`)
6. **Documents** — contract PDF, shared files from planner

### Backend Changes

| Change | File | Effort |
|--------|------|--------|
| Add `couple_access_token` field to Wedding model | `app/models/wedding.py` | Small |
| New `GET /public/couple-portal/{token}` endpoint | `app/api/couple_portal.py` (new) | Medium |
| Service to aggregate guest stats + budget for couple | `app/services/couple_portal_service.py` (new) | Medium |
| Admin UI button: "Generate Couple Link" | `app/admin/weddings/[id]/page.tsx` | Small |

### Frontend Changes

| Change | File | Effort |
|--------|------|--------|
| New couple portal page | `app/couple/[token]/page.tsx` (new) | Large |
| Couple portal layout | `app/couple/[token]/layout.tsx` (new) | Small |
| Reuse theme from wedding's `theme_config` | Existing hooks | Free |

### Data Exposed to Couples

**Visible:**
- couple_names, date, timezone, venue
- events (all details)
- guest count summary (totals only, not individual guest info)
- budget totals (total, spent, remaining — no line items)
- payment schedule & status
- planner name, email, phone
- registries, FAQs

**Hidden:**
- Individual guest list / contact info
- Detailed budget line items
- Admin settings
- Other weddings

### Security

- Token-based access (same pattern as payment portal)
- Rate limiting on token lookups
- Optional: planner can revoke/regenerate the couple token
- No write access — strictly read-only

## Effort Estimate

| Phase | Effort |
|-------|--------|
| Backend (model + API + service) | 4-6 hours |
| Frontend (portal page + components) | 6-8 hours |
| Integration & polish | 2-3 hours |
| **Total** | **12-17 hours** |

## Dependencies

- None — can be built independently of other features
- Optionally integrates with existing payment portal
