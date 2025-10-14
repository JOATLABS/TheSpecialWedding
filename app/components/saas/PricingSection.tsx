'use client';

import React, { useEffect, useMemo, useState } from 'react';

import { GlassCard } from '../ui/GlassCard';
import { ThemeConfig } from '@/types/wedding';

interface SubscriptionPlan {
  _id: string;
  name: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  max_weddings: number;
  max_guests_per_wedding: number;
  ai_credits_monthly: number;
  storage_gb: number;
  staff_seats: number;
  features: Record<string, boolean>;  // Backend format: {feature_name: true/false}
  features_list?: string[];  // Optional display list
  is_featured: boolean;
  is_active: boolean;
  display_order: number;
}

interface PricingSectionProps {
  theme: ThemeConfig;
  onPlanSelect?: (plan: { id: string; name: string }) => void;
}

const formatLimit = (value: number) => (value === -1 ? 'Unlimited' : value.toString());

// Fallback plans matching backend schema
const fallbackPlans: SubscriptionPlan[] = [
  {
    _id: 'plan_boutique',
    name: 'Boutique',
    description: 'For new planners onboarding their first weddings with concierge support.',
    price_monthly: 89,
    price_yearly: 930,
    max_weddings: 3,
    max_guests_per_wedding: 150,
    ai_credits_monthly: 400,
    storage_gb: 150,
    staff_seats: 1,
    features: {
      basic_website_builder: true,
      guest_management: true,
      rsvp_system: true,
      multi_user_collaboration: true,
    },
    features_list: ['Client-ready wedding websites', 'Unlimited vendor invites', 'Shared task boards', 'Automated payment reminders'],
    is_featured: false,
    is_active: true,
    display_order: 0,
  },
  {
    _id: 'plan_studio_growth',
    name: 'Studio Growth',
    description: 'Everything established planners need for 10 active weddings.',
    price_monthly: 179,
    price_yearly: 1890,
    max_weddings: 10,
    max_guests_per_wedding: 350,
    ai_credits_monthly: 900,
    storage_gb: 400,
    staff_seats: 3,
    features: {
      basic_website_builder: true,
      guest_management: true,
      ai_tools: true,
      advanced_reporting: true,
      multi_user_collaboration: true,
      priority_support: true,
    },
    features_list: ['AI timeline builder', 'Branded dashboards', 'Team permissions', 'Priority concierge support'],
    is_featured: true,
    is_active: true,
    display_order: 1,
  },
  {
    _id: 'plan_signature',
    name: 'Signature',
    description: 'Collaborate with unlimited vendors and automate client touchpoints.',
    price_monthly: 289,
    price_yearly: 3090,
    max_weddings: -1,
    max_guests_per_wedding: -1,
    ai_credits_monthly: 2000,
    storage_gb: 1024,
    staff_seats: -1,
    features: {
      basic_website_builder: true,
      guest_management: true,
      ai_tools: true,
      advanced_reporting: true,
      white_label: true,
      custom_integrations: true,
      multi_user_collaboration: true,
      priority_support: true,
    },
    features_list: ['Unlimited automations', 'White-glove onboarding', 'Advanced analytics', 'Dedicated success manager'],
    is_featured: false,
    is_active: true,
    display_order: 2,
  },
];

