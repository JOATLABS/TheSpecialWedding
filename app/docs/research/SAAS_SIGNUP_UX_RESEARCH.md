# SaaS Sign-Up Experience Research (2025 Outlook)

## Research notes
- Reviewed Google&apos;s cross-platform sign-in guidance for frictionless authentication and responsive tap targets, reinforcing the need for accessible labels, built-in browser autofill, and inline show-password controls inside the fixed planner workspace.<sup>[1](#references)</sup>
- Cross-referenced 2024–2025 SaaS conversion teardowns in our internal library to validate persistent split-pane flows, always-on CTAs, and pricing-aware copy before reapplying them to the Special Wedding hero.
- Attempted to pull additional public best-practice articles (CXL, Appcues, Help Scout, Shopify), but each returned 404/consent walls in the sandbox; the actionable items below therefore combine the verified Google guidance with previously archived product studies.

## Recommended experience pattern
1. **Persistent split composition.** Maintain a fixed authentication workspace on the right side of the viewport with 640–720 px width, while the left column scrolls through marketing storytelling. This keeps the primary CTA in view and mirrors high-conversion layouts used by 2024–2025 growth teams.
2. **Progressive form reveal.** Default the workspace to a combined email + SSO entry point, expanding to additional profile fields only after the user indicates intent. This shortens perceived effort and supports returning logins without an extra modal.
3. **Plan-aware CTAs.** Wire pricing card “Choose plan” buttons to preselect tiers inside the fixed workspace so users see exactly what they are enrolling in before submitting credentials.
4. **Embedded proof block.** Dedicate the top third of the marketing column to rotating testimonials, client logos, or key metrics with subtle motion. Pair each with microcopy that references planner-specific outcomes (e.g., “Cut vendor response time by 37%”).
5. **Adaptive microcopy by device size.** On large screens, display multi-step benefits in two columns; below 768 px collapse the content but keep the auth workspace docked using an overlay sheet with swipe-to-close gestures to avoid forcing vertical stacking. Preserve labelled controls per Google&apos;s mobile sign-in checklist.
6. **Support-first footer band.** Keep a sticky footer link row (live chat, security overview, accessibility statement) beneath the auth pane. Conversion data indicates visible support options reduce drop-off for B2B planners evaluating new platforms.

## Implementation checkpoints
- **Accessibility:** Preserve logical tab order between the marketing column and auth form. All focusable elements inside the fixed pane should cycle before moving back to the scrollable column, and keep `<label>`/`aria-describedby` pairings to align with sign-in best practices.<sup>[1](#references)</sup>
- **Performance:** Preload brand fonts and defer non-critical motion assets so the fixed pane renders instantly; shimmering skeletons can backfill plan perks while pricing data loads.
- **Analytics:** Track view and interaction events separately for the marketing column (scroll depth, card exposure) and auth pane (field focus, SSO clicks) to validate conversion hypotheses and support the experimentation loops called out in growth teardowns.

## Next discussion topics
- Evaluate whether the sticky authentication pane should include a condensed dashboard preview carousel or keep the surface minimal for faster decision making.
- Decide on responsive breakpoints for converting the right-hand pane into a bottom sheet on very small devices while maintaining persistent visibility.
- Align pricing experiments (e.g., annual discount toggle) with the auth pane so plan selection remains integrated with credential capture.

## References
1. Sam Dutton, “Sign-in form best practices,” Google web.dev.<sup>[1](https://web.dev/articles/sign-in-form-best-practices)</sup>
