# Sprint 6 Feature Spec: Registry, FAQ, QR Code, Push Notifications & PWA

**Author:** Etastic (spec drafted by Claude)
**Date:** 2026-03-23
**Sprint:** 6 — Couple Portal Enhancements
**Status:** Ready for Implementation

---

## 1. Problem Statement

The couple portal already has all the backend data and infrastructure for five additional features — registry display, FAQ display, QR code sharing, push notifications, and PWA support — but none of them are surfaced to the couple. Couples currently have to visit the public wedding landing page to see registries and FAQs, can't share their portal link easily, receive no real-time browser notifications for updates/messages, and can't install the portal as an app on their phone. These are all capabilities the platform already supports for planners or guests — they just haven't been wired into the couple portal.

The infrastructure is proven and production-tested. The gap is purely a frontend + auth-layer wiring issue, not a backend data problem.

---

## 2. Goals

1. **Registry & FAQ visibility** — Couples see their wedding registries and FAQs directly in the portal dashboard, eliminating the need to visit the public landing page for this information.
2. **One-tap portal sharing** — Couples can generate and download a QR code that links to their portal login, making it easy to share access with their partner or save for reference.
3. **Real-time push notifications** — Couples receive browser push alerts for new planner updates, messages, form assignments, meeting changes, and note replies — reducing missed communication.
4. **Installable app experience** — Couples can install the portal as a PWA on mobile/desktop, with offline access to cached dashboard data and app-like navigation.

---

## 3. Non-Goals

- **Registry editing by couples** — Couples view registries but do not add/edit/remove them. That remains a planner function. (Keeps the planner as the source of truth.)
- **FAQ editing by couples** — Same as above. FAQs are planner-managed content displayed read-only to couples.
- **QR code customization** — No branded QR codes, custom colors, or logo embedding. Standard black-and-white QR code is sufficient. (Can be enhanced later if demand arises.)
- **Offline push notifications** — Push only works when the browser/PWA is registered. We don't implement SMS fallback for missed pushes. (SMS is a separate channel with cost implications.)
- **Full offline editing** — PWA caches the dashboard for viewing but does not support offline form submissions, messages, or note creation. (Sync conflicts are complex and low-value for v1.)

---

## 4. Reuse Map — What Already Exists

This section documents every existing component, service, endpoint, and pattern that Sprint 6 reuses. **Nothing below should be recreated or duplicated.**

### 4.1 Registry Display

| Asset | Location | What It Does |
|-------|----------|--------------|
| `RegistryItemModel` | `/app/models/wedding.py` lines 44-47 | Pydantic model: `name`, `url`, `color` fields |
| `get_portal_dashboard()` | `/app/services/couple_portal_service.py` line 69 | Already returns `registries: wedding.get("registries", [])` in the dashboard response |
| Landing page registry rendering | `/app/components/landing-page/LandingLayout.tsx` lines 107-175 | Responsive grid with color-coded buttons, external link handling, fallback defaults — **reuse this layout pattern** |
| Dashboard data flow | `/app/couple/dashboard/page.tsx` | Dashboard already fetches and stores registries in `weddingData.wedding.registries` — just not rendering them in a tab |

**Effort: 🟢 Trivial** — Add a `Registry` tab to the existing `TabType` union and render the data already in state using the landing page's grid pattern.

### 4.2 FAQ Display

| Asset | Location | What It Does |
|-------|----------|--------------|
| `FAQItemModel` | `/app/models/wedding.py` lines 50-54 | Pydantic model: `question`, `answer`, `link_url`, `link_label` |
| `get_portal_dashboard()` | `/app/services/couple_portal_service.py` line 70 | Already returns `faqs: wedding.get("faqs", [])` |
| Landing page FAQ rendering | `/app/components/landing-page/LandingLayout.tsx` lines 182-243 | Accordion-style cards with optional external links — **reuse this layout pattern** |
| Dashboard data flow | `/app/couple/dashboard/page.tsx` | `weddingData.wedding.faqs` is already in component state |

