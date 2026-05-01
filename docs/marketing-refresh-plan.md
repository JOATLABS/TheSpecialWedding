# Marketing Refresh Plan — Surfacing the Complete Workspace

**Status:** Draft, awaiting user approval. No code changes until this doc is signed off.
**Date:** 2026-04-21
**Author:** Claude, working with Etastic
**Source of truth for what's missing:** `/Users/emmanuelakinwale/Desktop/WeddingWebApp/docs/feature-map.html`

---

## 1. Thesis

The landing page today sells 18 planner tools. It does not sell the thing that makes The Special Wedding structurally different from Honeybook, Aisle Planner, or Planning Pod: **everything a wedding needs — the public website, the couple communication channel, the vendor directory, the ad marketplace, the contract portal — lives inside one workspace.** There is no "send them to Squarespace for the wedding site," no "ask them to sign in DocuSign," no "look up a photographer on The Knot." That's the pitch the refreshed marketing needs to carry.

This plan reframes four bundles of shipped-but-unmarketed capability as thesis-aligned landing cards, extends the /features comparison table with the smaller ops-layer features, tightens the top blog post to lead with the thesis, and adds a 5-post feature series that each landing card can deep-link into. Onboarding decks for planner and couple get matching step additions so the in-product experience mirrors the marketing narrative. Vendor onboarding is out of scope for this iteration.

---

## 2. Landing Page — Four New Tier-1 Cards

Each new entry is a `MarketingFeature` appended to `app/data/marketingFeatures.ts`. Shape, tone, and length match the existing 18 entries.

### 2.1 `wedding-website`

```
id: 'wedding-website'
icon: '🌐'
title: 'The Wedding Website, Built In'
category: 'Experience'
image: '/wedding_microsite.png'
tagline: 'Every wedding gets a branded public site with gallery, RSVP, and QR memory uploads — no Squarespace, no The Knot.'
description:
  'Each wedding slug (yourname.thespecialwedding.io/couple) ships as a public microsite with
   the couple's branding, event schedule, gallery, RSVP flow, and guest memory uploads via QR.
   You stop paying for a separate wedding website builder and your couples stop maintaining
   one. All of it is wired to the same guest list, gallery, and RSVP data you already work in.'
ai: false
```

**Why this lands first in Tier 1:** It's the most concrete "no second tool" story and it's visually rich for a screenshot.

### 2.2 `vendor-network`

```
id: 'vendor-network'
icon: '🏛️'
title: 'Your Vendor Network, Inside the Platform'
category: 'Business'
image: '/vendor_network.png'
tagline: 'Source from the public directory, advertise to planners via the ad portal, or collaborate through the contract portal — every vendor path lives here.'
description:
  'The Special Wedding is also a vendor marketplace. Browse photographers, venues, and
   caterers in the public directory, invite contract vendors into token-based workspaces
   for signatures and payments, and let advertising vendors buy CPL campaigns that surface
   leads in your planner inbox. The vendor side of a wedding — discovery, contracting,
   payment, advertising — is not a separate universe anymore.'
ai: false
```

**Card combines three distinct surfaces** (public directory, contract portal, ad portal). The pitch is unified; the detail lives in the matching blog post.

### 2.3 `couple-answers`

```
id: 'couple-answers'
icon: '💬'
title: "Everything Couples Ask, Already Answered"
category: 'Client Experience'
image: '/couple_registry_faqs.png'
tagline: "Registry, FAQs, meeting scheduler, memory wall, push notifications — so couples stop texting you the same five questions."
description:
  "The couple portal answers itself. Registry URLs, FAQ entries the couple maintains, a
   meeting scheduler for check-ins, a QR memory wall for guest photos, and real-time push
   notifications when anything changes. You stop being the human API between your couple
   and their plan, and they stop feeling out of the loop."
ai: false
```

**Rationale for bundling:** All five sub-features share the "couples self-serve" frame. Splitting them would produce five weak cards.

### 2.4 `real-time`

```
id: 'real-time'
icon: '⚡'
title: 'Real-Time Planning, Not Email Tag'
category: 'Operations'
image: '/realtime_updates.png'
tagline: 'Changes appear instantly, every action is logged, and inbound emails thread straight into the planner inbox.'
description:
  'Server-sent events push updates to the couple portal the moment you save them — no
   refresh, no "did you get my email." An activity audit log captures every write so your
   team can trace who changed what. Inbound emails forwarded to your wedding address
   automatically thread into the planner inbox against the right couple. Planning stops
   being a sync-every-morning operation.'
ai: false
```

