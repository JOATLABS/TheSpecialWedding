"use client";

import { umamiTrack } from "@/utils/umami";

// The couple offer is intentionally NOT part of the planner plan catalog:
// it is the one-time $199 couple plan (constant COUPLE_LIFETIME_OFFER in
// app/constants/billing.py), not a Mongo subscription plan, so it does not
// flow through /public/subscription-plans or the planner SignupModal.
//
// 2026-07-30: rendered as a compact card INSIDE the planner pricing grid
// (PricingSignupSection) so all tiers sit in one aligned row — the previous
// full-width band below the grid looked disorganized.
//
// IMPORTANT: keep price/copy in sync with app/constants/billing.py
// (COUPLE_LIFETIME_OFFER: $199 one-time), public/llms.txt, and the
// resources FAQ (app/resources/resourcesShared.ts).

// Stripe Payment Link for the couple one-time checkout (see .env.example).
// Client component: the value is inlined at build time (Dockerfile.frontend
// ARG + CI build-args). When unset we fall back to the sales/onboarding
// contact path — we never fabricate a checkout URL.
const COUPLE_CHECKOUT_URL = (process.env.NEXT_PUBLIC_COUPLE_CHECKOUT_URL ?? "").trim();

const COUPLE_CONTACT_FALLBACK_HREF =
  "mailto:hello@thespecialwedding.io?subject=Couple%20Plan%20(%24199%20one-time)";

const COUPLE_FEATURES = [
  "One live wedding workspace",
  "Full planning tools",
  "Guest list, plus-ones & RSVP tracking",
  "Your own wedding website",
  "Photo galleries & guest memories",
  "Export your wedding data anytime",
  "Active through 90 days after your wedding",
];

// Compact card matching the planner tier cards in PricingSignupSection —
// rendered inside the same grid so every tier aligns.
export function CouplePlanCard() {
  const hasCheckoutLink = COUPLE_CHECKOUT_URL.length > 0;
  const ctaHref = hasCheckoutLink ? COUPLE_CHECKOUT_URL : COUPLE_CONTACT_FALLBACK_HREF;
  const ctaLabel = hasCheckoutLink ? "Get your wedding workspace" : "Contact us to get started";

  return (
    <article
      id="for-couples"
      className="relative flex h-full min-h-full scroll-mt-28 flex-col rounded-xl border border-wedding-rose/40 bg-white/[0.04] p-4 sm:rounded-2xl sm:p-6 lg:min-h-[36rem]"
    >
      <span className="absolute right-4 top-4 rounded-full border border-wedding-rose/50 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-rose-200 sm:right-6 sm:top-6">
        For couples
      </span>
      <h3 className="text-2xl font-semibold text-white">Couple Plan</h3>
      <div className="mt-4 flex items-end gap-1 sm:mt-6">
        <span className="text-3xl font-semibold text-white sm:text-4xl">$199</span>
        <span className="pb-1 text-sm text-slate-400">one-time</span>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        One wedding, no planner subscription. Nothing renews.
      </p>
      <ul className="mt-4 grid flex-1 grid-cols-2 gap-x-4 gap-y-2 text-[13px] leading-5 text-slate-200 sm:mt-6 sm:block sm:space-y-3 sm:text-sm sm:leading-normal">
        {COUPLE_FEATURES.map((feature) => (
          <li key={feature} className="flex gap-2 sm:gap-3">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-300" aria-hidden="true" />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto pt-5 sm:pt-8">
        <a
          href={ctaHref}
          onClick={() =>
            umamiTrack("couple_cta_clicked", {
              has_checkout_link: hasCheckoutLink,
            })
          }
          className="inline-flex w-full items-center justify-center rounded-full border border-wedding-rose/60 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-wedding-rose/15 sm:py-3"
        >
          {ctaLabel}
        </a>
      </div>
    </article>
  );
}
