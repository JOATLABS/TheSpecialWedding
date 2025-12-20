"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
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
  features: Record<string, boolean>;
  features_list?: string[];
  is_featured: boolean;
}

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

export default function PlannerBillingPage() {
  const router = useRouter();
  const { userProfile } = useAdmin();
  const [loading, setLoading] = useState(true);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [currentSubscription, setCurrentSubscription] = useState<UserSubscription | null>(null);
  const [currentPlan, setCurrentPlan] = useState<SubscriptionPlan | null>(null);
  const [usageStats, setUsageStats] = useState<UsageStats>({
    weddings_count: 0,
    total_guests: 0,
    storage_used_gb: 0,
    ai_credits_used: 0,
    ai_credits_remaining: 100
  });
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [billingAlerts, setBillingAlerts] = useState<BillingAlert[]>([]);
  const [showAllInvoices, setShowAllInvoices] = useState(false);

  // Access control - only for wedding planners
  useEffect(() => {
    if (userProfile && !userProfile.is_wedding_planner && !userProfile.is_root_admin) {
      router.push('/admin');
    }
  }, [userProfile, router]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

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
          `${baseUrl}/admin/stripe/subscription`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            credentials: 'include'
          }
        );

        if (stripeSubResponse.ok) {
          const subData = await stripeSubResponse.json();
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
        const userId = userProfile.email || userProfile.id || '';
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

          if (subResponse.ok) {
            const subData = await subResponse.json();
            if (subData && subData.plan_id) {
              setCurrentSubscription(subData);
              const planDetail = fetchedPlans.find((p: SubscriptionPlan) => p._id === subData.plan_id);
              setCurrentPlan(planDetail || null);
              generateBillingAlerts(subData, planDetail);
            }
          } else {
            // Try alternative endpoint
            const altResponse = await fetch(
              `${baseUrl}/admin/planner/subscription`,
              {
                headers: {
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json'
                },
                credentials: 'include'
              }
            );

            if (altResponse.ok) {
              const altData = await altResponse.json();
              if (altData && altData.plan_id) {
                setCurrentSubscription(altData);
                const planDetail = fetchedPlans.find((p: SubscriptionPlan) => p._id === altData.plan_id);
                setCurrentPlan(planDetail || null);
                generateBillingAlerts(altData, planDetail);
              }
            }
          }
        }
      }

      // Load usage statistics
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

      // Load billing history from Stripe
      try {
        const invoicesResponse = await fetch(
          `${baseUrl}/admin/stripe/invoices`,
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
          setInvoices(formattedInvoices);
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
  }, [userProfile]);

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
    if (subscription.status === 'past_due') {
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

      if (daysUntilRenewal <= 7 && daysUntilRenewal > 0 && subscription.status === 'active') {
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

  const handleManageBilling = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      if (!token) {
        toast.error('Please log in to manage billing');
        return;
      }

      const response = await fetch(
        `${baseUrl}/admin/stripe/create-portal-session`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify({
            return_url: `${window.location.origin}/admin/planner/billing`
          })
        }
      );

      if (!response.ok) {
        throw new Error('Failed to create portal session');
      }

      const data = await response.json();

      if (data.portal_url) {
        window.location.href = data.portal_url;
      }
    } catch (error) {
      console.error('Portal error:', error);
      toast.error('Failed to open billing portal. Please contact support.');
    }
  };

  const handleSubscribe = async (planId: string, interval: 'monthly' | 'yearly' = 'monthly') => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      if (!token) {
        toast.error('Please log in to subscribe');
        return;
      }

      const response = await fetch(
        `${baseUrl}/admin/stripe/create-checkout-session`,
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
            success_url: `${window.location.origin}/admin/planner/billing?success=true`,
            cancel_url: `${window.location.origin}/admin/planner/billing`,
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
    const config: Record<string, { color: string; bgColor: string; icon: React.ReactNode; label: string }> = {
      active: {
        color: 'text-green-700 dark:text-green-300',
        bgColor: 'bg-green-100 dark:bg-green-900/30',
        icon: <CheckCircle2 className="w-4 h-4" />,
        label: 'Active'
      },
      trialing: {
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
      }
    };
    return config[status] || config.active;
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

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric'
    });
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

  // No subscription - show simple onboarding
  if (!currentSubscription || !currentPlan) {
    return (
      <div className="space-y-6 max-w-4xl mx-auto">
        <div className="text-center py-12">
          <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <CreditCard className="w-8 h-8 text-blue-600 dark:text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
            Choose Your Plan
          </h1>
          <p className="text-gray-600 dark:text-gray-400 max-w-md mx-auto">
            Select a subscription plan to unlock all features and start managing your weddings.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {plans.map((plan) => (
            <Card
              key={plan._id}
              className={`relative bg-white dark:bg-gray-800 transition-all hover:shadow-lg ${
                plan.is_featured
                  ? 'border-2 border-blue-500 dark:border-blue-400'
                  : 'border border-gray-200 dark:border-gray-700'
              }`}
            >
              {plan.is_featured && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge className="bg-blue-500 text-white px-3">Recommended</Badge>
                </div>
              )}
              <CardHeader className="text-center pb-2">
                <CardTitle className="text-lg text-gray-900 dark:text-gray-100">
                  {plan.name}
                </CardTitle>
                <div className="mt-3">
                  <span className="text-3xl font-bold text-gray-900 dark:text-white">
                    ${plan.price_monthly}
                  </span>
                  <span className="text-gray-500 dark:text-gray-400">/mo</span>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center gap-2 text-gray-700 dark:text-gray-300">
                    <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                    {plan.max_weddings === -1 ? 'Unlimited' : plan.max_weddings} weddings
                  </li>
                  <li className="flex items-center gap-2 text-gray-700 dark:text-gray-300">
                    <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                    {plan.max_guests_per_wedding} guests per wedding
                  </li>
                  <li className="flex items-center gap-2 text-gray-700 dark:text-gray-300">
                    <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                    {plan.storage_gb} GB storage
                  </li>
                </ul>
                <Button
                  onClick={() => handleSubscribe(plan._id)}
                  className={`w-full ${
                    plan.is_featured
                      ? 'bg-blue-600 hover:bg-blue-700 text-white'
                      : 'bg-gray-900 dark:bg-gray-100 hover:bg-gray-800 dark:hover:bg-gray-200 text-white dark:text-gray-900'
                  }`}
                >
                  Get Started
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Has subscription - show billing dashboard
  const statusConfig = getStatusConfig(currentSubscription.status);
  const daysUntilRenewal = getDaysUntilRenewal();
  const displayedInvoices = showAllInvoices ? invoices : invoices.slice(0, 3);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Billing</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Manage your subscription, payment methods, and billing history
        </p>
      </div>

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
                  onClick={handleManageBilling}
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
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left Column - Subscription & Payment */}
        <div className="lg:col-span-2 space-y-6">
          {/* Current Subscription */}
          <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700">
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
                      /{currentSubscription.billing_interval === 'monthly' ? 'mo' : 'yr'}
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
                  onClick={handleManageBilling}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  <TrendingUp className="w-4 h-4 mr-2" />
                  Change Plan
                </Button>
                <Button
                  onClick={handleManageBilling}
                  variant="outline"
                  className="border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300"
                >
                  <XCircle className="w-4 h-4 mr-2" />
                  Cancel Subscription
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Payment Method */}
          <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700">
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
                  onClick={handleManageBilling}
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
          <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-gray-900 dark:text-gray-100">Billing History</CardTitle>
                {invoices.length > 3 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowAllInvoices(!showAllInvoices)}
                    className="text-blue-600 dark:text-blue-400 hover:text-blue-700"
                  >
                    {showAllInvoices ? 'Show Less' : `View All (${invoices.length})`}
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {invoices.length > 0 ? (
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
        <div className="space-y-6">
          {/* Usage This Period */}
          <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700">
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

              {/* AI Credits */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-yellow-500" />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">AI Credits</span>
                  </div>
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {usageStats.ai_credits_remaining} / {currentPlan.ai_credits_monthly}
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className="h-2 rounded-full transition-all bg-blue-500"
                    style={{ width: `${(usageStats.ai_credits_remaining / currentPlan.ai_credits_monthly) * 100}%` }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Plan Features */}
          <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700">
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
          <Card className="bg-gray-50 dark:bg-gray-900/50 border-gray-200 dark:border-gray-700">
            <CardContent className="pt-6">
              <div className="flex items-start gap-3">
                <Shield className="w-5 h-5 text-gray-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">Need help?</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                    Contact our support team for billing questions or subscription changes.
                  </p>
                  <Button
                    variant="link"
                    className="text-blue-600 dark:text-blue-400 p-0 h-auto mt-2 text-sm"
                    onClick={() => window.open('mailto:support@example.com', '_blank')}
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