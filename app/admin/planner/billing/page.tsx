"use client";

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import { formatAdminDate, DEFAULT_TIMEZONE } from '@/utils/dateFormat';
import {
  BILLING_PORTAL_RECOVERY_SUBSCRIPTION_STATUSES,
  getPlannerBillingEntryState,
  normalizeSubscriptionStatus,
} from '@/utils/subscriptionStatus';
import PageHeader from '../../components/PageHeader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import {
  Loader2,
  CreditCard,
  CheckCircle2,
  XCircle,
  Clock,
  Calendar,
  Database,
  Zap,
  Users,
  Download,
  AlertTriangle,
  AlertCircle,
  ChevronRight,
  Receipt,
  Shield,
  TrendingUp,
  RefreshCw
} from 'lucide-react';
import { toast } from 'sonner';
import { usePagination } from '@/admin/hooks/usePagination';
import { GlassPagination } from '@/admin/components/ui/glass/GlassPagination';
import PayoutsCard from './PayoutsCard';

interface SubscriptionPlan {
  _id: string;
  name: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  billing_model?: string;
  is_metered?: boolean;
  max_weddings: number;
  max_guests_per_wedding: number;
  ai_credits_monthly: number;
  storage_gb: number;
  staff_seats: number;
  features: Record<string, boolean>;
  features_list?: string[];
  is_featured: boolean;
}

const billingCadenceLabel = (plan: SubscriptionPlan | null | undefined, interval: 'monthly' | 'yearly') => {
  const isMetered = plan?.is_metered || plan?.billing_model === 'metered';
  if (isMetered) {
    return interval === 'yearly' ? 'active wedding/yr' : 'active wedding/mo';
  }
  return interval === 'yearly' ? 'yr' : 'mo';
};

interface UserSubscription {
  _id?: string;
  plan_id: string;
  status: string;
  billing_interval: string;
  current_period_start: string;
  current_period_end: string;
  stripe_subscription_id?: string;
  stripe_customer_id?: string;
  payment_status?: string;
  created_at?: string;
  card_last_four?: string;
  card_brand?: string;
  card_exp_month?: number;
  card_exp_year?: number;
}

interface UsageStats {
  weddings_count: number;
  total_guests: number;
  storage_used_gb: number;
  ai_credits_used: number;
  ai_credits_remaining: number;
  // AI credits are soft-capped with metered overage billing. When `overage`
  // is true, `overage_credits` is the count past the included allotment and
  // `overage_cost_cents` is the running charge for the current cycle at
  // `overage_price_per_credit_usd`. The backend computes all three via
  // SubscriptionService.check_usage_limits("ai_credits"); see /admin/ai/credits.
  ai_overage?: boolean;
  ai_overage_credits?: number;
  ai_overage_cost_cents?: number;
  ai_overage_price_per_credit_usd?: number;
}

interface Invoice {
  id: string;
  date: string;
  amount: number;
  status: string;
  invoice_pdf?: string;
  description: string;
}

interface BillingAlert {
  type: 'warning' | 'error' | 'info';
  title: string;
  message: string;
  action?: string;
  actionLabel?: string;
}

const normalizeSubscription = (subscription: UserSubscription): UserSubscription => ({
  ...subscription,
  status: normalizeSubscriptionStatus(subscription.status),
});