**Category `Operations`** mirrors existing Dashboard/Analytics/Team entries.

### 2.5 Ordering in `MARKETING_FEATURES`

Insert in this order, between existing `couple-portal` (index 1) and the rest:

1. dashboard *(existing)*
2. **wedding-website** *(new)*
3. couple-portal *(existing, reshape tagline — see 2.6)*
4. **couple-answers** *(new)*
5. guests *(existing)*
6. seating *(existing)*
7. reminders *(existing)*
8. **real-time** *(new)*
9. contracts *(existing)*
10. packages *(existing)*
11. **vendor-network** *(new)*
12. vendors *(existing — rename to "Vendor CRM (Planner Side)" to disambiguate from vendor-network)*
13. …rest unchanged

### 2.6 Existing cards requiring light edits

**`couple-portal`** tagline today says "timeline, payments, forms, messages, memories, registry, and FAQs." Since registry/FAQs get their own card now, the couple-portal tagline should refocus on portal-as-communication-hub: *"Give each couple a dedicated login where the whole wedding conversation lives."*

**`vendors`** (Vendor CRM) should be renamed to **"Vendor CRM (Planner Side)"** and its description tweaked to clarify it's the planner's private vendor rolodex, distinct from the public directory in `vendor-network`.

**`gallery`** description references QR memory uploads — keep, but cross-link implicitly to the wedding-website card in body copy.

No other existing cards change.

---

## 3. /features — Comparison Table Additions

Append to the `comparison` array in `app/features/page.tsx`. Competitor-state calls below follow the same `true | 'adjacent' | false` three-state convention. Ambiguous rows are flagged with `⚠ REVIEW` — those need user sign-off before we ship.

| Feature | You | Honeybook | Aisle Planner | Planning Pod | Confidence |
|---|---|---|---|---|---|
| Built-In Wedding Microsite | true | false | adjacent | false | confirmed — Aisle Planner has a "wedding website" add-on |
| Public Vendor Directory | true | false | false | false | confirmed |
| Contract Vendor Portal (token-based) | true | adjacent | false | false | Honeybook has vendor-adjacent collab, not token portals |
| Vendor Advertising Portal (CPL) | true | false | false | false | confirmed |
| Real-Time Couple Notifications (SSE + Push) | true | adjacent | false | false | Honeybook has some push, not SSE-driven |
| Couple-Managed Registry | true | false | adjacent | false | ⚠ REVIEW — Aisle Planner may expose registry links in couple portal |
| Couple-Managed FAQs | true | false | false | false | confirmed |
| Meeting Scheduler (couple-side) | true | adjacent | false | adjacent | Honeybook + Planning Pod have scheduling add-ons |
| Guest Memory QR Wall | true | false | false | false | confirmed |
| Plus-Ones Management | true | adjacent | true | adjacent | ⚠ REVIEW |
| AI Quote Comparison | true | false | false | false | confirmed |
| Budget Templates | true | false | adjacent | adjacent | ⚠ REVIEW |
| CSV / Google Sheets Imports | true | true | true | adjacent | confirmed |
| OTP-Verified Guest Access | true | false | false | false | confirmed |
| Inbound Email Threading | true | adjacent | false | false | Honeybook has inbound-to-project |
| Activity Audit Log | true | adjacent | false | adjacent | ⚠ REVIEW |
| In-App Support Desk | true | false | false | false | confirmed |

**Three rows flagged for user review** — decide before merge. I will not guess.

Existing 17 rows are untouched.

---

## 4. Blog Series

### 4.1 Modify existing top post — `introducing-the-special-wedding`

**What changes:** opening three paragraphs. Today the post frames the pitch as "stop juggling 8+ tools." That's close but narrow. The refreshed open leads with the **surfaces** — wedding website, couple channel, vendor directory, ad marketplace, contract portal — and makes the "one workspace" claim via surface completeness rather than tool count. The rest of the post stays.

**New opening draft** (to replace current lines 27–52 of `data.tsx`):

