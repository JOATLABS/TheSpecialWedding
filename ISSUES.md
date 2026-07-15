# Deferred Issues

This file records verified follow-up issues that are useful to fix but do **not** block the current Phase 1 marketing, product-imagery, or walkthrough-video goal.

An issue belongs here only when:

- the current video can still be recorded, reviewed, and published;
- the platform remains usable and truthful without the fix; and
- deferring it does not weaken the current goal's acceptance evidence.

Anything that blocks a sanitized capture, a current product story, publication, or visible frontend verification stays in the active work instead of being moved here.

## Open

| ID | Area | Verified issue | Why it is deferred |
| --- | --- | --- | --- |
| DI-001 | Guest Memories | The couple Memories page renders the complete active guest-upload URL in the page. A future privacy polish could mask the token by default while preserving Copy link, QR generation, and an intentional reveal action. | The upload workflow works, and the current marketing work can use a safe capture composition without changing product behavior. |
| DI-002 | Public wedding metadata | The Sofia & Daniel browser title says January 24, 2027 while the visible wedding date and event record say January 25, 2027. | The visible wedding experience and the cross-surface 4:00 PM event data are correct, and fullscreen capture does not show the browser title. |
| DI-003 | Video production ergonomics | Manual-capture and playback approval receipts must currently be assembled as JSON by hand; there is no small receipt generator. | The schemas are defined and the receipts can be created manually for this walkthrough. Building a generator would not improve the actual take. |
| DI-004 | Video production ergonomics | The canonical renderer requires narration before it can produce a review export; it cannot create a silent draft through the normal command. | The raw manual recording is directly playable and can be reviewed at normal speed before narration. |
| DI-005 | Video quality assurance | The pipeline does not automatically compare narration duration and cue timing against the authored scene schedule. | The required human normal-speed playback review can detect timing drift for the current export. |
| DI-006 | Capture portability | The manual-capture contract is tied to a 1440×900 raw source, which makes future capture on different displays less convenient. | The current full-window take can be preserved without cropping by fitting the native capture into the required frame. |
| DI-007 | Features-page visual language | The secondary 17-card capability grid uses emoji-led cards and feels more like a feature catalog than the calmer Phase 1 outcome storytelling above it. | The page already leads with the four approved planner outcomes, so this is visual refinement rather than a positioning blocker. |
| DI-008 | Product-image freshness policy | The product-image validator accepts a capture build that is an ancestor of the current build, so approval alone does not prove an image is visually current after later UI changes. | The current goal is recapturing and visually approving the required images; a stricter future freshness policy is useful but not required for those new receipts. |
| DI-009 | Local public vendor directory | The shared local database still contains older non-capture vendor and verifier records, so the public Photography filter can show a second legacy Luna card and unrelated test listings alongside the exact `67c4...001` capture profile. | The isolated capture seed does not own those records and correctly refuses to delete unrelated local data. The current take can use the exact approved profile; a dedicated local capture database or an explicit operator cleanup is a separate environment-hygiene task. |
| DI-010 | Couple portal payment summary | Contract totals currently treat only `succeeded` milestones as paid, even though the canonical lifecycle also treats `paid_externally` as completed; a negative remaining balance is not clamped. | The Phase 1 contract walkthrough uses seeded `succeeded` and scheduled rows, so its visible totals remain truthful. Correcting every completed-payment state is important follow-up work but does not block the current recording. |
| DI-011 | Couple contract access query | The contract-email fallback branch repeats `wedding_id`, so it does not narrow access by the authenticated couple email as intended; the current fake collection also lacks a mismatched-email negative test. | The isolated walkthrough session resolves to the intended Sofia & Daniel wedding and contract. This owner-scope issue needs prioritized security correction after the current capture goal, but it does not alter the seeded recording path. |

## Resolved

Move entries here with the resolving commit and verification evidence after the active Phase 1 goal is complete.
