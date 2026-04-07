# Competitor Comparison Verification

Research date: April 6, 2026

Scope: verify every comparison-table row in `app/features/page.tsx` plus the pricing row, using primary sources only from HoneyBook, Aisle Planner, and Planning Pod.

## Method

- I used only official competitor sites, help centers, and product pages.
- I treated official blog/comparison posts as primary sources when they were published by the competitor itself.
- I marked rows as `Confirmed`, `Adjacent`, or `Not found` instead of forcing false certainty.
- `Adjacent` means the competitor has a close capability, but not the exact wording or workflow in the comparison row.

## Source Key

- `HB1` HoneyBook pricing: https://www.honeybook.com/pricing
- `HB2` HoneyBook client portal / smart files: https://help.honeybook.com/en/articles/4394789-set-a-custom-domain-for-your-client-portal-and-smart-files
- `HB3` HoneyBook contact workspace: https://help.honeybook.com/en/articles/7942562-find-and-use-the-contact-workspace
- `HB4` HoneyBook communication, scheduling, automations: https://help.honeybook.com/en/articles/2209147-communicating-through-honeybook
- `HB5` HoneyBook event planner page: https://www.honeybook.com/software-for-event-planners
- `HB6` HoneyBook invoice/payment page: https://www.honeybook.com/free-invoice-maker
- `AP1` Aisle Planner pricing: https://www.aisleplanner.com/pricing
- `AP2` Aisle Planner guest list download: https://help.aisleplanner.com/en/articles/2130230-downloading-your-guest-list
- `AP3` Aisle Planner layout canvas seating: https://help.aisleplanner.com/en/articles/2887342-viewing-guest-names-seat-numbers-meal-selections-on-your-layout-canvas
- `AP4` Aisle Planner wedding website / QR RSVP: https://help.aisleplanner.com/en/articles/2013039-how-to-create-an-event-or-wedding-website-in-aisle-planner
- `AP5` Aisle Planner calendar sync: https://help.aisleplanner.com/en/articles/10375834-ap-connect
- `AP6` Aisle Planner integrated account calendar: https://help.aisleplanner.com/en/articles/11786770-ap-connect-integrated-account-calendar
- `AP7` Aisle Planner lead contact forms: https://help.aisleplanner.com/en/articles/2210385-setting-up-your-lead-contact-form
- `AP8` Aisle Planner contract / proposal lifecycle: https://help.aisleplanner.com/en/articles/3128743-voiding-a-proposal-or-contract
- `AP9` Aisle Planner platform fees / online payments: https://help.aisleplanner.com/en/articles/3706461-platform-fees-offsetting-service-related-costs

- `PP1` Planning Pod email and communications: https://planningpod.com/email-and-communications
- `PP2` Planning Pod pricing and feature comparison article: https://planningpod.com/blog/tripleseat-vs-caterease-vs-planning-pod-venue-management-software-competitors-pricing

## Verified Pricing And Major Corrections

- HoneyBook current public starting price is `Plans start as low as $29/mo` on the pricing page. The same pricing page also shows `SMS reminders`, `Automations`, `Up to 2 team members`, `Client portal`, and `HoneyBook AI` on its paid tiers.
- Aisle Planner current public entry price is `Sales Essentials $49.99 / Mo` with a free 30-day trial, plus higher project-based tiers that include `Lead Management`, `Automated Email Responses`, `Budgets`, `Guest Management & Messaging`, `Layouts & Seating`, `Event Website & Online RSVP`, and `Unlimited Users`.
- Planning Pod’s official comparison article states prices start at `$149/month (paid yearly)`.
- The audit report’s `HoneyBook $32.50/mo` and `Aisle Planner $30-70/mo` shorthand is not the clearest public pricing presentation. Use the official entry-plan language above when publishing.

## Comparison Matrix

