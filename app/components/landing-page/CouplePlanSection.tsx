"use client";

import { umamiTrack } from "@/utils/umami";

// The couple offer is intentionally NOT part of the planner plan catalog:
// it is the one-time $199 couple plan (constant
// COUPLE_LIFETIME_OFFER in app/constants/billing.py), not a Mongo
// subscription plan, so it does not flow through /public/subscription-plans
// or the planner SignupModal. Planner tiers stay the primary offering; this
// band renders BELOW the planner pricing grid as a clearly separated,
// secondary section.
//
// IMPORTANT: keep price/copy in sync with app/constants/billing.py
// (COUPLE_LIFETIME_OFFER: $199 one-time), public/llms.txt, and the
// resources FAQ (app/resources/resourcesShared.ts).

// Stripe Payment Link for the couple one-time checkout, created against the
// live "The Special Wedding — Couple Plan (One Wedding)" product (see
// .env.example). This is a client component, so the value is inlined at
// build time (Dockerfile.frontend ARG + CI build-args). When the env var is
// unset we fall back to the sales/onboarding contact path — we never
// fabricate a checkout URL.
const COUPLE_CHECKOUT_URL = (process.env.NEXT_PUBLIC_COUPLE_CHECKOUT_URL ?? "").trim();

const COUPLE_CONTACT_FALLBACK_HREF =
  "mailto:hello@thespecialwedding.io?subject=Couple%20Plan%20(%24199%20one-time)";

const COUPLE_FEATURES = [
  "One live wedding workspace — active through 90 days after your wedding",
  "Full planning tools for your entire planning window",
  "Guest list, plus-ones, and RSVP tracking",
  "Your own wedding website for guests",
  "Photo galleries and guest memories",
  "Export your wedding data anytime",
];

export function CouplePlanSection() {
  const hasCheckoutLink = COUPLE_CHECKOUT_URL.length > 0;
  const ctaHref = hasCheckoutLink ? COUPLE_CHECKOUT_URL : COUPLE_CONTACT_FALLBACK_HREF;
  const ctaLabel = hasCheckoutLink ? "Get your wedding workspace" : "Contact us to get started";

  return (
    <section
      id="for-couples"
      className="scroll-mt-28 bg-slate-950 px-5 pb-16 pt-2 sm:px-8 sm:pb-20 lg:px-12"
    >
      <div className="mx-auto max-w-7xl">
        <div className="rounded-2xl border border-wedding-rose/30 bg-white/[0.04] p-6 sm:rounded-3xl sm:p-10">
          <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-rose-200">For couples</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-normal text-white sm:text-4xl">
                Planning your own wedding?
              </h2>
              <p className="mt-4 max-w-xl text-sm leading-6 text-slate-300 sm:text-base">
                You don&apos;t need a planner subscription. The couple plan is a single one-time fee
                that covers everything the platform offers for one wedding — your entire planning
                window plus 90 days after your wedding day. Not a subscription. Nothing renews.
              </p>
              <ul className="mt-6 grid gap-x-6 gap-y-2.5 text-[13px] leading-5 text-slate-200 sm:grid-cols-2 sm:text-sm">
                {COUPLE_FEATURES.map((feature) => (
                  <li key={feature} className="flex gap-2 sm:gap-3">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-300" aria-hidden="true" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="flex flex-col items-center rounded-2xl border border-white/10 bg-white/[0.05] p-6 text-center sm:p-8">
              <div className="flex items-end gap-1">
                <span className="text-5xl font-semibold text-white">$199</span>
                <span className="pb-1.5 text-sm text-slate-400">one-time</span>
              </div>
              <p className="mt-2 text-sm font-medium text-rose-200">Through 90 days after your wedding</p>
              <a
                href={ctaHref}
                onClick={() =>
                  umamiTrack("couple_cta_clicked", {
                    has_checkout_link: hasCheckoutLink,
                  })
                }
                className="mt-6 inline-flex w-full items-center justify-center rounded-full border border-wedding-rose/60 px-6 py-3 text-sm font-semibold text-white transition hover:bg-wedding-rose/15 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-wedding-rose"
              >
                {ctaLabel}
              </a>
              <p className="mt-3 text-xs leading-5 text-slate-400">
                One payment for one wedding workspace. Your workspace closes 90 days after your
                wedding — export everything before then. Working with a planner? Ask them to invite
                you — your couple portal is included in their plan.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
