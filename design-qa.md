# Public Microsite Footer — Design QA

## Source truth

- Selected concept: `/Users/emmanuelakinwale/.codex/generated_images/019f7d3d-ee13-7363-aebc-f4ad4c528158/exec-06d03e7e-4d69-4358-82f4-88f5f65f8300.png`
- Source dimensions: 853 × 1844 px. The selected reference is the compact footer at the bottom of the concept.
- Product constraints: attribution must feel like part of the couple's site, remain theme-aware, use the real The Special Wedding lockup, link to the marketing site, and add no popup, CTA, tagline, or advertising module.

## Browser evidence

- Couple microsite context: `output/footer-design-qa/microsite-mobile-footer-context.png`
- Couple microsite focused footer: `output/footer-design-qa/microsite-mobile-footer-focused.png`
- Gallery route context: `output/footer-design-qa/gallery-mobile-footer-context.png`
- Side-by-side source/implementation comparison: `output/footer-design-qa/footer-reference-vs-implementation.png`
- QA viewport: 390 × 844 CSS px at device scale factor 1.
- Focused comparison: source footer normalized to 390 × 74 px; implementation footer is 390 × 86 px. The 12 px increase preserves 44 px touch targets for the brand and legal controls.
- State: dark Sofia & Daniel microsite, themed olive/gold brand treatment, footer placed after the couple content and before the infinite-scroll cycle repeats.

## Fidelity review

| Surface | Result |
| --- | --- |
| Typography | Passed. Uses the canonical product wordmark rather than recreating the approximate mock typography. Legal and copyright text retain the restrained, editorial scale of the reference. |
| Spacing and layout | Passed. Shallow full-width bar, brand left, legal/copyright right, with mobile-safe spacing and no extra promotional copy. |
| Colors and tokens | Passed. The black translucent surface matches the reference hierarchy; logo and legal accents consume the configured wedding theme variables with safe fallbacks. |
| Image and logo fidelity | Passed. Uses the repository's canonical ring-and-heart SVG lockup with unique gradient IDs for primary and cloned renders. |
| Copy | Passed. Only `Privacy`, `Terms`, and the year accompany the product name. No `Created with`, sales CTA, tagline, or ad language was introduced. |

## Interaction and responsive checks

- The primary brand link opens `https://thespecialwedding.io/` in a new tab with microsite referral UTMs, `noopener noreferrer`, and `no-referrer`.
- Referral data contains no slug, guest identifier, invitation token, email, phone, or wedding ID. The analytics event records only `{ location: "footer" }`.
- Landing-page Privacy and Terms controls open the existing legal modals; no new popup or modal was added.
- Gallery Privacy and Terms links resolve to the public legal routes.
- The infinite-scroll clone has no footer ID and no focusable links or buttons, leaving one interactive attribution per page.
- Landing and gallery routes both render at 390 px with `scrollWidth === innerWidth`; no horizontal overflow.
- Fresh, database-stable loads of the landing and gallery routes produced no browser console errors.

## Comparison history

- Pass 1: no actionable P0, P1, or P2 visual drift found.
- Intentional difference: the reference's generic cream logo treatment becomes the couple-configured theme treatment, as required.
- Intentional difference: the approximate mock logo is replaced by the exact platform lockup.
- Intentional difference: the implementation is slightly taller to preserve accessible touch targets.
- Remaining P3 observation: the canonical wordmark reads slightly smaller than the approximate source lockup, but remains legible and appropriately subtle; enlarging it would push the footer toward ad-like prominence.

## Hostile review

- Tenant and authorization boundaries are unchanged; the footer receives only already-public theme state.
- Both public display surfaces use the same component, so gallery and landing behavior cannot drift independently.
- Marketing attribution does not expose guest or wedding data through the URL, referrer, or analytics payload.
- Duplicate IDs and duplicate keyboard targets are prevented in the infinite-scroll clone.
- The implementation does not alter RSVP, guest verification, legal-modal, or gallery lifecycles.

final result: passed
