"use client";

import dynamic from "next/dynamic";
import { startTransition, useEffect, useState } from "react";
import type { ThemeConfig } from "@/types/wedding";
import { getApiBaseUrl } from "@/utils/env";

const SignupModal = dynamic(() => import("@/components/saas/SignupModal").then((mod) => mod.SignupModal), {
  ssr: false,
});

type PricingTier = {
  id: string;
  name: string;
  tagline: string;
  price: string;
  period: string;
  features: string[];
  cta: string;
  popular?: boolean;
  savings?: string;
};

type Props = {
  pricing: PricingTier[];
  theme: ThemeConfig;
};

type ApiPlan = {
  _id: string;
  name: string;
  price_monthly: number;
  trial_days?: number;
  features_list?: string[];
  is_featured?: boolean;
  sort_order?: number;
  display_order?: number;
  is_active?: boolean;
};

export function PricingSignupSection({ pricing, theme }: Props) {
  const [displayPricing, setDisplayPricing] = useState<PricingTier[]>(pricing);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState<string | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    const timeout = window.setTimeout(() => {
      void fetch(`${getApiBaseUrl()}/public/subscription-plans`)
        .then((response) => (response.ok ? response.json() : Promise.reject(new Error("Failed to fetch plans"))))
        .then((plans: ApiPlan[]) => {
          if (cancelled || !Array.isArray(plans) || plans.length === 0) {
            return;
          }

          const mappedPlans = plans
            .filter((plan) => plan && plan.is_active !== false)
            .sort((a, b) => (a.sort_order ?? a.display_order ?? 0) - (b.sort_order ?? b.display_order ?? 0))
            .map<PricingTier>((plan) => ({
              id: plan._id,
              name: plan.name,
              tagline: plan.is_featured ? "Most popular for growing planner studios." : `For ${plan.name.toLowerCase()} planning teams.`,
              price: `$${plan.price_monthly}`,
              period: "/month",
              features: plan.features_list?.length ? plan.features_list : [],
              cta: plan.trial_days ? `Start ${plan.trial_days}-day trial` : `Choose ${plan.name}`,
              popular: Boolean(plan.is_featured),
              savings: plan.is_featured ? "Most popular" : undefined,
            }));

          if (mappedPlans.length > 0) {
            startTransition(() => setDisplayPricing(mappedPlans));
          }
        })
        .catch(() => {
          // Keep the server-rendered fallback pricing when the public plans API is unavailable.
        });
    }, 800);

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, []);

  const openSignup = (planId: string) => {
    setSelectedPlanId(planId);
    setModalOpen(true);
  };

  return (
    <section id="pricing" className="bg-slate-950 px-6 py-16 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto mb-10 max-w-3xl text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.28em] text-rose-200">Plans</p>
          <h2 className="mt-4 text-4xl font-semibold tracking-normal text-white sm:text-5xl">
            Start small, then scale the studio.
          </h2>
        </div>
        <div className="grid gap-5 lg:grid-cols-3">
          {displayPricing.map((tier) => (
            <article
              key={tier.id}
              className={`relative rounded-2xl border p-6 ${
                tier.popular ? "border-rose-300/60 bg-white/[0.08]" : "border-white/10 bg-white/[0.04]"
              }`}
            >
              {tier.savings ? (
                <span className="absolute right-5 top-5 rounded-full bg-rose-300 px-3 py-1 text-xs font-semibold text-slate-950">
                  {tier.savings}
                </span>
              ) : null}
              <h3 className="text-2xl font-semibold text-white">{tier.name}</h3>
              <p className="mt-3 min-h-14 text-sm leading-6 text-slate-300">{tier.tagline}</p>
              <div className="mt-6 flex items-end gap-1">
                <span className="text-4xl font-semibold text-white">{tier.price}</span>
                <span className="pb-1 text-sm text-slate-400">{tier.period}</span>
              </div>
              <ul className="mt-6 space-y-3 text-sm text-slate-200">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex gap-3">
                    <span className="mt-2 h-1.5 w-1.5 rounded-full bg-emerald-300" aria-hidden="true" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                onClick={() => openSignup(tier.id)}
                className={`mt-8 w-full rounded-full px-5 py-3 text-sm font-semibold transition ${
                  tier.popular
                    ? "bg-white text-slate-950 hover:bg-rose-50"
                    : "border border-white/20 text-white hover:bg-white/10"
                }`}
              >
                {tier.cta}
              </button>
            </article>
          ))}
        </div>
      </div>

      {modalOpen ? (
        <SignupModal isOpen={modalOpen} onClose={() => setModalOpen(false)} selectedPlanId={selectedPlanId} theme={theme} />
      ) : null}
    </section>
  );
}
