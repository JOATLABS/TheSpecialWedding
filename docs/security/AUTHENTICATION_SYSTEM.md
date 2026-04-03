# Authentication System Documentation

## Overview

The Special Wedding platform uses a cookie-backed authentication model for the shared back-office surface under `/admin` and related portals. Sensitive JWTs are stored in secure `httpOnly` cookies, while the frontend keeps only an in-memory access token for active API calls and refreshes it through the backend when needed.

This replaced the older two-cookie plus browser-storage pattern. If you see references to `admin_authenticated`, `localStorage` token persistence, or `sessionStorage` token persistence, treat them as legacy cleanup history, not current architecture.

## Roles

Back-office authentication currently supports these roles:

- `ROOT_ADMIN`: platform owner and system administrator
- `wedding_planner`: primary planner/customer account
- `team_member`: scoped planner staff account
- `vendor`: legacy vendor role inside the main platform
- `advertising_vendor`: vendor ads portal role

Couples authenticate through the separate couple auth system and are not part of the shared `/admin` role surface.

Role flags are derived in [auth_extended.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/dependencies/auth_extended.py) and exposed through [admin_auth.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/admin_auth.py).

## Current Session Model

### 1. Secure auth cookie

- Cookie name: `admin_token`
- Type: `httpOnly`
- Purpose: source of truth for authenticated backend and middleware access
- Accessibility: not readable by JavaScript
- Set by: [admin_auth.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/admin_auth.py)

### 2. In-memory access token

- Stored only on `window` for the active browser session
- Purpose: populate `Authorization: Bearer ...` headers for existing frontend API clients
- Source: login response or refresh response
- Persistence: not written to `localStorage` or `sessionStorage`

### 3. Legacy storage cleanup

The frontend proactively removes old storage keys such as `admin_token`, `couple_token`, and vendor ad storage keys during bootstrap/logout so older sessions cannot silently revive deprecated auth paths.

## Request Flow

### Login

1. The client submits credentials to `POST /admin/token`.
2. The backend validates the user and role.
3. The backend sets the `admin_token` `httpOnly` cookie.
4. The response body returns an access token payload for immediate in-memory client use.

### Session restore / refresh

1. On app bootstrap, the frontend checks for an in-memory token.
2. If it does not have one, it calls `POST /admin/token/refresh` with `credentials: include`.
3. The backend authenticates from the `admin_token` cookie and returns a fresh short-lived token.
4. The client stores that token only in memory.

### Logout

1. The client calls `POST /admin/logout`.
2. The backend clears the `admin_token` cookie.
3. The frontend clears in-memory auth state and legacy browser-storage keys.

## Security Properties

### What improved

- No active JWT persistence in `localStorage`
- No active JWT persistence in `sessionStorage`
- No client-readable auth-state cookie required
- Better resistance to token theft via straightforward XSS

### What still matters

- Any XSS in an authenticated page can still act as the user while the page is open
- Frontend code still uses bearer headers for some calls, so memory-resident tokens remain sensitive during an active session
- Cookie security still depends on correct production `secure`, `samesite`, and domain configuration

## Couple Auth

Couple auth is separate from the back-office flow:

- Cookie name: `couple_token`
- Login/setup endpoints live in [couple_auth.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/couple_auth.py)
- Cookie validation lives in [couple_auth.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/dependencies/couple_auth.py)

Couple sessions also clear legacy `localStorage` keys during logout/bootstrap.

## Vendor Ads Portal Auth

The ads portal reuses the shared admin auth backend and allows only:

- `ROOT_ADMIN`
- `advertising_vendor`

Its layout clears legacy `vendor_ad_*` browser storage keys and then bootstraps from the shared secure cookie flow.

## Files To Know

- Backend auth routes: [app/api/admin_auth.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/admin_auth.py)
- Shared auth dependency: [app/dependencies/auth_extended.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/dependencies/auth_extended.py)
- Admin token bootstrap/cleanup: [app/utils/adminAuthStorage.ts](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/utils/adminAuthStorage.ts)
- Couple auth helper: [app/couple/lib/auth.ts](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/couple/lib/auth.ts)
- Vendor ads layout bootstrap: [app/portal/ads/layout.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/portal/ads/layout.tsx)

## QA Checks

Use these checks after auth changes:

1. Log in as `ROOT_ADMIN`, `wedding_planner`, and `advertising_vendor`.
2. Refresh the page and confirm the session restores correctly.
3. Log out and confirm protected routes redirect appropriately.
4. Confirm `localStorage.getItem('admin_token')` and `sessionStorage.getItem('admin_token')` are `null`.
5. Confirm `document.cookie` does not expose readable auth-state cookies such as `admin_authenticated`.
6. Repeat the same storage checks for couple and vendor legacy keys.

## Known Constraints

- The frontend still relies on short-lived bearer tokens in memory for existing API-client patterns.
- Some older docs and review artifacts may still mention the retired two-cookie/browser-storage approach; they should not be treated as current behavior.
