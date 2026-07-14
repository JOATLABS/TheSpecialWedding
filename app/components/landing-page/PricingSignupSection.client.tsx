"use client";

import dynamic from "next/dynamic";
import { startTransition, useEffect, useRef, useState } from "react";
import type { ThemeConfig } from "@/types/wedding";
import { getApiBaseUrl } from "@/utils/env";
import { umamiTrack } from "@/utils/umami";

const SignupModal = dynamic(() => import("@/components/saas/SignupModal").then((mod) => mod.SignupModal), {
  ssr: false,
});

type PricingTier = {
  id: string;
  name: string;
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
  billing_model?: string;
  is_metered?: boolean;
  trial_days?: number;
  features_list?: string[];
  is_featured?: boolean;
  sort_order?: number;
  display_order?: number;
  is_active?: boolean;
};

function getPlanPeriod(plan: Pick<ApiPlan, "is_metered" | "billing_model">): string {
  return plan.is_metered || plan.billing_model === "metered"
    ? "/active wedding/mo"
    : "/month";
}

export function PricingSignupSection({ pricing, theme }: Props) {
  const [displayPricing, setDisplayPricing] = useState<PricingTier[]>(pricing);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState<string | undefined>(undefined);

  // Umami: fire `pricing_viewed` once per session when the pricing section
  // first scrolls into view. The ref guard keeps it from re-firing on
  // subsequent scrolls, which would inflate the funnel-top number.
  const sectionRef = useRef<HTMLElement | null>(null);
  const viewedRef = useRef(false);
  useEffect(() => {
    const node = sectionRef.current;
    if (!node || viewedRef.current) return;
    if (typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && !viewedRef.current) {
            viewedRef.current = true;
            umamiTrack("pricing_viewed");
            observer.disconnect();
            break;
          }
        }
      },
      { threshold: 0.35 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    const timeout = window.setTimeout(() => {
      void fetch(`${getApiBaseUrl()}/public/subscription-plans`, {
        cache: "no-store",
      })
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
              price: `$${plan.price_monthly}`,
              period: getPlanPeriod(plan),
              features: plan.features_list?.length ? plan.features_list : [],
              cta: plan.price_monthly === 0 ? "Start free" : `Choose ${plan.name}`,
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
    const tier = displayPricing.find((p) => p.id === planId);
    umamiTrack("pricing_cta_clicked", {
      plan_id: planId,
      plan_name: tier?.name,
      is_popular: Boolean(tier?.popular),
    });
    setSelectedPlanId(planId);
    setModalOpen(true);
  };

  return (
    <section ref={sectionRef} id="pricing" className="scroll-mt-28 bg-slate-950 px-5 py-10 sm:px-8 sm:py-16 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto mb-7 max-w-3xl text-center sm:mb-10">
          <p className="text-sm font-semibold uppercase tracking-[0.28em] text-rose-200">Planner workspace plans</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-normal text-white sm:mt-4 sm:text-5xl">
            Start small, then scale the studio.
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
            Every plan opens the wedding planner workspace used to manage client weddings, couples, guests, vendors, and teams.
          </p>
        </div>
        <div className="grid items-stretch gap-3 sm:gap-5 md:grid-cols-2 lg:auto-rows-fr lg:grid-cols-4">
          {displayPricing.map((tier) => (
            <article
              key={tier.id}
              className={`relative flex h-full min-h-full flex-col rounded-xl border p-4 sm:rounded-2xl sm:p-6 lg:min-h-[36rem] ${
                tier.popular ? "border-rose-300/60 bg-white/[0.08]" : "border-white/10 bg-white/[0.04]"
              }`}
            >
              <h3 className="text-2xl font-semibold text-white">{tier.name}</h3>
              <div className="mt-4 flex items-end gap-1 sm:mt-6">
                <span className="text-3xl font-semibold text-white sm:text-4xl">{tier.price}</span>
                <span className="pb-1 text-sm text-slate-400">{tier.period}</span>
              </div>
              <ul className="mt-4 grid flex-1 grid-cols-2 gap-x-4 gap-y-2 text-[13px] leading-5 text-slate-200 sm:mt-6 sm:block sm:space-y-3 sm:text-sm sm:leading-normal">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex gap-2 sm:gap-3">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-300" aria-hidden="true" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-auto pt-5 sm:pt-8">
                <button
                  type="button"
                  onClick={() => openSignup(tier.id)}
                  className={`w-full rounded-full px-5 py-2.5 text-sm font-semibold transition sm:py-3 ${
                    tier.popular
                      ? "bg-white text-slate-950 hover:bg-rose-50"
                      : "border border-white/20 text-white hover:bg-white/10"
                  }`}
                >
                  {tier.cta}
                </button>
              </div>
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