> If you're a professional wedding planner, the painful part isn't software cost — it's **surface sprawl.** The wedding website lives on Squarespace. The couple channel lives in text threads and email. The vendor directory is a pinterest board and three browser bookmarks. The contract portal is DocuSign. The ad budget goes to The Knot. Your actual planning tool is tool number six.
>
> The Special Wedding is built on a single idea: **every surface a wedding needs already lives in one workspace.** The couple has a branded public microsite at your-couple.thespecialwedding.io. They have a private portal for messages, registry, FAQs, payments, and forms. Your vendors live in a public directory and — when contracted — in token-based portals that handle signatures and payments. Advertising vendors pay you for leads. Your team operates from one planner dashboard wired to all of it.
>
> Most platforms you're familiar with rebuilt the planner dashboard. We rebuilt everything the planner used to stitch together.
>
> (Rest of existing post continues from "Most wedding management platforms were built as generalist tools...")

**Rationale:** Keeps the working "tools are retrofitted" argument but prepends the surface-completeness thesis so the new blog series has somewhere to hook into.

### 4.2 New feature-series posts (5 posts)

Each follows the existing `BlogPost` shape in `data.tsx`. Structure per post: ~1000 words, 3–4 `<h3>` sections, outbound CTA at the end linking to the matching landing card or in-app surface. Dates stagger across May 2026 so the series reads as a planned drop.

---

**Post 1 — `the-built-in-wedding-website`**

| Field | Value |
|---|---|
| title | "Stop Sending Couples to Squarespace: The Built-In Wedding Website" |
| excerpt | "Every wedding on The Special Wedding gets a public microsite with gallery, RSVP, and QR memory uploads — wired to the same data you plan from." |
| category | 'Product' |
| date | '2026-05-05' |
| readTime | 6 |
| ogDescription | "The wedding website is built in. Branded, connected to RSVP and gallery, with QR memory uploads. No Squarespace, no The Knot." |

**Section outline:**
- *The separate-website tax* — planners currently spend $12–$24/mo per wedding on a second tool; couples see a disconnected experience.
- *What every microsite ships with* — slug, event schedule, theme/branding, gallery, RSVP, QR memory wall, privacy controls.
- *The data connection* — guest list drives RSVP, gallery is the same gallery you manage, memories flow into moderation before publish.
- *CTA* — deep-link to the new `wedding-website` landing card.

---

**Post 2 — `your-vendor-network-inside-the-platform`**

| Field | Value |
|---|---|
| title | "Your Vendor Network Lives Inside Your Platform" |
| excerpt | "Public directory, token-based contract portals, and a CPL ad marketplace — The Special Wedding is also where vendors work." |
| category | 'Product' |
| date | '2026-05-12' |
| readTime | 8 |
| ogDescription | "Vendors don't need a separate tool. The directory, the contract portal, and the ad marketplace all live inside The Special Wedding." |

**Section outline:**
- *Three vendor roles, one platform* — public-directory vendor, contract vendor, advertising vendor.
- *The public directory* — browseable by couples and planners; SEO entry for new vendors.
- *Contract vendor portal* — `/portal/[token]` flow; signature + form intake + payment without DocuSign.
- *Advertising portal* — vendors pay CPL to surface leads; planners earn referral revenue.
- *CTA* — landing card deep-link plus "vendor signup" link.

---

**Post 3 — `why-your-couples-stop-texting-you`**

| Field | Value |
|---|---|
| title | "Why Your Couples Stop Texting You" |
| excerpt | "Registry, FAQs, meetings, memory wall, push notifications — the couple portal answers itself so you stop being the human API." |
| category | 'Client Experience' |
| date | '2026-05-19' |
| readTime | 7 |
| ogDescription | "Couples manage their own registry, FAQs, and meeting schedule inside the portal, with push notifications when anything changes." |

**Section outline:**
- *The five questions you answer every week* — "where's the registry?", "when's the rehearsal?", "who's our photographer?", "can my mom join the tasting?", "when's our next check-in?".
- *How the portal answers each* — registry CRUD, FAQ CRUD, contract view, meeting scheduler, push notifications.
- *The memory wall* — guests upload via QR, couple moderates, nothing goes live without approval.
- *CTA* — landing card deep-link.

---

**Post 4 — `real-time-planning-not-email-tag`**

| Field | Value |
|---|---|
| title | "Real-Time Planning, Not Email Tag" |
| excerpt | "SSE updates, audit logs, and inbound email threading make planning a live system instead of a nightly reconciliation job." |
| category | 'Operations' |
| date | '2026-05-26' |
| readTime | 6 |
| ogDescription | "Real-time updates, full audit log, and inbound email threading — the platform stays live while you work." |

**Section outline:**
- *The refresh-and-hope problem* — why most planning tools feel like nightly batch jobs.
- *SSE in the couple portal* — changes appear instantly.
- *The audit log* — every write recorded, filterable by who/what/when.
- *Inbound email threading* — how `inbound_email_service` routes forwards to the right wedding.
- *CTA* — landing card deep-link.

