# Admin Login UX Research Summary

## Research Inputs
- Nielsen Norman Group login guidance highlighting the importance of primary actions, field labels, and transparent error messaging (April 2024 update).
- Google Web.dev sign-in form best practices covering autofill, password managers, and accessible focus states (2023–2024 refresh).
- Apple Human Interface Guidelines for Sign In flows emphasising glass surfaces, clear hierarchies, and biometric-first SSO on mobile (WWDC24 design fundamentals).
- Competitive teardown of Notion, Linear, and Monday.com admin logins across desktop and mobile breakpoints (Jan 2025 product updates).

## Core Principles for 2025-ready Planner Login
1. **Single prominent primary action** – Elevate the fastest, most secure auth path (SSO) while keeping email fallback visually secondary to reduce friction for enterprise tenants.
2. **Glassmorphic clarity** – Use translucent panels, layered light, and softened shadows with 12–16px radii to align with Apple glass fundamentals while maintaining AA contrast ratios.
3. **Inline guidance, not modal errors** – Validate email format and password presence client-side, surface errors within the form, and provide recovery context without navigating away.
4. **Responsive rhythm** – Preserve vertical stacking and ≥48px touch targets below 640px while enabling two-column density on wide viewports.
5. **Security reassurance** – Communicate why SSO is recommended, when sessions persist, and how to escalate provisioning issues.
6. **Low-latency transitions** – Use lightweight gradients and blur utilities instead of heavy images so mobile hardware can render the experience smoothly.

## Mobile-Friendly Comparisons
| Pattern | Mobile Expectation | Desktop Expectation | Notes |
| --- | --- | --- | --- |
| Primary CTA | Full-width button ≥48px tall | Fixed-width or auto with ample padding | Keep label explicit: “Log in to planner portal.” |
| SSO placement | Above keyboard fold with descriptive microcopy | Left-aligned with supporting context | Aligns with biometric-first flows on iOS/Android. |
| Form layout | Single column, stacked labels | Can sit beside supporting copy | Ensure error text wraps without layout shift. |
| Background treatments | Subtle gradients + blur (no parallax) | Can include asymmetrical orbs for depth | Keep GPU cost low for mid-range devices. |
| Help & return links | Inline, thumb reachable | Top-right or footer | Provide escape path back to SaaS marketing site. |

## Implementation Checklist (Mapped to Current Work)
- [x] GlassCard shell with depth="near" and xl blur, plus decorative gradients that respect reduced motion.
- [x] SocialAuthButtons prioritised above email form with mobile-safe spacing.
- [x] Email/password labels, guidance copy, and password toggle that expose state via `aria-pressed`.
- [x] Validation + error messaging living inside the form with `role="alert"` semantics.
- [x] Responsive grid splitting contextual copy from the form on large screens while stacking on mobile.
- [x] Dual-plane glass surface with a diffused center seam to imply separation between narrative and action areas without a hard divider.
- [x] SaaS hero link labelled “Log in to the planner portal” pointing to `/admin/login` with focus-visible treatment.

## Follow-up Opportunities
- Instrument conversion analytics to compare SSO vs. email success by device class.
- Add organisation-specific support contacts once tenant metadata exposes the correct escalation channel.
- Introduce passkey support when the backend surfaces WebAuthn registration endpoints.

## March 2025 Verification Notes
- Confirmed the current `/admin/login` implementation renders the dual-plane glass layout with the animated welcome cloud opposite the authentication panel, matching the checklist above. The layout remains keyboard accessible and Screen Reader text for the animation persists in production builds. [Ref: `app/admin/login/page.tsx` lines 12-188]
- Verified the SaaS landing hero links to the planner portal login without breaking focus order or colour contrast on the hero action row. [Ref: `app/components/saas/SaasHeroSection.tsx` lines 120-171]
- Smoke-tested the responsive behaviour by resizing the viewport; the form collapses beneath the narrative column at <1024px widths while maintaining ≥48px touch targets and 16px body copy, keeping parity with the 2025 guidance from Apple HIG and NN/g login heuristics.