| Feature row | The Special Wedding claim | HoneyBook status | Aisle Planner status | Planning Pod status | Evidence / source URLs | Confidence |
|---|---|---|---|---|---|---|
| Guest Management & RSVPs | `Yes` | `Adjacent` - contact/workspace management exists, but no explicit guest manager or RSVP flow | `Confirmed` - guest list, RSVP summary, seat/meal tracking | `Confirmed` - guest lists, registrations, ticketing | `HB3`, `HB4`; `AP2`, `AP3`; `PP2` | High |
| Couple Portal (dashboard, inbox, payments) | `Yes` | `Adjacent` - client portal + contact workspace + payments, but not a wedding-couple portal | `Adjacent` - client portal + dashboard + guest messaging, but not a dedicated couple portal | `Not found` - closest is centralized inbox and event webpages | `HB2`, `HB3`, `HB4`; `AP1`, `AP4`; `PP1`, `PP2` | High |
| SMS & Email Reminders with Fallback | `Yes` | `Adjacent` - SMS reminders and automations exist, but the fallback part is not source-backed | `Adjacent` - automated email responses and reminders exist, but SMS evidence is not explicit | `Adjacent` - automated email/text reminders exist, but fallback logic is not explicit | `HB1`, `HB4`; `AP1`, `AP5`, `AP6`; `PP1`, `PP2` | Medium |
| Seating Charts with AI Suggestions | `Yes` | `Not found` | `Adjacent` - strong seating/layout tools, no AI suggestions | `Adjacent` - floor plan / layout tools, no AI suggestions | `AP3`, `AP1`; `PP2` | High |
| AI Contract Generation & E-Sign | `Yes` | `Adjacent` - contracts/e-sign exist and HoneyBook AI exists, but no explicit AI contract generator found | `Adjacent` - contracts and e-signatures exist, but no AI contract generation | `Adjacent` - contracts/e-sign exist, but no AI contract generation | `HB1`, `HB5`; `AP1`, `AP8`; `PP2` | Medium |
| AI Pricing & Package Builder | `Yes` | `Adjacent` - AI exists, and lead/forms/pricing workflows exist, but no explicit package builder found | `Not found` | `Adjacent` - proposals/packages exist, but no AI pricing builder found | `HB1`, `HB5`; `AP1`, `AP7`; `PP2` | Medium |
| AI Cash Flow Predictions | `Yes` | `Not found` - finance tools exist, but no explicit forecasting/prediction feature found | `Not found` | `Not found` | `HB1`, `HB6`; `AP1`, `AP9`; `PP2` | Medium |
| Budget Management & Forecasting | `Yes` | `Adjacent` - business finances and reports exist, but no explicit budgeting/forecasting page found | `Confirmed` for budgets; forecasting not explicit | `Adjacent` - budgeting is mentioned in related tools, but not clearly documented on the reviewed feature page | `HB1`, `HB6`; `AP1`, `AP2`, `AP3`; `PP2` | Medium |
| Photo Gallery & Guest QR Uploads | `Yes` | `Not found` | `Adjacent` - wedding website has QR RSVP access, but guest photo uploads are not explicit | `Not found` | `AP4`; `HB1`; `PP1`, `PP2` | Medium |
| Vendor CRM & Payment Tracking | `Yes` | `Adjacent` - contact workspace + payments, but not a vendor CRM | `Adjacent` - vendor/contact management plus invoicing/payments | `Adjacent` - CRM manager plus invoicing/payments | `HB3`, `HB6`; `AP1`, `AP9`; `PP2` | Medium |
| Custom Forms Builder & Analytics | `Yes` | `Adjacent` - live lead forms, questionnaires, and reports exist | `Adjacent` - lead contact forms, questionnaires, automated responses; analytics not explicit | `Adjacent` - online forms/surveys and reporting/tooling | `HB1`, `HB4`; `AP1`, `AP7`; `PP1`, `PP2` | High |
| Calendar with Google Sync | `Yes` | `Adjacent` - calendar/scheduler exist, but Google sync was not explicit in sources reviewed | `Confirmed` - external calendar syncing with Google, Outlook, Apple | `Not found` | `HB1`; `AP5`, `AP6`; `PP1`, `PP2` | High |
| Team Management (12+ permissions) | `Yes` | `Adjacent` - up to 2 team members on Essentials, unlimited on Premium, but no 12+ permission model found | `Adjacent` - unlimited users and collaboration settings, but no 12+ permission model found | `Adjacent` - unlimited users and team email controls, but no 12+ permission model found | `HB1`; `AP1`; `PP2` | High |
| Invoicing & Stripe Payments | `Yes` | `Adjacent` - invoicing/payments are explicit, but Stripe is not named on the reviewed pages | `Adjacent` - invoicing/online payments are explicit, but Stripe is not named on the reviewed pages | `Confirmed` - official Planning Pod article explicitly mentions Stripe integration | `HB1`, `HB6`; `AP1`, `AP9`; `PP2` | High |
| Multi-Tenant Agency Tier | `Yes` | `Adjacent` - teams and multiple collaborators exist, but no agency-tier branding | `Not found` | `Not found` | `HB1`; `AP1`; `PP2` | Medium |
| Vendor Advertising Portal | `Yes` | `Not found` | `Not found` | `Not found` | `HB1`, `HB5`; `AP1`; `PP2` | High |
| Touchless Day-of Check-in | `Yes` | `Not found` | `Not found` - QR RSVP access exists, but not a check-in app | `Adjacent` - registration/ticketing plus QR-code attendance flow, but not a dedicated check-in product | `AP4`; `PP2`; `HB1` | Medium |
| Starting price | `TSW: $29/mo` | `Confirmed` - `Plans start as low as $29/mo` | `Confirmed` - `Sales Essentials $49.99 / Mo` | `Confirmed` with caveat - `$149/month (paid yearly)` in official Planning Pod comparison article | `HB1`; `AP1`; `PP2` | High |