export const PricingSection: React.FC<PricingSectionProps> = ({ theme, onPlanSelect }) => {
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isYearly, setIsYearly] = useState(false);
  const [activePlanId, setActivePlanId] = useState<string | null>(null);

  useEffect(() => {
    fetchPlans();
  }, []);

  useEffect(() => {
    if (plans.length === 0 || activePlanId) {
      return;
    }
    const featured = plans.find((plan) => plan.is_featured) ?? plans[0];
    setActivePlanId(featured._id);
  }, [plans, activePlanId]);

  const selectedPlan = useMemo(
    () => plans.find((plan) => plan._id === activePlanId) ?? null,
    [plans, activePlanId]
  );

  const fetchPlans = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/public/subscription-plans`);

      if (!response.ok) {
        setPlans(fallbackPlans);
        setError('We are showing signature tiers while live pricing reconnects. Your choice will sync during onboarding.');
        return;
      }

      const data = await response.json();
      const sortedPlans = (Array.isArray(data) ? data : [])
        .filter((plan: SubscriptionPlan) => plan.is_active)
        .sort((a: SubscriptionPlan, b: SubscriptionPlan) => a.display_order - b.display_order);

      if (sortedPlans.length > 0) {
        setPlans(sortedPlans);
        setError('');
      } else {
        setPlans(fallbackPlans);
        setError('Live plans are temporarily unavailable. Showing our standard tiers.');
      }
    } catch (fetchError) {
      console.error('Failed to load pricing plans', fetchError);
      setPlans(fallbackPlans);
      setError('We could not connect to pricing services. Showing the latest available details.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPlan = (plan: SubscriptionPlan) => {
    setActivePlanId(plan._id);
    onPlanSelect?.({ id: plan._id, name: plan.name });
  };

  const getPriceLabel = (plan: SubscriptionPlan) => {
    if (plan.price_monthly === 0) {
      return 'Free';
    }

    const price = isYearly ? plan.price_yearly || plan.price_monthly * 12 : plan.price_monthly;
    const suffix = isYearly ? '/year' : '/month';
    return `$${price}${suffix}`;
  };

  if (loading) {
    return (
      <section className="px-4 py-16">
        <div className="mx-auto max-w-6xl text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2" style={{ borderColor: theme.primary_color }} />
          <p className="text-slate-200">Loading pricing plans…</p>
        </div>
      </section>
    );
  }

  if (error && plans.length === 0) {
    return (
      <section className="px-4 py-16">
        <div className="mx-auto max-w-6xl text-center">
          <p className="text-sm text-red-200">{error}</p>
        </div>
      </section>
    );
  }

  return (
    <section className="px-4 py-16">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-12">
        <div className="space-y-6 text-center">
          <h2 className="text-3xl font-semibold text-white sm:text-4xl">Simple, transparent pricing</h2>
          <p className="mx-auto max-w-3xl text-base text-slate-200 sm:text-lg">
            Choose the plan that fits your studio. Every tier includes our concierge onboarding and secure client portals.
          </p>

          <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <div className="inline-flex items-center rounded-full border border-white/30 bg-white/10 p-1 text-xs font-medium text-slate-200">
              <button
                type="button"
                onClick={() => setIsYearly(false)}
                className={`flex-1 rounded-full px-4 py-2 transition ${!isYearly ? 'bg-white text-slate-900 shadow' : 'hover:text-white'}`}
                aria-pressed={!isYearly}
              >
                Monthly
              </button>
              <button
                type="button"
                onClick={() => setIsYearly(true)}
                className={`flex-1 rounded-full px-4 py-2 transition ${isYearly ? 'bg-white text-slate-900 shadow' : 'hover:text-white'}`}
                aria-pressed={isYearly}
              >
                Yearly
              </button>
            </div>
            {isYearly && <span className="rounded-full bg-emerald-500/90 px-3 py-1 text-xs font-semibold text-white">Save 2 months</span>}
          </div>

          {error && plans.length > 0 && <p className="text-sm text-amber-200/90">{error}</p>}
        </div>

        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
          {plans.map((plan) => {
            const isSelected = plan._id === activePlanId;
            return (
              <button
                key={plan._id}
                type="button"
                onClick={() => handleSelectPlan(plan)}
                className={`group relative w-full overflow-hidden rounded-3xl border p-[1px] text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white ${
                  isSelected ? 'border-white/80 shadow-[0_28px_90px_-40px_rgba(15,23,42,0.7)]' : 'border-white/20 hover:border-white/50'
                }`}
                aria-pressed={isSelected}
              >
                <div className={`flex h-full flex-col gap-6 rounded-3xl p-6 transition ${isSelected ? 'bg-white/95 text-slate-900' : 'bg-white/80 text-slate-800 group-hover:bg-white/90'}`}>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xl font-semibold">{plan.name}</h3>
                      {plan.is_featured && (
                        <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">Most popular</span>
                      )}
                    </div>
                    <p className="text-sm text-slate-600">{plan.description}</p>
                  </div>

                  <div>
                    <div className="text-3xl font-semibold">{getPriceLabel(plan)}</div>
                    {isYearly && plan.price_monthly > 0 && (
                      <p className="text-xs text-slate-500">Billed annually. Equivalent to ${(plan.price_monthly * 12).toFixed(0)} per year.</p>
                    )}
                  </div>

                  <div className="space-y-3 text-sm">
                    <div className="flex items-center justify-between text-slate-600">
                      <span>Active weddings</span>
                      <span className="font-semibold text-slate-900">{formatLimit(plan.max_weddings)}</span>
                    </div>
                    <div className="flex items-center justify-between text-slate-600">
                      <span>Guests per event</span>
                      <span className="font-semibold text-slate-900">{formatLimit(plan.max_guests_per_wedding)}</span>
                    </div>
                    <div className="flex items-center justify-between text-slate-600">
                      <span>AI credits / month</span>
                      <span className="font-semibold text-slate-900">{plan.ai_credits_monthly}</span>
                    </div>
                    <div className="flex items-center justify-between text-slate-600">
                      <span>Secure storage</span>
                      <span className="font-semibold text-slate-900">{plan.storage_gb} GB</span>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Highlights</p>
                    <ul className="space-y-1 text-sm text-slate-600">
                      {(plan.features_list || []).slice(0, 4).map((feature, index) => (
                        <li key={index} className="flex items-start gap-2">
                          <span className={`mt-1 h-1.5 w-1.5 rounded-full ${isSelected ? 'bg-slate-900' : 'bg-slate-400'}`} aria-hidden="true" />
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {selectedPlan && (
          <GlassCard depth="near" blur="lg" className="flex flex-col gap-3 rounded-3xl border border-white/40 bg-white/85 p-6 text-left shadow-xl" theme={theme}>
            <p className="text-sm font-semibold text-slate-900">Selected plan</p>
            <div className="flex flex-col gap-2 text-sm text-slate-600 sm:flex-row sm:items-center sm:justify-between">
              <span className="text-base font-semibold text-slate-900">{selectedPlan.name}</span>
              <span>{getPriceLabel(selectedPlan)}</span>
            </div>
            <p className="text-xs text-slate-500">
              We&apos;ll carry this choice into onboarding so your free trial starts with the right usage limits.
            </p>
          </GlassCard>
        )}
      </div>
    </section>
  );
};

export default PricingSection;