**Effort: 🟢 Trivial** — Same pattern as registry. Add tab, render existing data.

### 4.3 QR Code Generation

| Asset | Location | What It Does |
|-------|----------|--------------|
| `generate_qr_code(url)` | `/app/services/guest_export_service.py` lines 33-71 | Takes a URL string, returns PNG bytes using `qrcode[pil]` |
| QR dependencies | `requirements.txt` | `qrcode[pil]` and `pillow` already installed |

**New work needed:**
- One new API endpoint: `GET /couple-portal/qr-code` that calls `generate_qr_code(couple_portal_url)` and returns the PNG
- One frontend widget: QR code display with download button

**Effort: 🟡 Small** — ~15 lines backend, ~30 lines frontend.

### 4.4 Push Notifications (Couple-Side)

| Asset | Location | What It Does |
|-------|----------|--------------|
| `WebPushService` | `/app/services/web_push_service.py` (255 lines) | Full VAPID-based push: `save_subscription()`, `send_notification()`, `remove_subscription()`, health checks |
| `web_push_service` singleton | Same file, bottom | Instantiated and ready to use |
| Push API endpoints | `/app/api/web_push.py` | Subscribe, unsubscribe, send, health — **BUT all require `require_admin_or_planner` auth** |
| Service worker | `/public/sw.js` (87 lines) | Handles push events, notification clicks, subscription changes — **fully reusable as-is** |
| VAPID public key endpoint | `GET /web-push/vapid-public-key` | No auth required — already works for couples |
| `planner_notification_service` | `/app/services/planner_notification_service.py` | `create_notification()` already sends push to planner when couple acts — **use same pattern in reverse** |

**New work needed:**
- Couple-specific push endpoints: `POST /couple-portal/push/subscribe`, `DELETE /couple-portal/push/unsubscribe` — using `require_couple_auth` instead of `require_admin_or_planner`
- Trigger push to couple on: new planner update, new message from planner, form assigned, meeting scheduled/cancelled, note reply from planner
- Frontend: notification permission prompt + subscription management in couple dashboard settings

**Effort: 🔴 Medium** — The service layer is done, but new auth-scoped endpoints + trigger wiring across 5 event types = ~100 lines backend, ~60 lines frontend.

### 4.5 PWA Support

| Asset | Location | What It Does |
|-------|----------|--------------|
| Service worker | `/public/sw.js` | Currently handles push only — needs caching strategy added |
| Next.js app shell | Standard | App Router already supports static shell |

**New work needed:**
- `manifest.json` in `/public/` with app name, icons, theme color, start URL pointing to couple portal
- Extend `sw.js` with cache-first strategy for static assets + network-first for API calls
- Add `<link rel="manifest">` and meta tags to couple dashboard layout
- Install prompt component in couple dashboard

**Effort: 🔴 Medium** — Manifest is boilerplate, but service worker caching strategy needs careful design to not break the planner-side push behavior.

---

## 5. User Stories

### Couple Stories

**Registry:**
- As a couple, I want to see my wedding registries in the portal so that I can quickly access them without visiting the public wedding page.
- As a couple, I want each registry to show its name and a link to the external registry site so that I can share it with family.

**FAQ:**
- As a couple, I want to see the FAQs my planner has set up so that I can reference the same information guests will see.
- As a couple, I want FAQ entries with links to open in a new tab so that I can access external resources.

**QR Code:**
- As a couple, I want to generate a QR code for my couple portal so that I can share access easily (e.g., screenshot to my partner).
- As a couple, I want to download the QR code as a PNG so that I can save or print it.

**Push Notifications:**
- As a couple, I want to opt in to browser push notifications so that I get alerted when my planner sends updates, messages, or assigns forms.
- As a couple, I want to unsubscribe from push notifications from my dashboard settings so that I can control my notification preferences.

**PWA:**
- As a couple, I want to install the portal as an app on my phone so that I can access it from my home screen without opening a browser.
- As a couple, I want the portal to show cached data when offline so that I can still view my wedding details without internet.