---

**Post 5 — `the-ops-layer-nobody-sees`**

| Field | Value |
|---|---|
| title | "The Ops Layer Nobody Sees (But Every Wedding Relies On)" |
| excerpt | "Imports, OTP-verified guest access, support desk, plus-ones, AI quote comparison, budget templates — the plumbing that makes the platform trustworthy." |
| category | 'Product' |
| date | '2026-06-02' |
| readTime | 9 |
| ogDescription | "The ops layer: imports, OTP, support desk, plus-ones, AI quote comparison, and budget templates. Unglamorous, essential." |

**Section outline:**
- *What "reliable" means for a platform handling someone's wedding* — the stakes of a bug.
- *Import tooling* — CSV/Sheets into guests, vendors, budgets.
- *OTP-verified guest access* — how sensitive guest actions are gated.
- *Support desk* — tickets in-platform, not a support email address.
- *AI quote comparison* — the `/admin/budget/quotes` feature.
- *Budget templates, plus-ones, and the small things* — a sweep of Tier-2 features that add up.
- *CTA* — /features link.

---

### 4.3 Cross-links from landing cards into blog

The landing page doesn't currently deep-link individual cards into blog posts. Two options:

- **Minimal:** add a "Read the story →" link beneath each Tier-1 card that links to the matching blog slug.
- **Richer:** add a slug field to `MarketingFeature` and render the link only when present.

Recommend the richer option since the 18 existing cards don't need a link — the slug field stays `undefined` for them. Small code touch, big narrative payoff.

---

## 5. Onboarding Decks

### 5.1 Planner — `ONBOARDING_STEPS` (`app/admin/components/OnboardingModal.tsx`)

**Append two new steps** before the final `ready` step (i.e., insert between `support` and `ready`). Shape matches existing entries.

**Step A: Grow via Vendor Partnerships**

```
id: 'vendor-network'
title: 'Grow Through Your Vendor Network'
description: 'The platform is also a vendor marketplace. Vendors you already work with can sign contracts in their own portal, and vendors you don't know yet show up in the public directory. Advertising vendors can even surface leads straight into your inbox.'
icon: <Megaphone className="w-12 h-12 text-orange-500" />
features: [
  'Invite contract vendors into their own portal for signatures and payment',
  'Browse the public vendor directory when you need a new supplier',
  'Earn referrals from advertising vendors who buy leads on the platform',
  'Keep every vendor interaction tied to the wedding record'
]
```

**Step B: Stay in Real-Time Sync**

```
id: 'real-time'
title: 'Everyone Stays in Sync, Automatically'
description: 'The couple portal updates live when you save changes — no refresh, no forwarded emails. Every action is audit-logged for your team, and inbound email forwards thread into the planner inbox against the right couple.'
icon: <Zap className="w-12 h-12 text-yellow-400" />
features: [
  'Changes appear in the couple portal the moment you save',
  'Full audit log of every team action, filterable by planner',
  'Inbound emails route to the right wedding automatically',
  'Stop relying on nightly catch-up emails'
]
```

**New icon imports required:** `Megaphone`, `Zap` from `lucide-react`.

### 5.2 Couple — `COUPLE_ONBOARDING_STEPS` (`app/couple/components/CoupleOnboardingModal.tsx`)

The existing `extras` step already covers registry/FAQ/push at surface level. Two options:

- **Option A (minimum touch):** expand the existing `extras` step description and features list to call out memory wall + meetings more explicitly.
- **Option B (clearer narrative):** split `extras` into two steps — `self-serve` (registry + FAQ + meetings) and `stay-informed` (push notifications + memory wall).

Recommend **Option B** because it lets the deck mirror the landing-page card (`couple-answers`) and the blog post (Post 3). Copy:

**Replacement for current `extras` step:**

```
id: 'self-serve'
title: 'Your Registry, FAQs & Check-Ins'
description: 'Keep the questions your guests and family ask in one place. You own the content — update registry links, FAQ entries, and meeting times whenever plans shift.'
icon: <Gift className="w-12 h-12 text-pink-500" />
features: [
  'Manage registry URLs and gift wishlist in the portal',
  'Update shared FAQs your guests can reference',
  'Schedule meetings with your planner when you need face time',
  'Every change is visible to your planner immediately'
]
```

**New step added after it:**

