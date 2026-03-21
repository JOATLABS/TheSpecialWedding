# Feature Scope: Guest Check-In

## Overview

A day-of check-in system that lets planners (or designated staff) scan guest QR codes at the venue entrance. Provides a live attendance dashboard showing who has arrived, who is missing, and real-time headcount.

## What Exists Today

| Component | Status |
|-----------|--------|
| Backend `CheckInService` | Built — `POST /checkin/{token}`, `GET /checkin/status/{token}` |
| MongoDB `checkins` collection | Schema defined (guest_id, checked_in_at, method, by) |
| QR code generation | Built — single guest PNG, bulk ZIP export |
| Guest tokens | Built — 10-char alphanumeric, stored on guest record |
| QR codes link to | RSVP page (`/{slug}/invite/{token}`) — NOT check-in |
| Scanner UI | **Not built** |
| Live dashboard | **Not built** |

## Proposed Architecture

### Routes

```
/admin/checkin                → Check-in scanner page (planner auth)
/admin/checkin/dashboard      → Live attendance dashboard (planner auth)
```

### Phase 1: Scanner Page

A mobile-friendly page that:

1. Opens the device camera using `navigator.mediaDevices.getUserMedia()`
2. Reads QR codes in real-time (use `jsQR` or `html5-qrcode` library — no native app needed)
3. Decodes the guest token from the URL in the QR code
4. Calls `POST /checkin/{token}` to record the check-in
5. Shows success (guest name + photo if available) or error (already checked in, not found)
6. Auto-resets for the next scan after 3 seconds

**Manual fallback:** Search-by-name field for guests who forgot their QR code.

### Phase 2: Live Dashboard

A dashboard showing:

1. **Headcount bar** — X of Y guests arrived (progress bar)
2. **Recent arrivals** — live feed of last 10 check-ins with timestamps
3. **Missing guests** — list of RSVP'd guests who haven't arrived
4. **Stats cards** — total expected, checked in, percentage, avg check-in rate

Auto-refreshes via polling (reuse `usePolling` hook, 10s interval).

### Backend Changes

| Change | File | Effort |
|--------|------|--------|
| Add `GET /checkin/dashboard/{wedding_id}` endpoint | `app/api/checkin.py` | Medium |
| Add `GET /checkin/recent/{wedding_id}` endpoint | `app/api/checkin.py` | Small |
| Extend CheckInService with dashboard aggregation | `app/services/checkin_service.py` | Medium |
| Add `method: "qr_scan"` to check-in records | `app/services/checkin_service.py` | Tiny |
| Add manual check-in by name endpoint | `app/api/checkin.py` | Small |

### Frontend Changes

| Change | File | Effort |
|--------|------|--------|
| Scanner page with camera + QR decode | `app/admin/checkin/page.tsx` (new) | Large |
| Live dashboard page | `app/admin/checkin/dashboard/page.tsx` (new) | Medium |
| Add "Check-In" nav item to admin sidebar | `app/admin/components/Sidebar.tsx` | Tiny |
| Install `html5-qrcode` package | `package.json` | Tiny |

### QR Code Update

Currently QR codes encode the RSVP URL: `/{slug}/invite/{token}`

For check-in, we have two options:

**Option A (recommended):** Keep the same QR code. The scanner page extracts the token from the URL and calls the check-in API. No need to regenerate QR codes.

**Option B:** Generate separate check-in QR codes with a different URL pattern. More complexity, no real benefit.

### Check-In Record Schema (extended)

```javascript
{
  "_id": ObjectId,
  "guest_id": String,
  "wedding_id": ObjectId,        // NEW — for dashboard queries
  "checked_in_at": ISODate,
  "method": "qr_scan" | "manual" | "search",
  "by": String (staff email),
  "device_info": String           // Optional — browser user agent
}
```

### Security

- Requires planner/admin authentication (existing `require_admin_or_planner`)
- Rate limiting on check-in endpoint to prevent abuse
- Duplicate check-in protection already exists (409 response)
- Camera permission handled by browser (user must approve)

## Effort Estimate

| Phase | Effort |
|-------|--------|
| Phase 1: Scanner page + backend updates | 6-8 hours |
| Phase 2: Live dashboard | 4-6 hours |
| QR code parsing + testing | 2-3 hours |
| **Total** | **12-17 hours** |

## Dependencies

- `html5-qrcode` npm package (~50KB gzipped)
- Device with camera (phone/tablet preferred for day-of use)
- Existing QR codes work as-is (Option A)

## Priority Recommendation

This feature is high-impact for the "day-of" experience and directly addresses the value proposition of the platform. The backend is already 70% built — the main effort is the scanner UI and live dashboard.