---

## 6. Requirements

### Must-Have (P0) — Ship in Sprint 6

| # | Requirement | Acceptance Criteria |
|---|------------|---------------------|
| S6-1 | **Registry tab** | New "Registry" tab in couple dashboard. Renders `weddingData.wedding.registries` using responsive grid. Each item shows name + colored "View Registry" link opening in new tab. Empty state when no registries. |
| S6-2 | **FAQ tab** | New "FAQ" tab in couple dashboard. Renders `weddingData.wedding.faqs` as card list. Each card shows question (bold), answer, optional external link. Empty state when no FAQs. |
| S6-3 | **QR code widget** | New section in Overview tab or as a standalone utility. Calls `GET /couple-portal/qr-code` → displays QR image + download button. QR encodes the couple portal URL. |
| S6-4 | **QR code API endpoint** | `GET /couple-portal/qr-code` behind `require_couple_auth`. Calls `guest_export_service.generate_qr_code(portal_url)`. Returns `image/png` response. |
| S6-5 | **Couple push subscribe endpoint** | `POST /couple-portal/push/subscribe` behind `require_couple_auth`. Accepts same `SubscribeRequest` model. Calls `web_push_service.save_subscription(couple_email, ...)`. |
| S6-6 | **Couple push unsubscribe endpoint** | `DELETE /couple-portal/push/unsubscribe` behind `require_couple_auth`. Calls `web_push_service.remove_subscription(couple_email, endpoint)`. |
| S6-7 | **Push triggers for couple** | When planner does any of: post update, send message, assign form, schedule/cancel meeting, reply to note → call `web_push_service.send_notification()` targeting the couple's subscriptions. |
| S6-8 | **Push opt-in UI** | Notification bell icon in couple dashboard header. Click → browser permission prompt → on grant, call subscribe endpoint. Visual indicator for active/inactive state. |
| S6-9 | **PWA manifest** | `/public/manifest.json` with `name: "My Wedding Portal"`, `short_name: "Wedding"`, `start_url: "/couple/dashboard"`, `display: "standalone"`, `theme_color`, `background_color`, icons (192px, 512px). |
| S6-10 | **Service worker caching** | Extend `sw.js` with: cache static assets (JS/CSS/images) on install, network-first for API calls with cache fallback, versioned cache names for updates. |
| S6-11 | **PWA install prompt** | "Add to Home Screen" banner/button in couple dashboard. Uses `beforeinstallprompt` event. Dismissable, shows only once per session. |

### Nice-to-Have (P1) — If time allows

| # | Requirement | Notes |
|---|------------|-------|
| S6-P1-1 | **Push notification preferences** | Granular toggles: updates, messages, forms, meetings, notes — stored per couple |
| S6-P1-2 | **Offline indicator** | Show "You're offline — viewing cached data" banner when navigator.onLine is false |
| S6-P1-3 | **QR code in planner view** | Show the couple's QR code on the planner management page for easy sharing |

---

## 7. Technical Implementation Plan

### Phase 1: Registry + FAQ Tabs (Estimated: 30 min)

**Frontend only — zero backend changes.**

1. Add `'registry' | 'faq'` to `TabType` union in couple dashboard
2. Add tab entries with `Gift` and `HelpCircle` icons from lucide-react
3. Create `RegistryTab` component:
   - Read from `weddingData.wedding.registries`
   - Grid layout matching `LandingLayout.tsx` lines 115-135
   - Empty state: gift icon + "No registries have been added yet"
4. Create `FAQTab` component:
   - Read from `weddingData.wedding.faqs`
   - Card layout matching `LandingLayout.tsx` lines 187-210
   - Empty state: help icon + "No FAQs have been added yet"

### Phase 2: QR Code (Estimated: 45 min)

**Backend: 1 new endpoint. Frontend: 1 widget.**