export default function PlannerBillingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const handledCheckoutSessionRef = useRef<string | null>(null);
  const portalRetryCountRef = useRef(0);
  const { userProfile, token, fetchUserProfile } = useAdmin();
  const [loading, setLoading] = useState(true);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [currentSubscription, setCurrentSubscription] = useState<UserSubscription | null>(null);
  const [currentPlan, setCurrentPlan] = useState<SubscriptionPlan | null>(null);
  const [usageStats, setUsageStats] = useState<UsageStats>({
    weddings_count: 0,
    total_guests: 0,
    storage_used_gb: 0,
    ai_credits_used: 0,
    ai_credits_remaining: 100,
    ai_overage: false,
    ai_overage_credits: 0,
    ai_overage_cost_cents: 0,
    ai_overage_price_per_credit_usd: 0,
  });
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [allInvoices, setAllInvoices] = useState<Invoice[]>([]);
  const [billingAlerts, setBillingAlerts] = useState<BillingAlert[]>([]);
  const paginationInvoices = usePagination({ initialItemsPerPage: 50 });
  const requestedPlanId = searchParams.get('plan');
  const requestedInterval = searchParams.get('interval') === 'yearly' ? 'yearly' : 'monthly';
  const checkoutSucceeded = searchParams.get('success') === 'true';
  const checkoutSessionId = searchParams.get('session_id');
  const portalReturned = searchParams.get('from_portal') === '1';
  // Access control - only for wedding planners
  useEffect(() => {
    if (userProfile && !userProfile.is_wedding_planner && !userProfile.is_root_admin) {
      router.push('/admin');
    }
  }, [userProfile, router]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const baseUrl = getApiBaseUrl();

      if (!token || !userProfile) return;

      // Load available plans
      let fetchedPlans: SubscriptionPlan[] = [];
      const plansResponse = await fetch(
        `${baseUrl}/public/subscription-plans`,
        { credentials: 'include' }
      );

      if (plansResponse.ok) {
        fetchedPlans = await plansResponse.json();
        setPlans(fetchedPlans);
      }

      // Try to load subscription with card details from the new endpoint first
      let subscriptionLoaded = false;
      try {
        const stripeSubResponse = await fetch(
          `${baseUrl}/stripe/subscription`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            credentials: 'include'
          }
        );

        // 402 = subscription expired/blocked — trigger profile refresh to update subscription status
        if (stripeSubResponse.status === 402) {
          if (portalRetryCountRef.current < 1) {
            portalRetryCountRef.current += 1;
            await fetchUserProfile();
            // Exit early; profile update will trigger loadData again via useEffect
            return;
          }
          // If we've already retried once, don't retry again to avoid infinite loop
          return;
        }

        if (stripeSubResponse.ok) {
          const subData = normalizeSubscription(await stripeSubResponse.json());
          if (subData && subData.plan_id) {
            setCurrentSubscription(subData);
            const planDetail = fetchedPlans.find((p: SubscriptionPlan) => p._id === subData.plan_id);
            setCurrentPlan(planDetail || null);
            generateBillingAlerts(subData, planDetail);
            subscriptionLoaded = true;
          }
        }
      } catch (error) {
        console.warn('Could not load subscription from Stripe endpoint:', error);
      }

      // Fallback to legacy endpoints if Stripe endpoint failed
      if (!subscriptionLoaded) {
        // Use user_id (MongoDB _id mapped to .id), not email — backend authorization checks _id match
        const userId = userProfile.id || (userProfile as any)._id || (userProfile as any).user_data?._id || '';
        if (userId) {
          const subResponse = await fetch(
            `${baseUrl}/users/${encodeURIComponent(userId)}/subscription`,
            {
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
              },
              credentials: 'include'
            }
          );

          // 402 = subscription expired/blocked — trigger profile refresh
          if (subResponse.status === 402) {
            if (portalRetryCountRef.current < 1) {
              portalRetryCountRef.current += 1;
              await fetchUserProfile();
              // Exit early; profile update will trigger loadData again via useEffect
              return;
            }
            // If we've already retried once, don't retry again to avoid infinite loop
            return;
          }

          if (subResponse.ok) {
            const subData = normalizeSubscription(await subResponse.json());
            if (subData && subData.plan_id) {
              setCurrentSubscription(subData);
              const planDetail = fetchedPlans.find((p: SubscriptionPlan) => p._id === subData.plan_id);
              setCurrentPlan(planDetail || null);
              generateBillingAlerts(subData, planDetail);
              subscriptionLoaded = true;
            }
          }
        }
      }

      // Last-resort fallback: if no subscription endpoints returned data but
      // the user profile indicates an active/trial subscription (set by webhook
      // updating the users collection), construct a minimal subscription object
      // so the billing page shows the management view instead of "Choose Your Plan".
      const normalizedProfileStatus = normalizeSubscriptionStatus(userProfile.subscription_status);
      if (!subscriptionLoaded && ['active', 'trial'].includes(normalizedProfileStatus)) {
        const profilePlanId = (userProfile as any).user_data?.plan_id || '';
        if (profilePlanId) {
          const minimalSub: any = {
            plan_id: profilePlanId,
            status: normalizedProfileStatus,
            billing_interval: 'monthly',
            payment_status: 'paid',
          };
          setCurrentSubscription(minimalSub);
          const planDetail = fetchedPlans.find((p: SubscriptionPlan) => p._id === profilePlanId);
          setCurrentPlan(planDetail || null);
          if (planDetail) {
            generateBillingAlerts(minimalSub, planDetail);
          }
        }
      }

      // Load usage statistics (S6: from weddings + AI credits endpoint)
      try {
        const weddingsResponse = await fetch(
          `${baseUrl}/admin/weddings`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            credentials: 'include'
          }
        );

        // 402 = subscription expired/blocked — trigger profile refresh
        if (weddingsResponse.status === 402) {
          if (portalRetryCountRef.current < 1) {
            portalRetryCountRef.current += 1;
            await fetchUserProfile();
            // Exit early; profile update will trigger loadData again via useEffect
            return;
          }
          // If we've already retried once, don't retry again to avoid infinite loop
          return;
        }

        if (weddingsResponse.ok) {
          const weddingsData = await weddingsResponse.json();
          const weddingsList = weddingsData.weddings || weddingsData || [];

          // Calculate total guests across all weddings
          let totalGuests = 0;
          if (Array.isArray(weddingsList)) {
            weddingsList.forEach((wedding: { guest_count?: number }) => {
              totalGuests += wedding.guest_count || 0;
            });
          }

          setUsageStats(prev => ({
            ...prev,
            weddings_count: Array.isArray(weddingsList) ? weddingsList.length : 0,
            total_guests: totalGuests
          }));
        }
      } catch (error) {
        console.warn('Could not load weddings count:', error);
      }

      // S6: Load AI credit usage from dedicated endpoint
      try {
        const creditsResponse = await fetch(
          `${baseUrl}/admin/ai/credits`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            credentials: 'include'
          }
        );

        if (creditsResponse.ok) {
          const creditsData = await creditsResponse.json();
          // The `/admin/ai/credits` endpoint now passes through the soft-cap
          // overage shape from SubscriptionService.check_usage_limits().
          // `credits_used` is preferred over the computed diff because the
          // backend resolves it via live aggregation on `ai_usage_log`,
          // which is the canonical source; the counter can drift.
          const used =
            typeof creditsData.credits_used === 'number'
              ? creditsData.credits_used
              : (creditsData.credits_limit || 0) - (creditsData.credits_remaining || 0);
          setUsageStats(prev => ({
            ...prev,
            ai_credits_used: used,
            ai_credits_remaining: creditsData.credits_remaining || 0,
            ai_overage: Boolean(creditsData.overage),
            ai_overage_credits: creditsData.overage_credits || 0,
            ai_overage_cost_cents: creditsData.overage_cost_cents || 0,
            ai_overage_price_per_credit_usd:
              creditsData.overage_price_per_credit_usd || 0,
          }));
        }
      } catch (error) {
        console.warn('Could not load AI credits:', error);
      }

      // Load billing history from Stripe
      try {
        const invoicesResponse = await fetch(
          `${baseUrl}/stripe/invoices`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            credentials: 'include'
          }
        );

        if (invoicesResponse.ok) {
          const invoicesData = await invoicesResponse.json();
          // Convert Unix timestamps to ISO strings for display
          const formattedInvoices = invoicesData.map((inv: { id: string; date: number; amount: number; status: string; invoice_pdf?: string; description: string }) => ({
            ...inv,
            date: new Date(inv.date * 1000).toISOString()
          }));
          setAllInvoices(formattedInvoices);
          paginationInvoices.setTotalItems(formattedInvoices.length);
        }
      } catch (error) {
        console.warn('Invoices not available:', error);
      }

    } catch (error) {
      console.error('Error loading billing data:', error);
      toast.error('Failed to load billing information');
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, userProfile, paginationInvoices.currentPage, paginationInvoices.itemsPerPage]);

  const generateBillingAlerts = (subscription: UserSubscription, plan: SubscriptionPlan | null | undefined) => {
    const alerts: BillingAlert[] = [];

    // Check card expiration
    if (subscription.card_exp_month && subscription.card_exp_year) {
      const now = new Date();
      const expDate = new Date(subscription.card_exp_year, subscription.card_exp_month - 1);
      const monthsUntilExp = (expDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24 * 30);

      if (monthsUntilExp < 0) {
        alerts.push({
          type: 'error',
          title: 'Card Expired',
          message: 'Your payment method has expired. Please update it to avoid service interruption.',
          action: 'update_payment',
          actionLabel: 'Update Now'
        });
      } else if (monthsUntilExp <= 2) {
        alerts.push({
          type: 'warning',
          title: 'Card Expiring Soon',
          message: `Your card ending in ${subscription.card_last_four} expires in ${Math.ceil(monthsUntilExp)} month(s).`,
          action: 'update_payment',
          actionLabel: 'Update Card'
        });
      }
    }

    // Check subscription status
    if (normalizeSubscriptionStatus(subscription.status) === 'past_due') {
      alerts.push({
        type: 'error',
        title: 'Payment Failed',
        message: 'Your last payment failed. Please update your payment method to continue service.',
        action: 'update_payment',
        actionLabel: 'Fix Payment'
      });
    }

    // Check if subscription is about to renew (within 7 days)
    if (subscription.current_period_end) {
      const endDate = new Date(subscription.current_period_end);
      const now = new Date();
      const daysUntilRenewal = (endDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);

      if (daysUntilRenewal <= 7 && daysUntilRenewal > 0 && normalizeSubscriptionStatus(subscription.status) === 'active') {
        const price = subscription.billing_interval === 'yearly'
          ? plan?.price_yearly
          : plan?.price_monthly;
        alerts.push({
          type: 'info',
          title: 'Upcoming Renewal',
          message: `Your subscription renews in ${Math.ceil(daysUntilRenewal)} days. You'll be charged $${price}.`
        });
      }
    }

    setBillingAlerts(alerts);
  };

  useEffect(() => {
    if (userProfile) {
      loadData();
    }
  }, [userProfile, loadData]);

  useEffect(() => {
    if (!checkoutSucceeded || !checkoutSessionId || !token) {
      return;
    }

    if (handledCheckoutSessionRef.current === checkoutSessionId) {
      return;
    }

    handledCheckoutSessionRef.current = checkoutSessionId;

    const reconcileCheckoutReturn = async () => {
      try {
        const baseUrl = getApiBaseUrl();
        const sessionResponse = await fetch(
          `${baseUrl}/stripe/checkout-session/${encodeURIComponent(checkoutSessionId)}`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            credentials: 'include',
          },
        );

        if (!sessionResponse.ok) {
          throw new Error('Unable to verify the completed checkout session');
        }

        const sessionPayload = await sessionResponse.json();
        const session = sessionPayload.session;

        if (!session || (session.payment_status !== 'paid' && !session.subscription)) {
          toast.error('Stripe checkout did not complete successfully.');
          return;
        }

        toast.success('Checkout completed. Syncing your billing status...');

        for (let attempt = 0; attempt < 5; attempt += 1) {
          const subscriptionResponse = await fetch(
            `${baseUrl}/stripe/subscription`,
            {
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
              },
              credentials: 'include',
            },
          );

          if (subscriptionResponse.ok) {
            await loadData();
            router.replace('/admin/planner/billing');
            return;
          }

          await new Promise((resolve) => window.setTimeout(resolve, 1200));
        }

        await loadData();
        toast.message('Payment confirmed with Stripe. Billing details may take a few more seconds to refresh.');
        router.replace('/admin/planner/billing');
      } catch (error) {
        console.error('Checkout reconciliation failed:', error);
        toast.error(error instanceof Error ? error.message : 'Unable to verify your Stripe checkout return');
      }
    };

    void reconcileCheckoutReturn();
  }, [checkoutSessionId, checkoutSucceeded, loadData, router, token]);

  // Handle portal return: user returns from Stripe portal, poll for webhook updates
  useEffect(() => {
    if (!portalReturned || !token) {
      return;
    }

    // Reset the retry count ref when returning from portal
    portalRetryCountRef.current = 0;

    const handlePortalReturn = async () => {
      try {
        // Wait 1.5s for webhook to process
        await new Promise((resolve) => window.setTimeout(resolve, 1500));

        // Load updated billing data
        await loadData();

        // Check if subscription status was updated by webhook
        // If still stale, retry once more after 2s
        const subscriptionStale = !currentSubscription ||
          (currentSubscription.status &&
           ['pending_checkout', 'pending_payment'].includes(
             normalizeSubscriptionStatus(currentSubscription.status)
           ));

        if (subscriptionStale) {
          await new Promise((resolve) => window.setTimeout(resolve, 2000));
          await loadData();
        }

        // Clean up the URL param
        router.replace('/admin/planner/billing');
      } catch (error) {
        console.error('Portal return handling failed:', error);
        // Still clean up the URL even if there was an error
        router.replace('/admin/planner/billing');
      }
    };

    void handlePortalReturn();
  }, [portalReturned, token, loadData, router, currentSubscription]);

  const openBillingPortal = async (flowType?: 'payment_method_update' | 'subscription_update' | 'subscription_cancel', loadingMessage?: string) => {
    try {
      const baseUrl = getApiBaseUrl();

      if (!token) {
        toast.error('Please log in to manage billing');
        return;
      }

      toast.loading(loadingMessage || 'Opening billing portal...', { id: 'portal-loading' });

      const response = await fetch(
        `${baseUrl}/stripe/create-portal-session`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify({
            return_url: `${window.location.origin}/admin/planner/billing?from_portal=1`,
            flow_type: flowType
          })
        }
      );

      toast.dismiss('portal-loading');

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || 'Failed to create portal session';

        if (response.status === 404) {
          toast.error('No billing account found. Please subscribe to a plan first.');
        } else if (response.status === 503) {
          toast.error('Billing service is currently unavailable. Please try again later.');
        } else {
          toast.error(errorMessage);
        }
        return;
      }

      const data = await response.json();

      if (data.portal_url) {
        window.location.href = data.portal_url;
      } else {
        toast.error('Unable to open billing portal. Please try again.');
      }
    } catch (error) {
      toast.dismiss('portal-loading');
      console.error('Portal error:', error);
      toast.error('Failed to connect to billing service. Please check your connection and try again.');
    }
  };

  const handleChangePlan = () => openBillingPortal('subscription_update', 'Opening plan options...');
  const handleUpdatePayment = () => openBillingPortal('payment_method_update', 'Opening payment settings...');
  const handleCancelSubscription = () => openBillingPortal('subscription_cancel', 'Opening cancellation page...');
  const handleManageBilling = () => openBillingPortal(undefined, 'Opening billing portal...');

  const handleSubscribe = async (planId: string, interval: 'monthly' | 'yearly' = 'monthly') => {
    try {
      const baseUrl = getApiBaseUrl();

      if (!token) {
        toast.error('Please log in to subscribe');
        return;
      }

      const response = await fetch(
        `${baseUrl}/stripe/create-checkout-session`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify({
            plan_id: planId,
            billing_interval: interval,
            success_url: `${window.location.origin}/admin/planner/billing?success=true&session_id={CHECKOUT_SESSION_ID}`,
            cancel_url: `${window.location.origin}/admin/planner/billing`,
            trial_days: 0,
          })
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create checkout session');
      }

      const data = await response.json();

      if (data.checkout_session?.url) {
        window.location.href = data.checkout_session.url;
      } else if (data.url) {
        window.location.href = data.url;
      }
    } catch (error: unknown) {
      console.error('Subscribe error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to start subscription process';
      toast.error(errorMessage);
    }
  };

  const getStatusConfig = (status: string) => {
    const normalizedStatus = normalizeSubscriptionStatus(status);
    const config: Record<string, { color: string; bgColor: string; icon: React.ReactNode; label: string }> = {
      active: {
        color: 'text-green-700 dark:text-green-300',
        bgColor: 'bg-green-100 dark:bg-green-900/30',
        icon: <CheckCircle2 className="w-4 h-4" />,
        label: 'Active'
      },
      trial: {
        color: 'text-blue-700 dark:text-blue-300',
        bgColor: 'bg-blue-100 dark:bg-blue-900/30',
        icon: <Clock className="w-4 h-4" />,
        label: 'Trial'
      },
      cancelled: {
        color: 'text-red-700 dark:text-red-300',
        bgColor: 'bg-red-100 dark:bg-red-900/30',
        icon: <XCircle className="w-4 h-4" />,
        label: 'Cancelled'
      },
      past_due: {
        color: 'text-yellow-700 dark:text-yellow-300',
        bgColor: 'bg-yellow-100 dark:bg-yellow-900/30',
        icon: <AlertCircle className="w-4 h-4" />,
        label: 'Past Due'
      },
      pending_checkout: {
        color: 'text-amber-700 dark:text-amber-300',
        bgColor: 'bg-amber-100 dark:bg-amber-900/30',
        icon: <Clock className="w-4 h-4" />,
        label: 'Checkout Pending'
      },
      pending_payment: {
        color: 'text-amber-700 dark:text-amber-300',
        bgColor: 'bg-amber-100 dark:bg-amber-900/30',
        icon: <AlertTriangle className="w-4 h-4" />,
        label: 'Payment Required'
      },
      suspended: {
        color: 'text-red-700 dark:text-red-300',
        bgColor: 'bg-red-100 dark:bg-red-900/30',
        icon: <AlertCircle className="w-4 h-4" />,
        label: 'Suspended'
      },
      inactive: {
        color: 'text-slate-700 dark:text-slate-300',
        bgColor: 'bg-slate-100 dark:bg-slate-800',
        icon: <XCircle className="w-4 h-4" />,
        label: 'Inactive'
      }
    };
    return config[normalizedStatus] || {
      color: 'text-slate-700 dark:text-slate-300',
      bgColor: 'bg-slate-100 dark:bg-slate-800',
      icon: <AlertCircle className="w-4 h-4" />,
      label: normalizedStatus ? normalizedStatus.replace(/_/g, ' ') : 'Unknown',
    };
  };

  const getUsagePercentage = (used: number, total: number) => {
    if (total === -1) return 0;
    return Math.min((used / total) * 100, 100);
  };

  const getUsageColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 75) return 'bg-yellow-500';
    return 'bg-blue-500';
  };

  // Get planner's timezone from user profile or use default
  const plannerTimezone = userProfile?.user_data?.timezone || DEFAULT_TIMEZONE;

  const formatDate = (dateString: string) => {
    return formatAdminDate(dateString, plannerTimezone);
  };

  const getMemberSinceDate = () => {
    if (currentSubscription?.created_at) {
      return formatDate(currentSubscription.created_at);
    }
    if (currentSubscription?.current_period_start) {
      return formatDate(currentSubscription.current_period_start);
    }
    return 'N/A';
  };

  const getDaysUntilRenewal = () => {
    if (!currentSubscription?.current_period_end) return null;
    const endDate = new Date(currentSubscription.current_period_end);
    const now = new Date();
    return Math.ceil((endDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  // No subscription OR unpaid/expired/cancelled — show plan selection with fresh checkout
  const subStatus = normalizeSubscriptionStatus(currentSubscription?.status);
  const billingEntryState = getPlannerBillingEntryState({
    status: subStatus,
    hasSubscription: Boolean(currentSubscription),
    hasPlan: Boolean(currentPlan),
  });
  const needsPortalRecovery = billingEntryState === 'portal_recovery';
  const needsNewSubscription = billingEntryState === 'new_checkout';
  if (needsNewSubscription) {
    const requestedPlan = requestedPlanId
      ? plans.find((plan) => plan._id === requestedPlanId) ?? null
      : null;
    const heading = subStatus === 'expired'
      ? 'Reactivate Your Account'
      : subStatus === 'cancelled'
        ? 'Resubscribe'
        : subStatus === 'pending_checkout'
          ? 'Complete Your Subscription'
          : 'Choose Your Plan';
    const description = subStatus === 'expired'
      ? 'Your trial has ended. Choose a plan to continue — all your data is safe and will be restored instantly.'
      : subStatus === 'cancelled'
        ? 'Welcome back! Pick a plan to reactivate your account.'
        : subStatus === 'pending_checkout'
          ? 'Your last checkout was not completed. Choose a plan to resume with a fresh Stripe Checkout session.'
          : 'Select a subscription plan to unlock all features and start managing your weddings.';

    return (
      <div className="space-y-6">
        <div className="text-center py-12">
          <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <CreditCard className="w-8 h-8 text-blue-600 dark:text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
            {heading}
          </h1>
          <p className="text-gray-600 dark:text-gray-400 max-w-md mx-auto">
            {description}
          </p>
        </div>

        {requestedPlan && (
          <div className="mx-auto max-w-3xl rounded-2xl border border-blue-200 bg-blue-50 px-6 py-4 text-sm text-blue-900 dark:border-blue-900/60 dark:bg-blue-950/40 dark:text-blue-100">
            Continuing with <span className="font-semibold">{requestedPlan.name}</span> on{' '}
            <span className="font-semibold">{requestedInterval}</span> billing. Review the details below to start checkout.
          </div>
        )}

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {plans.map((plan) => {
            const isRequestedPlan = requestedPlanId === plan._id;
            const displayInterval = isRequestedPlan ? requestedInterval : 'monthly';
            const displayPrice = displayInterval === 'yearly' && plan.price_yearly > 0
              ? plan.price_yearly
              : plan.price_monthly;
            const displayCadence = billingCadenceLabel(plan, displayInterval);

            return (
              <Card
                key={plan._id}
                className={`relative flex flex-col bg-white dark:bg-gray-800 transition-all hover:shadow-lg ${
                  isRequestedPlan
                    ? 'border-2 border-blue-600 dark:border-blue-300 shadow-lg ring-2 ring-blue-200/70 dark:ring-blue-500/40'
                    : plan.is_featured
                    ? 'border-2 border-blue-500 dark:border-blue-400 shadow-md'
                    : 'border border-gray-200 dark:border-gray-700'
                }`}
              >
                {(plan.is_featured || isRequestedPlan) && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-blue-500 text-white px-3 py-1">
                      {isRequestedPlan ? 'Selected' : 'Recommended'}
                    </Badge>
                  </div>
                )}
                <CardHeader className="text-center pb-4 pt-8">
                  <CardTitle className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                    {plan.name}
                  </CardTitle>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{plan.description}</p>
                  <div className="mt-4">
                    <span className="text-4xl font-bold text-gray-900 dark:text-white">
                      ${displayPrice}
                    </span>
                    <span className="text-gray-500 dark:text-gray-400">/{displayCadence}</span>
                    {plan.price_yearly > 0 && (
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                        or ${plan.price_yearly}/yr (save ${plan.price_monthly * 12 - plan.price_yearly})
                      </p>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col space-y-6 px-6 pb-8">
                  <ul className="space-y-3 text-sm flex-1">
                    {(plan.features_list && plan.features_list.length > 0 ? plan.features_list : [
                      `${plan.max_weddings === -1 ? 'Unlimited' : plan.max_weddings} weddings`,
                      `${plan.max_guests_per_wedding === -1 ? 'Unlimited' : plan.max_guests_per_wedding} guests per wedding`,
                      `${plan.storage_gb} GB storage`,
                      `${plan.staff_seats} staff seat${plan.staff_seats !== 1 ? 's' : ''}`,
                      `${plan.ai_credits_monthly} AI credits/month`,
                    ]).map((feature, idx) => (
                      <li key={idx} className="flex items-start gap-2.5 text-gray-700 dark:text-gray-300">
                        <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                  <Button
                    onClick={() => handleSubscribe(plan._id, displayInterval)}
                    className={`w-full py-3 text-base font-medium ${
                      isRequestedPlan || plan.is_featured
                        ? 'bg-blue-600 hover:bg-blue-700 text-white'
                        : 'bg-gray-900 dark:bg-gray-100 hover:bg-gray-800 dark:hover:bg-gray-200 text-white dark:text-gray-900'
                    }`}
                  >
                    {isRequestedPlan ? `Continue with ${displayInterval}` : 'Get Started'}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    );
  }

  if (needsPortalRecovery && !currentPlan) {
    return (
      <div className="space-y-6">
        <div className="mx-auto max-w-2xl rounded-2xl border border-amber-200 bg-amber-50 p-8 text-center dark:border-amber-900/60 dark:bg-amber-950/30">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300">
            <AlertCircle className="h-8 w-8" />
          </div>
          <h1 className="mb-2 text-2xl font-bold text-slate-900 dark:text-white">
            Billing Action Required
          </h1>
          <p className="mx-auto max-w-xl text-sm text-slate-600 dark:text-slate-300">
            Your billing relationship is still active, but the saved plan details could not be loaded.
            Use the billing portal to update your payment method or review your subscription before continuing.
          </p>
          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <Button onClick={handleUpdatePayment}>
              Update Payment Method
            </Button>
            <Button variant="outline" onClick={handleManageBilling}>
              Open Billing Portal
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!currentSubscription || !currentPlan) {
    return (
      <div className="space-y-6">
        <div className="mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-white p-8 text-center dark:border-slate-700 dark:bg-slate-900">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            <AlertCircle className="h-8 w-8" />
          </div>
          <h1 className="mb-2 text-2xl font-bold text-slate-900 dark:text-white">
            Billing Information Unavailable
          </h1>
          <p className="mx-auto max-w-xl text-sm text-slate-600 dark:text-slate-300">
            Your billing data could not be fully loaded. Refresh the page or open the billing portal to continue.
          </p>
          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <Button onClick={loadData}>
              Refresh Billing Data
            </Button>
            <Button variant="outline" onClick={handleManageBilling}>
              Open Billing Portal
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Has subscription - show billing dashboard
  const statusConfig = getStatusConfig(currentSubscription.status);
  const daysUntilRenewal = getDaysUntilRenewal();
  // Compute displayed invoices from all invoices using pagination
  const displayedInvoices = allInvoices.slice(
    (paginationInvoices.currentPage - 1) * paginationInvoices.itemsPerPage,
    paginationInvoices.currentPage * paginationInvoices.itemsPerPage
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Billing"
        description="Manage your subscription, payment methods, and billing history"
      />

      {/* Billing Alerts */}
      {billingAlerts.length > 0 && (
        <div className="space-y-3">
          {billingAlerts.map((alert, index) => (
            <div
              key={index}
              className={`p-4 rounded-lg border flex items-start gap-3 ${
                alert.type === 'error'
                  ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                  : alert.type === 'warning'
                  ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
                  : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
              }`}
            >
              {alert.type === 'error' ? (
                <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
              ) : alert.type === 'warning' ? (
                <AlertTriangle className="w-5 h-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" />
              ) : (
                <Clock className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
              )}
              <div className="flex-1">
                <p className={`font-medium ${
                  alert.type === 'error'
                    ? 'text-red-900 dark:text-red-100'
                    : alert.type === 'warning'
                    ? 'text-yellow-900 dark:text-yellow-100'
                    : 'text-blue-900 dark:text-blue-100'
                }`}>
                  {alert.title}
                </p>
                <p className={`text-sm mt-0.5 ${
                  alert.type === 'error'
                    ? 'text-red-700 dark:text-red-300'
                    : alert.type === 'warning'
                    ? 'text-yellow-700 dark:text-yellow-300'
                    : 'text-blue-700 dark:text-blue-300'
                }`}>
                  {alert.message}
                </p>
              </div>
              {alert.actionLabel && (
                <Button
                  size="sm"
                  onClick={alert.action === 'update_payment' ? handleUpdatePayment : handleManageBilling}
                  className={
                    alert.type === 'error'
                      ? 'bg-red-600 hover:bg-red-700 text-white'
                      : 'bg-yellow-600 hover:bg-yellow-700 text-white'
                  }
                >
                  {alert.actionLabel}
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Main Grid */}
      <div className="grid lg:grid-cols-3 gap-6 overflow-hidden">
        {/* Left Column - Subscription & Payment */}
        <div className="lg:col-span-2 space-y-6 min-w-0">

          {/* Payouts (Stripe Connect) — gates the planner's ability to
              collect from couples; sits above subscription because without
              payouts set up, there's no point in the rest. */}
          <PayoutsCard />

          {/* Current Subscription */}
          <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 p-6">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-gray-900 dark:text-gray-100">Your Subscription</CardTitle>
                <Badge className={`${statusConfig.bgColor} ${statusConfig.color} flex items-center gap-1`}>
                  {statusConfig.icon}
                  {statusConfig.label}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Plan Info */}
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                    {currentPlan.name} Plan
                  </h3>
                  <p className="text-gray-600 dark:text-gray-400 text-sm mt-1">
                    {currentPlan.description}
                  </p>
                </div>
                <div className="text-right">
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-bold text-gray-900 dark:text-white">
                      ${currentSubscription.billing_interval === 'yearly'
                        ? currentPlan.price_yearly
                        : currentPlan.price_monthly}
                    </span>
                    <span className="text-gray-500 dark:text-gray-400 text-sm">
                      /{billingCadenceLabel(
                        currentPlan,
                        currentSubscription.billing_interval === 'yearly' ? 'yearly' : 'monthly',
                      )}
                    </span>
                  </div>
                </div>
              </div>

              {/* Key Dates */}
              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Member since</p>
                  <p className="font-medium text-gray-900 dark:text-gray-100 mt-1">
                    {getMemberSinceDate()}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Next billing date</p>
                  <p className="font-medium text-gray-900 dark:text-gray-100 mt-1">
                    {formatDate(currentSubscription.current_period_end)}
                    {daysUntilRenewal !== null && daysUntilRenewal <= 7 && (
                      <span className="text-sm text-gray-500 dark:text-gray-400 ml-2">
                        ({daysUntilRenewal} days)
                      </span>
                    )}
                  </p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex flex-wrap gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
                <Button
                  onClick={handleChangePlan}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  <TrendingUp className="w-4 h-4 mr-2" />
                  Change Plan
                </Button>
                <Button
                  onClick={handleCancelSubscription}
                  variant="outline"
                  className="border-red-300 dark:border-red-600 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
                >
                  <XCircle className="w-4 h-4 mr-2" />
                  Cancel Subscription
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Payment Method */}
          <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 p-6">
            <CardHeader className="pb-4">
              <CardTitle className="text-gray-900 dark:text-gray-100">Payment Method</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-8 bg-gray-100 dark:bg-gray-700 rounded flex items-center justify-center">
                    <CreditCard className="w-6 h-6 text-gray-600 dark:text-gray-400" />
                  </div>
                  <div>
                    {currentSubscription.card_last_four ? (
                      <>
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {currentSubscription.card_brand || 'Card'} ending in {currentSubscription.card_last_four}
                        </p>
                        {currentSubscription.card_exp_month && currentSubscription.card_exp_year && (
                          <p className="text-sm text-gray-500 dark:text-gray-400">
                            Expires {currentSubscription.card_exp_month}/{currentSubscription.card_exp_year}
                          </p>
                        )}
                      </>
                    ) : (
                      <p className="text-gray-600 dark:text-gray-400">
                        Managed through Stripe
                      </p>
                    )}
                  </div>
                </div>
                <Button
                  onClick={handleUpdatePayment}
                  variant="outline"
                  className="border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Update
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Billing History */}
          <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 p-6">
            <CardHeader className="pb-4">
              <CardTitle className="text-gray-900 dark:text-gray-100">Billing History</CardTitle>
            </CardHeader>
            <CardContent>
              {allInvoices.length > 0 ? (
                <>
                  <div className="mb-4">
                    <GlassPagination
                      currentPage={paginationInvoices.currentPage}
                      totalPages={paginationInvoices.totalPages}
                      totalItems={paginationInvoices.totalItems}
                      itemsPerPage={paginationInvoices.itemsPerPage}
                      onPageChange={paginationInvoices.setPage}
                      variant="compact"
                      itemLabel="invoices"
                    />
                  </div>
                  <div className="divide-y divide-gray-200 dark:divide-gray-700">
                    {displayedInvoices.map((invoice) => (
                      <div
                        key={invoice.id}
                        className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
                      >
                        <div className="flex items-center gap-3">
                          <Receipt className="w-5 h-5 text-gray-400" />
                          <div>
                            <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">
                              {invoice.description || 'Invoice'}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              {formatDate(invoice.date)}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-medium text-gray-900 dark:text-gray-100">
                            ${(invoice.amount / 100).toFixed(2)}
                          </span>
                          {invoice.status === 'paid' && (
                            <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300 text-xs">
                              Paid
                            </Badge>
                          )}
                          {invoice.invoice_pdf && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-gray-500 hover:text-gray-700 p-1 h-auto"
                              onClick={() => window.open(invoice.invoice_pdf, '_blank')}
                            >
                              <Download className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                    <GlassPagination
                      currentPage={paginationInvoices.currentPage}
                      totalPages={paginationInvoices.totalPages}
                      totalItems={paginationInvoices.totalItems}
                      itemsPerPage={paginationInvoices.itemsPerPage}
                      onPageChange={paginationInvoices.setPage}
                      onItemsPerPageChange={paginationInvoices.setItemsPerPage}
                      itemLabel="invoices"
                    />
                  </div>
                </>
              ) : (
                <div className="text-center py-6 text-gray-500 dark:text-gray-400">
                  <Receipt className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No billing history yet</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column - Usage & Quick Actions */}
        <div className="space-y-6 min-w-0 overflow-hidden">
          {/* Usage This Period */}
          <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 p-6">
            <CardHeader className="pb-4">
              <CardTitle className="text-gray-900 dark:text-gray-100 text-base">Usage This Period</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Weddings */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-blue-500" />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Weddings</span>
                  </div>
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {usageStats.weddings_count} / {currentPlan.max_weddings === -1 ? '∞' : currentPlan.max_weddings}
                  </span>
                </div>
                {currentPlan.max_weddings !== -1 && (
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${getUsageColor(
                        getUsagePercentage(usageStats.weddings_count, currentPlan.max_weddings)
                      )}`}
                      style={{ width: `${Math.max(getUsagePercentage(usageStats.weddings_count, currentPlan.max_weddings), 3)}%` }}
                    />
                  </div>
                )}
              </div>

              {/* Guests */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-green-500" />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Total Guests</span>
                  </div>
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {usageStats.total_guests}
                  </span>
                </div>
              </div>

              {/* Storage */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-purple-500" />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Storage</span>
                  </div>
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {usageStats.storage_used_gb.toFixed(1)} / {currentPlan.storage_gb} GB
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all ${getUsageColor(
                      getUsagePercentage(usageStats.storage_used_gb, currentPlan.storage_gb)
                    )}`}
                    style={{ width: `${Math.max(getUsagePercentage(usageStats.storage_used_gb, currentPlan.storage_gb), 3)}%` }}
                  />
                </div>
              </div>

              {/* AI Credits — soft-capped with metered overage.
                  When usage exceeds the monthly allotment, `ai_overage` is
                  true and the running overage cost is surfaced inline. The
                  bar shows 100% filled in that case, with a distinct color
                  so the planner can tell they're billing past plan. */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-yellow-500" />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">AI Credits</span>
                  </div>
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {/* Display "used / limit". In overage we cap the
                        numerator at the included allotment so the
                        included-credits ratio reads cleanly; the extra
                        credits are surfaced in the orange callout below. */}
                    {usageStats.ai_overage
                      ? `${currentPlan.ai_credits_monthly} / ${currentPlan.ai_credits_monthly}`
                      : `${usageStats.ai_credits_used} / ${currentPlan.ai_credits_monthly}`}
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all ${
                      usageStats.ai_overage ? 'bg-orange-500' : 'bg-blue-500'
                    }`}
                    style={{
                      width: usageStats.ai_overage
                        ? '100%'
                        : `${Math.min(
                            100,
                            (usageStats.ai_credits_used /
                              (currentPlan.ai_credits_monthly || 1)) *
                              100,
                          )}%`,
                    }}
                  />
                </div>
                {usageStats.ai_overage && (
                  <div className="mt-2 rounded-lg border border-orange-300 bg-orange-50 px-3 py-2 text-xs text-orange-800 dark:border-orange-900/40 dark:bg-orange-950/30 dark:text-orange-200">
                    <p className="font-semibold">Overage billing active</p>
                    <p className="mt-0.5">
                      {(usageStats.ai_overage_credits ?? 0).toLocaleString()} extra credit
                      {(usageStats.ai_overage_credits ?? 0) === 1 ? '' : 's'} this cycle ·{' '}
                      <span className="font-semibold">
                        ${((usageStats.ai_overage_cost_cents ?? 0) / 100).toFixed(2)}
                      </span>{' '}
                      at $
                      {(usageStats.ai_overage_price_per_credit_usd ?? 0).toFixed(3)} per
                      credit. Charged on next invoice.
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Plan Features */}
          <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 p-6">
            <CardHeader className="pb-4">
              <CardTitle className="text-gray-900 dark:text-gray-100 text-base">Plan Features</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {currentPlan.features_list?.slice(0, 5).map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
                    <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                    {feature}
                  </li>
                ))}
              </ul>
              {(currentPlan.features_list?.length || 0) > 5 && (
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-3">
                  +{currentPlan.features_list!.length - 5} more features
                </p>
              )}
            </CardContent>
          </Card>

          {/* Need Help */}
          <Card className="bg-gray-50 dark:bg-gray-900/50 border-gray-200 dark:border-gray-700 p-6">
            <CardContent>
              <div className="flex items-start gap-3">
                <Shield className="w-5 h-5 text-gray-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">Need help?</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                    Contact our support team for billing questions or subscription changes.
                  </p>
                  <Button
                    variant="ghost"
                    className="text-blue-600 dark:text-blue-400 p-0 h-auto mt-2 text-sm hover:bg-transparent hover:underline"
                    onClick={() => router.push('/admin/support')}
                  >
                    Contact Support
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