## Ambiguous Or Low-Confidence Rows

- `Couple Portal` is still the biggest terminology mismatch. HoneyBook has a client portal/client workspace, Aisle Planner has a client portal/project dashboard, and Planning Pod has event communication tools, but none of those pages expose a true wedding-couple portal workflow matching the Special Wedding feature.
- `SMS & Email Reminders with Fallback` remains only partially supported across competitors. HoneyBook and Planning Pod have reminders and/or SMS/email tools, but I did not find explicit fallback logic on any competitor site.
- `AI Contract Generation & E-Sign`, `AI Pricing & Package Builder`, and `AI Cash Flow Predictions` are still the clearest moat rows. Competitors have adjacent non-AI contract, proposal, billing, or finance tools, but not the exact AI workflows claimed by The Special Wedding.
- `Invoicing & Stripe Payments` should stay conservative. Stripe is explicit only in the Planning Pod source reviewed; HoneyBook and Aisle Planner expose payment functionality but do not name Stripe on the pages I checked.
- `Touchless Day-of Check-in` is strongest for Planning Pod, but the source is a registration/ticketing workflow, not a wedding-planner-specific check-in product.
- `Calendar with Google Sync` should stay conservative for HoneyBook and Planning Pod; I only found explicit external sync language on Aisle Planner.

## Re-audit Downgrade List

The following cells should be treated as downgraded from the earlier pass and published conservatively:

- `SMS & Email Reminders with Fallback`: downgrade all competitors to `Adjacent`.
- `AI Contract Generation & E-Sign`: keep all competitors as `Adjacent`, not `Confirmed`.
- `AI Pricing & Package Builder`: keep HoneyBook and Planning Pod as `Adjacent`; Aisle Planner stays `Not found`.
- `Budget Management & Forecasting`: keep HoneyBook and Planning Pod as `Adjacent`; Aisle Planner stays the only `Confirmed` budget match, but forecasting remains unproven.
- `Vendor CRM & Payment Tracking`: downgrade all competitors to `Adjacent`.
- `Custom Forms Builder & Analytics`: downgrade all competitors to `Adjacent`.
- `Calendar with Google Sync`: keep Aisle Planner `Confirmed`; HoneyBook and Planning Pod should stay `Adjacent` or `Not found` rather than implying parity.
- `Invoicing & Stripe Payments`: downgrade HoneyBook and Aisle Planner to `Adjacent`; keep Planning Pod `Confirmed`.
- `Touchless Day-of Check-in`: keep Planning Pod `Adjacent`; do not call it a confirmed check-in app.

## Bottom Line

The table in `app/features/page.tsx` is directionally useful, but several rows should not be published as hard binary truths. The safest public version is to keep the strong claims for guest management, Aisle Planner calendar sync, and Planning Pod check-in, while softening or qualifying the rows that are really adjacent capabilities rather than exact feature matches.