1. Add `GET /couple-portal/qr-code` to `/app/api/couple_portal.py`:
   ```python
   @router.get("/couple-portal/qr-code")
   async def get_couple_qr_code(couple=Depends(require_couple_auth)):
       portal_url = f"{settings.FRONTEND_URL}/couple/login"
       png_bytes = guest_export_service.generate_qr_code(portal_url)
       return Response(content=png_bytes, media_type="image/png")
   ```
2. Add QR section to Overview tab or as separate utility:
   - Fetch QR image as blob → create object URL → render `<img>`
   - Download button triggers `<a download="portal-qr.png">`

### Phase 3: Push Notifications (Estimated: 2-3 hours)

**Backend: 2 new endpoints + trigger wiring. Frontend: permission UI.**

1. Add couple push endpoints to `/app/api/couple_portal.py`:
   - `POST /couple-portal/push/subscribe` — mirrors `/web-push/subscribe` but uses `require_couple_auth`
   - `DELETE /couple-portal/push/unsubscribe` — mirrors `/web-push/unsubscribe`
2. Add push triggers at existing action points:
   - In `post_couple_update()` → push to couple
   - In `send_message()` (planner→couple direction) → push to couple
   - In `share_form_with_couple()` → push to couple
   - In `schedule_meeting()` / `cancel_meeting()` → push to couple
   - In note reply endpoints → push to couple
3. Frontend push subscription manager:
   - Check `Notification.permission` state on mount
   - Bell icon in dashboard header (lucide `Bell` / `BellOff`)
   - On click: request permission → if granted, `pushManager.subscribe()` → POST to couple endpoint
   - Store subscription state in component state

### Phase 4: PWA (Estimated: 1-2 hours)

1. Create `/public/manifest.json`
2. Add `<link rel="manifest" href="/manifest.json">` to couple layout
3. Add meta tags: `theme-color`, `apple-mobile-web-app-capable`, viewport
4. Extend `sw.js`:
   - `install` event: precache app shell (HTML, CSS, JS bundles)
   - `fetch` event: cache-first for static assets, network-first for `/api/` calls
   - `activate` event: clean old caches
   - Preserve existing push handling untouched
5. Install prompt component using `beforeinstallprompt` event

---

## 8. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Registry/FAQ tab usage | 50% of active couples view at least once | Tab click analytics |
| QR code downloads | 30% of couples download QR at least once | Download button click tracking |
| Push notification opt-in rate | 40% of active couples enable push | `push_subscriptions` where user is couple |
| PWA install rate | 20% of couples install PWA | `beforeinstallprompt` outcome tracking |
| Missed planner message rate | 50% reduction vs. pre-push baseline | Time from planner message → couple view |

---

## 9. Open Questions

| # | Question | Owner | Blocking? |
|---|----------|-------|-----------|
| 1 | Should the QR code encode the couple portal login URL or a deep link to the dashboard (requiring existing auth)? | Engineering | No — defaulting to login URL for broadest usefulness |
| 2 | Should PWA manifest `start_url` be `/couple/login` or `/couple/dashboard`? | Engineering | No — defaulting to `/couple/dashboard`, service worker redirects to login if no token |
| 3 | Do we need separate PWA icons or can we reuse existing site icons? | Design | No — using existing icons initially |
| 4 | Should push notification triggers be configurable per-planner (e.g., planner opts out of triggering push on note replies)? | Product | No — shipping all triggers on, P1 for granular control |

---

## 10. Timeline

| Phase | Features | Estimated Effort | Dependencies |
|-------|----------|-----------------|--------------|
| Phase 1 | Registry tab + FAQ tab | 30 min | None — frontend only |
| Phase 2 | QR code (endpoint + widget) | 45 min | Phase 1 (tab structure) |
| Phase 3 | Push notifications | 2-3 hours | None (independent) |
| Phase 4 | PWA manifest + caching | 1-2 hours | Phase 3 (sw.js extension) |
| **Total** | **All 5 features** | **~4-6 hours** | |

All phases can begin independently except Phase 4 depends on Phase 3 (same `sw.js` file).