```
id: 'stay-informed'
title: 'Get Pinged, Not Pestered'
description: 'Turn on browser notifications and the portal tells you when anything changes. Guests can upload photos to a moderated memory wall via QR code. You review everything before it goes live.'
icon: <BellRing className="w-12 h-12 text-cyan-500" />
features: [
  'Browser push notifications for messages and updates',
  'QR-code memory wall for guest photos',
  'Private review queue before anything goes public',
  'Save the portal to your phone for fast access'
]
```

**No new icon imports required** — `BellRing` and `Gift` already imported.

Vendor onboarding deck is explicitly out of scope for this iteration.

---

## 6. Screenshots — Capture Plan

Target six screenshots for the four new Tier-1 cards plus two reshape-candidates. Captured live via Claude in Chrome with Etastic watching.

| Filename | Source route | Fixtures needed | Notes |
|---|---|---|---|
| `/public/wedding_microsite.png` | `/[slug]` on a seeded couple | Branded wedding with schedule, at least one event, some gallery photos, RSVP visible | Hero shot of the public microsite. Scroll to show event schedule. |
| `/public/vendor_network.png` | `/vendors` list view | 6+ vendors, mixed categories, at least one with photos | Grid view of public directory. May crop to show "Browse" filter. |
| `/public/couple_registry_faqs.png` | `/couple/dashboard` → Registry + FAQ sections | Couple account with 2+ registry entries and 3+ FAQs populated | Composite shot — may need to crop two panels. |
| `/public/realtime_updates.png` | Couple portal + planner activity log side-by-side | Recent activity entries, any open SSE notification toast | Harder shot. Fallback: just the audit log view from `/admin/planner/activity-log`. |
| `/public/couple_portal_dashboard.png` | existing | — | Keep existing image; tagline change doesn't require new shot. |
| `/public/vendor_management.png` | existing | — | Keep existing. Renamed card still uses the same screenshot. |

**Session logistics:**
1. Planner login (`okpoko.peace@gmail.com`) — capture microsite, vendor directory, audit log.
2. Couple login (pending password) — capture registry/FAQ composite.
3. Image post-processing: resize to match existing aspect ratios (~1600×1000 for dashboard shots).

If staging lacks data for any shot (e.g., no populated registry on the test couple), we seed it during the session before capturing.

---

## 7. Sequencing

1. **Today:** this spec doc goes to Etastic for review.
2. **After approval:** address the three ⚠ REVIEW rows in the comparison table; confirm Option B for couple onboarding; confirm richer-link option for landing→blog cross-links.
3. **Screenshot session:** live Chrome with user, capture 4 new images.
4. **Implementation pass 1:** `marketingFeatures.ts` + tagline/rename edits.
5. **Implementation pass 2:** comparison table additions in `app/features/page.tsx`.
6. **Implementation pass 3:** modify top blog post, add 5 new posts to `data.tsx`.
7. **Implementation pass 4:** planner onboarding additions.
8. **Implementation pass 5:** couple onboarding split.
9. **Verification:** live Chrome walkthrough of landing page, /features, all 6 blog URLs, planner onboarding trigger, couple onboarding trigger. Console clean, no 404s, no missing images.

---

## 8. Decisions Needed From Etastic

1. **Comparison table rows flagged ⚠ REVIEW** — Registry, Plus-Ones, Budget Templates, Audit Log. Confirm the competitor-state calls or tell me to research deeper.
2. **Couple onboarding** — Option A (expand existing `extras` step) or Option B (split into `self-serve` + `stay-informed`)?
3. **Landing card → blog deep-link** — minimal "Read the story" link or richer optional `slug` field on `MarketingFeature`?
4. **Card order in `MARKETING_FEATURES`** — confirm the proposed insertion order in section 2.5, or re-sequence?
5. **Renaming `vendors` card to "Vendor CRM (Planner Side)"** — approve or keep "Vendor CRM" and rely on description alone to disambiguate?
6. **Blog post dates** — I proposed staggered weekly drops through May into early June. Confirm or shift.

---

## 9. Out of Scope (Explicit)

- Vendor onboarding deck (Etastic's call, not building this iteration).
- Tier-3 internal features (SaaS super-admin, scraper, behavioral analytics, test-clock billing, team-member subscription gate) — not marketed.
- Pricing-page updates — this plan touches marketing surfaces only; pricing tiers remain as-is.
- SEO metadata beyond the `ogDescription` field already present on each blog post.
- A/B testing infrastructure for the new landing cards.
