'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter } from 'next/navigation';

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

interface CachedPlans {
  plans: SubscriptionPlan[];
  timestamp: number;
}

interface PricingSectionProps {
  theme: ThemeConfig;
  onPlanSelect?: (plan: { id: string; name: string }) => void;
}

const formatLimit = (value: number) => (value === -1 ? 'Unlimited' : value.toString());

// Cache configuration
const CACHE_KEY = 'pricing_plans_cache';
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
const MAX_RETRIES = 3;
const INITIAL_RETRY_DELAY_MS = 1000; // 1 second, doubles each retry

export const PricingSection: React.FC<PricingSectionProps> = ({ theme, onPlanSelect }) => {
  const router = useRouter();
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isYearly, setIsYearly] = useState(false);
  const [activePlanId, setActivePlanId] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);

  // Get cached plans from localStorage
  const getCachedPlans = useCallback((): SubscriptionPlan[] | null => {
    if (typeof window === 'undefined') return null;
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (!cached) return null;

      const { plans: cachedPlans, timestamp }: CachedPlans = JSON.parse(cached);
      const isExpired = Date.now() - timestamp > CACHE_TTL_MS;

      if (isExpired) {
        localStorage.removeItem(CACHE_KEY);
        return null;
      }

      return cachedPlans;
    } catch {
      return null;
    }
  }, []);

  // Save plans to localStorage cache
  const setCachedPlans = useCallback((plansToCache: SubscriptionPlan[]) => {
    if (typeof window === 'undefined') return;
    try {
      const cacheData: CachedPlans = {
        plans: plansToCache,
        timestamp: Date.now(),
      };
      localStorage.setItem(CACHE_KEY, JSON.stringify(cacheData));
    } catch {
      // localStorage might be full or disabled - ignore
    }
  }, []);

  // Fetch with exponential backoff retry
  const fetchPlans = useCallback(async (attempt: number = 0): Promise<void> => {
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/public/subscription-plans`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      const sortedPlans = (Array.isArray(data) ? data : [])
        .filter((plan: SubscriptionPlan) => plan.is_active)
        .sort((a: SubscriptionPlan, b: SubscriptionPlan) => a.display_order - b.display_order);

      if (sortedPlans.length > 0) {
        setPlans(sortedPlans);
        setCachedPlans(sortedPlans); // Cache successful response
        setError('');
        setRetryCount(0);
        setIsRetrying(false);
      } else {
        setError('No pricing plans are currently available. Please contact us for custom pricing.');
      }
    } catch (fetchError) {
      console.error(`Failed to load pricing plans (attempt ${attempt + 1}/${MAX_RETRIES})`, fetchError);

      // Try to use cached data first
      const cachedPlans = getCachedPlans();
      if (cachedPlans && cachedPlans.length > 0) {
        setPlans(cachedPlans);
        setError(''); // Don't show error if we have cached data
        setRetryCount(0);
        setIsRetrying(false);
        return;
      }

      // Retry with exponential backoff
      if (attempt < MAX_RETRIES - 1) {
        setIsRetrying(true);
        setRetryCount(attempt + 1);
        const delay = INITIAL_RETRY_DELAY_MS * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
        return fetchPlans(attempt + 1);
      }

      // All retries exhausted
      setIsRetrying(false);
      setError('Pricing is temporarily unavailable. Please try again shortly or contact us for details.');
    } finally {
      setLoading(false);
    }
  }, [getCachedPlans, setCachedPlans]);

  const handleSelectPlan = (plan: SubscriptionPlan) => {
    setActivePlanId(plan._id);
    onPlanSelect?.({ id: plan._id, name: plan.name });

    // If user is authenticated, redirect to billing page with pre-selected plan
    const token = localStorage.getItem('authToken');
    if (token) {
      const billingInterval = isYearly ? 'yearly' : 'monthly';
      router.push(`/admin/billing?plan=${encodeURIComponent(plan._id)}&interval=${billingInterval}`);
    }
  };

  // Derive selected plan object from activePlanId
  const selectedPlan = useMemo(() => {
    if (!activePlanId) return null;
    return plans.find(p => p._id === activePlanId) || null;
  }, [activePlanId, plans]);

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
          <p className="text-slate-200">
            {isRetrying
              ? `Retrying... (attempt ${retryCount + 1}/${MAX_RETRIES})`
              : 'Loading pricing plans…'
            }
          </p>
        </div>
      </section>
    );
  }

  if (error && plans.length === 0) {
    return (
      <section className="px-4 py-16">
        <div className="mx-auto max-w-2xl text-center">
          <div className="rounded-2xl border border-white/20 bg-white/10 backdrop-blur-sm p-8">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/20">
              <svg className="h-6 w-6 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Pricing Temporarily Unavailable</h3>
            <p className="text-slate-300 mb-6">{error}</p>
            <a
              href="mailto:hello@thespecialwedding.com"
              className="inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-900 hover:bg-slate-100 transition"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              Contact Us for Pricing
            </a>
          </div>
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
